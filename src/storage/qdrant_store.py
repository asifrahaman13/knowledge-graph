from typing import List, Dict, Any, Optional
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
import uuid
import asyncio
from concurrent.futures import ThreadPoolExecutor
from ..config.models import IndexNames
from ..core.logger import log


class QdrantVectorStore:
    def __init__(
        self,
        collection_name: str = IndexNames.LEGAL_DOCS.value,
        url: Optional[str] = None,
        api_key: Optional[str] = None,
        dimension: int = 3072,
    ):
        self.collection_name = collection_name
        self.dimension = dimension

        if url:
            self.client = QdrantClient(url=url, api_key=api_key)
        else:
            log.info("Connecting to Qdrant at: ./qdrant_db")

        self._ensure_collection()

    def _ensure_collection(self):
        try:
            collections = self.client.get_collections()
            collection_names = [col.name for col in collections.collections]

            if self.collection_name not in collection_names:
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(
                        size=self.dimension, distance=Distance.COSINE
                    ),
                )
        except Exception:
            pass

    def add_chunks(self, chunks: List[Dict[str, Any]], embeddings: List[List[float]]):
        if len(chunks) != len(embeddings):
            raise ValueError("Number of chunks must match number of embeddings")

        points = []
        for i, (chunk, embedding) in enumerate[tuple[Dict[str, Any], List[float]]](
            zip[tuple[Dict[str, Any], List[float]]](chunks, embeddings)
        ):
            point_id = str(uuid.uuid4())
            original_chunk_id = chunk.get("chunk_id", point_id)

            point = PointStruct(
                id=point_id,
                vector=embedding,
                payload={
                    "chunk_id": original_chunk_id,
                    "text": chunk["text"],
                    "chunk_index": chunk.get("chunk_index", i),
                    "start_char": chunk.get("start_char", 0),
                    "end_char": chunk.get("end_char", 0),
                    "document_id": chunk.get("document_id", "default"),
                },
            )
            points.append(point)

        self.client.upsert(collection_name=self.collection_name, points=points)

    async def async_add_chunks(
        self, chunks: List[Dict[str, Any]], embeddings: List[List[float]]
    ):
        """Async version of add_chunks using thread pool."""
        if len(chunks) != len(embeddings):
            raise ValueError("Number of chunks must match number of embeddings")

        points = []
        for i, (chunk, embedding) in enumerate[tuple[Dict[str, Any], List[float]]](
            zip(chunks, embeddings)
        ):
            point_id = str(uuid.uuid4())
            original_chunk_id = chunk.get("chunk_id", point_id)

            point = PointStruct(
                id=point_id,
                vector=embedding,
                payload={
                    "chunk_id": original_chunk_id,
                    "text": chunk["text"],
                    "chunk_index": chunk.get("chunk_index", i),
                    "start_char": chunk.get("start_char", 0),
                    "end_char": chunk.get("end_char", 0),
                    "document_id": chunk.get("document_id", "default"),
                },
            )
            points.append(point)

        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as executor:
            await loop.run_in_executor(
                executor,
                lambda: self.client.upsert(
                    collection_name=self.collection_name, points=points
                ),
            )

    def search(
        self, query_embedding: List[float], top_k: int = 5
    ) -> List[Dict[str, Any]]:
        results = self.client.search(
            collection_name=self.collection_name,
            query_vector=query_embedding,
            limit=top_k,
        )

        chunks = []
        for result in results:
            payload = result.payload or {}
            chunks.append(
                {
                    "chunk_id": payload.get("chunk_id", str(result.id)),
                    "point_id": str(result.id),
                    "text": payload.get("text", ""),
                    "score": result.score,
                    "chunk_index": payload.get("chunk_index", 0),
                    "start_char": payload.get("start_char", 0),
                    "end_char": payload.get("end_char", 0),
                    "document_id": payload.get("document_id", "default"),
                }
            )

        return chunks

    def delete_collection(self):
        try:
            self.client.delete_collection(self.collection_name)
        except Exception:
            pass
