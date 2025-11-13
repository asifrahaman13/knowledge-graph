import logging
import sys
from functools import wraps
from typing import Optional, Callable, Any


def ensure_logger(func: Callable) -> Callable:
    @wraps(func)
    def wrapper(self: "Logger", *args: Any, **kwargs: Any) -> Any:
        _ = self.logger
        return func(self, *args, **kwargs)

    return wrapper


class Logger:
    _instance: Optional["Logger"] = None
    _logger: Optional[logging.Logger] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(Logger, cls).__new__(cls)
            cls._instance._setup_logger()
        return cls._instance

    def _setup_logger(self):
        self._logger = logging.getLogger("knowledge_graph")
        self._logger.setLevel(logging.DEBUG)

        if not self._logger.handlers:
            handler = logging.StreamHandler(sys.stdout)
            handler.setLevel(logging.DEBUG)

            formatter = logging.Formatter(
                "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
            handler.setFormatter(formatter)
            self._logger.addHandler(handler)

    @property
    def logger(self) -> logging.Logger:
        """Property that ensures logger is initialized and returns non-optional logger."""
        if self._logger is None:
            self._setup_logger()
        assert self._logger is not None, "Logger should be initialized"
        return self._logger

    @ensure_logger
    def debug(self, message: str):
        self.logger.debug(message)

    @ensure_logger
    def info(self, message: str):
        self.logger.info(message)

    @ensure_logger
    def warning(self, message: str):
        self.logger.warning(message)

    @ensure_logger
    def error(self, message: str):
        self.logger.error(message)

    @ensure_logger
    def critical(self, message: str):
        self.logger.critical(message)

    @ensure_logger
    def set_level(self, level: str):
        level_map = {
            "DEBUG": logging.DEBUG,
            "INFO": logging.INFO,
            "WARNING": logging.WARNING,
            "ERROR": logging.ERROR,
            "CRITICAL": logging.CRITICAL,
        }
        self.logger.setLevel(level_map.get(level.upper(), logging.INFO))


def get_logger() -> Logger:
    return Logger()


log = get_logger()
