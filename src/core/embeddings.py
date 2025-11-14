from typing import List, Optional, Tuple, cast
import asyncio
import hashlib
from openai import OpenAI, AsyncOpenAI
from ..config.models import EmbeddingModels
from ..storage.redis_cache import RedisCache


class EmbeddingGenerator:
    def __init__(
        self,
        api_key: str,
        model: str = EmbeddingModels.TEXT_EMBEDDING_3_LARGE.value,
        redis_cache: Optional[RedisCache] = None,
        cache_ttl: int = 86400 * 3,
    ):
        self.client = OpenAI(api_key=api_key)
        self.async_client = AsyncOpenAI(api_key=api_key)
        self.model = model
        self.dimension = 3072
        self.cache = redis_cache
        self.cache_ttl = cache_ttl

    def _get_cache_key(self, text: str) -> str:
        text_hash = hashlib.sha256(f"{self.model}:{text}".encode()).hexdigest()
        return f"embedding:{self.model}:{text_hash}"

    def embed_text(self, text: str) -> List[float]:
        if self.cache:
            cache_key = self._get_cache_key(text)
            cached = self.cache.get(cache_key)
            if cached is not None:
                return cached

        try:
            response = self.client.embeddings.create(model=self.model, input=text)
            embedding = response.data[0].embedding

            if self.cache:
                cache_key = self._get_cache_key(text)
                self.cache.set(cache_key, embedding, ttl=self.cache_ttl, serialize=True)

            return embedding
        except Exception as e:
            raise Exception(f"Error generating embedding: {e}")

    def embed_batch(self, texts: List[str], batch_size: int = 100) -> List[List[float]]:
        embeddings: List[Optional[List[float]]] = [None] * len(texts)
        uncached_indices = []
        uncached_texts = []

        if self.cache:
            for i, text in enumerate(texts):
                cache_key = self._get_cache_key(text)
                cached = self.cache.get(cache_key)
                if cached is not None:
                    embeddings[i] = cached
                else:
                    uncached_indices.append(i)
                    uncached_texts.append(text)
        else:
            uncached_indices = list(range(len(texts)))
            uncached_texts = texts

        if uncached_texts:
            for i in range(0, len(uncached_texts), batch_size):
                batch = uncached_texts[i : i + batch_size]
                batch_indices = uncached_indices[i : i + batch_size]
                try:
                    response = self.client.embeddings.create(
                        model=self.model, input=batch
                    )
                    batch_embeddings = [item.embedding for item in response.data]

                    for j, (embedding, orig_idx) in enumerate[tuple[List[float], int]](
                        zip(batch_embeddings, batch_indices)
                    ):
                        embeddings[orig_idx] = embedding
                        if self.cache:
                            cache_key = self._get_cache_key(uncached_texts[i + j])
                            self.cache.set(
                                cache_key, embedding, ttl=self.cache_ttl, serialize=True
                            )
                except Exception as e:
                    raise Exception(f"Error generating batch embeddings: {e}")

        result = [emb for emb in embeddings if emb is not None]
        return cast(List[List[float]], result)

    async def async_embed_batch(
        self, texts: List[str], batch_size: int = 50, max_concurrent_batches: int = 10
    ) -> List[List[float]]:
        embeddings: List[Optional[List[float]]] = [None] * len(texts)
        uncached_indices = []
        uncached_texts = []

        if self.cache:
            for i, text in enumerate(texts):
                cache_key = self._get_cache_key(text)
                cached = await self.cache.async_get(cache_key)
                if cached is not None:
                    embeddings[i] = cached
                else:
                    uncached_indices.append(i)
                    uncached_texts.append(text)
        else:
            uncached_indices = list(range(len(texts)))
            uncached_texts = texts

        if uncached_texts:
            semaphore = asyncio.Semaphore(max_concurrent_batches)

            async def embed_single_batch(
                batch: List[str], batch_uncached_indices: List[int]
            ) -> Tuple[List[int], List[List[float]]]:
                async with semaphore:
                    try:
                        response = await self.async_client.embeddings.create(
                            model=self.model, input=batch
                        )
                        batch_embeddings = [item.embedding for item in response.data]

                        if self.cache:
                            for _, (embedding, text) in enumerate(
                                zip(batch_embeddings, batch)
                            ):
                                cache_key = self._get_cache_key(text)
                                await self.cache.async_set(
                                    cache_key,
                                    embedding,
                                    ttl=self.cache_ttl,
                                    serialize=True,
                                )

                        return batch_uncached_indices, batch_embeddings
                    except Exception as e:
                        raise Exception(f"Error generating batch embeddings: {e}")

            batches = [
                uncached_texts[i : i + batch_size]
                for i in range(0, len(uncached_texts), batch_size)
            ]
            batch_indices = [
                uncached_indices[i : i + batch_size]
                for i in range(0, len(uncached_indices), batch_size)
            ]

            tasks = [
                embed_single_batch(batch, indices)
                for batch, indices in zip(batches, batch_indices)
            ]
            batch_results = await asyncio.gather(*tasks)

            for orig_indices, batch_embeddings in batch_results:
                for orig_idx, embedding in zip(orig_indices, batch_embeddings):
                    embeddings[orig_idx] = embedding

        result = [emb for emb in embeddings if emb is not None]
        return cast(List[List[float]], result)

    def get_dimension(self) -> int:
        return self.dimension
