"""
Embedding Generation Module
Creates vector embeddings for text using OpenAI
"""

from typing import List
import asyncio
from openai import OpenAI, AsyncOpenAI
from models import EmbeddingModels


class EmbeddingGenerator:
    """Generates embeddings using OpenAI API"""

    def __init__(
        self, api_key: str, model: str = EmbeddingModels.TEXT_EMBEDDING_3_LARGE.value
    ):
        """
        Initialize embedding generator

        Args:
            api_key: OpenAI API key
            model: Embedding model to use (default: text-embedding-3-large)
        """
        self.client = OpenAI(api_key=api_key)
        self.async_client = AsyncOpenAI(api_key=api_key)
        self.model = model
        self.dimension = 3072  # Default for text-embedding-3-large

    def embed_text(self, text: str) -> List[float]:
        """
        Generate embedding for a single text

        Args:
            text: Text to embed

        Returns:
            List of floats representing the embedding vector
        """
        try:
            response = self.client.embeddings.create(model=self.model, input=text)
            return response.data[0].embedding
        except Exception as e:
            raise Exception(f"Error generating embedding: {e}")

    def embed_batch(self, texts: List[str], batch_size: int = 100) -> List[List[float]]:
        """
        Generate embeddings for multiple texts

        Args:
            texts: List of texts to embed
            batch_size: Number of texts to process in each batch

        Returns:
            List of embedding vectors
        """
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
        """
        Generate embeddings for multiple texts asynchronously with parallel batch processing

        Args:
            texts: List of texts to embed
            batch_size: Number of texts to process in each batch
            max_concurrent_batches: Maximum number of concurrent batch requests

        Returns:
            List of embedding vectors
        """
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

        # Split texts into batches
        batches = [texts[i : i + batch_size] for i in range(0, len(texts), batch_size)]

        # Process batches in parallel
        tasks = [embed_single_batch(batch) for batch in batches]
        batch_results = await asyncio.gather(*tasks)

        # Flatten results
        embeddings = []
        for batch_result in batch_results:
            embeddings.extend(batch_result)

        return embeddings

    def get_dimension(self) -> int:
        """Get the dimension of embeddings"""
        return self.dimension
