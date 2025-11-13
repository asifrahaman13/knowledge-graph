from typing import Any, Optional
import json
import hashlib
import redis
from redis.exceptions import ConnectionError, TimeoutError
from ..core.logger import log


class RedisCache:
    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        password: Optional[str] = None,
        socket_timeout: int = 5,
        socket_connect_timeout: int = 5,
        decode_responses: bool = False,
        default_ttl: int = 86400,  # 24 hours default
    ):
        self.default_ttl = default_ttl
        self._client: Optional[redis.Redis] = None
        self._connected = False

        try:
            self._client = redis.Redis(
                host=host,
                port=port,
                db=db,
                password=password,
                socket_timeout=socket_timeout,
                socket_connect_timeout=socket_connect_timeout,
                decode_responses=decode_responses,
                retry_on_timeout=True,
            )
            self._client.ping()
            self._connected = True
            log.info(f"Connected to Redis at {host}:{port}")
        except (ConnectionError, TimeoutError, Exception) as e:
            log.warning(f"Redis connection failed: {e}. Caching will be disabled.")
            self._connected = False
            self._client = None

    def is_connected(self) -> bool:
        if not self._connected or not self._client:
            return False
        try:
            self._client.ping()
            return True
        except Exception:
            self._connected = False
            return False

    def _generate_key(self, prefix: str, *args: Any) -> str:
        key_parts = [prefix]
        for arg in args:
            if isinstance(arg, (dict, list)):
                key_parts.append(json.dumps(arg, sort_keys=True))
            elif isinstance(arg, (int, float, str, bool)):
                key_parts.append(str(arg))
            else:
                key_parts.append(str(arg))
        key_string = ":".join(key_parts)
        if len(key_string) > 250:
            key_hash = hashlib.sha256(key_string.encode()).hexdigest()
            return f"{prefix}:{key_hash}"
        return key_string

    def get(self, key: str) -> Optional[Any]:
        if not self.is_connected() or self._client is None:
            return None

        try:
            value = self._client.get(key)
            if value is None:
                return None

            try:
                if isinstance(value, bytes):
                    return json.loads(value.decode("utf-8"))
                elif isinstance(value, str):
                    return json.loads(value)
                else:
                    return json.loads(str(value))
            except (json.JSONDecodeError, TypeError):
                return value

        except Exception as e:
            log.warning(f"Redis get error for key {key}: {e}")
            return None

    def set(
        self, key: str, value: Any, ttl: Optional[int] = None, serialize: bool = True
    ) -> bool:
        if not self.is_connected() or self._client is None:
            return False

        try:
            ttl = ttl if ttl is not None else self.default_ttl

            if serialize:
                if isinstance(value, (dict, list)):
                    serialized = json.dumps(value)
                elif isinstance(value, (str, int, float, bool)):
                    serialized = json.dumps(value)
                else:
                    serialized = json.dumps(value, default=str)
            else:
                serialized = value

            self._client.setex(key, ttl, serialized)
            return True

        except Exception as e:
            log.warning(f"Redis set error for key {key}: {e}")
            return False

    def delete(self, key: str) -> bool:
        if not self.is_connected() or self._client is None:
            return False

        try:
            self._client.delete(key)
            return True
        except Exception as e:
            log.warning(f"Redis delete error for key {key}: {e}")
            return False

    def delete_pattern(self, pattern: str) -> int:
        if not self.is_connected() or self._client is None:
            return 0

        try:
            keys = self._client.keys(pattern)
            if keys and isinstance(keys, (list, tuple)):
                deleted_count = self._client.delete(*keys)
                if isinstance(deleted_count, int):
                    return deleted_count
                elif isinstance(deleted_count, (float, str)):
                    return int(deleted_count)
            return 0
        except Exception as e:
            log.warning(f"Redis delete_pattern error for pattern {pattern}: {e}")
            return 0

    def exists(self, key: str) -> bool:
        if not self.is_connected() or self._client is None:
            return False

        try:
            return bool(self._client.exists(key))
        except Exception as e:
            log.warning(f"Redis exists error for key {key}: {e}")
            return False

    def get_or_set(
        self,
        key: str,
        func,
        ttl: Optional[int] = None,
        serialize: bool = True,
        *args,
        **kwargs,
    ) -> Any:
        cached = self.get(key)
        if cached is not None:
            return cached

        value = func(*args, **kwargs)
        self.set(key, value, ttl=ttl, serialize=serialize)
        return value

    async def async_get(self, key: str) -> Optional[Any]:
        if not self.is_connected():
            return None
        return self.get(key)

    async def async_set(
        self, key: str, value: Any, ttl: Optional[int] = None, serialize: bool = True
    ) -> bool:
        if not self.is_connected():
            return False
        return self.set(key, value, ttl=ttl, serialize=serialize)

    def clear_all(self) -> bool:
        if not self.is_connected() or self._client is None:
            return False

        try:
            self._client.flushdb()
            log.info("Redis cache cleared")
            return True
        except Exception as e:
            log.warning(f"Redis clear_all error: {e}")
            return False
