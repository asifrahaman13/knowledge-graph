from typing import List
import asyncio
from openai import OpenAI, AsyncOpenAI
from models import EmbeddingModels


class EmbeddingGenerator:
    def __init__(
        self, api_key: str, model: str = EmbeddingModels.TEXT_EMBEDDING_3_LARGE.value
    ):
        self.client = OpenAI(api_key=api_key)
        self.async_client = AsyncOpenAI(api_key=api_key)
        self.model = model
        self.dimension = 3072

    def embed_text(self, text: str) -> List[float]:
        try:
            response = self.client.embeddings.create(model=self.model, input=text)
            return response.data[0].embedding
        except Exception as e:
            raise Exception(f"Error generating embedding: {e}")

    def embed_batch(self, texts: List[str], batch_size: int = 100) -> List[List[float]]:
        embeddings = []

        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            try:
                response = self.client.embeddings.create(model=self.model, input=batch)
                batch_embeddings = [item.embedding for item in response.data]
                embeddings.extend(batch_embeddings)
            except Exception as e:
                raise Exception(f"Error generating batch embeddings: {e}")

        return embeddings

    async def async_embed_batch(
        self, texts: List[str], batch_size: int = 50, max_concurrent_batches: int = 10
    ) -> List[List[float]]:
        semaphore = asyncio.Semaphore(max_concurrent_batches)

        async def embed_single_batch(batch: List[str]) -> List[List[float]]:
            async with semaphore:
                try:
                    response = await self.async_client.embeddings.create(
                        model=self.model, input=batch
                    )
                    return [item.embedding for item in response.data]
                except Exception as e:
                    raise Exception(f"Error generating batch embeddings: {e}")

        batches = [texts[i : i + batch_size] for i in range(0, len(texts), batch_size)]

        tasks = [embed_single_batch(batch) for batch in batches]
        batch_results = await asyncio.gather(*tasks)

        embeddings = []
        for batch_result in batch_results:
            embeddings.extend(batch_result)

        return embeddings

    def get_dimension(self) -> int:
        return self.dimension
