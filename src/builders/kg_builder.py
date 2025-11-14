from typing import Dict, Any, Optional, List
import uuid
import asyncio
from ..core.text_chunker import TextChunker
from ..core.embeddings import EmbeddingGenerator
from ..core.entity_extractor import EntityRelationshipExtractor
from ..core.logger import log
from ..storage.qdrant_store import QdrantVectorStore
from ..storage.neo4j_store import Neo4jGraphStore
from ..storage.elasticsearch_store import ElasticsearchStore
from ..storage.redis_cache import RedisCache
from ..config.models import LLMModels, EmbeddingModels, IndexNames


class KnowledgeGraphBuilder:
    def __init__(
        self,
        openai_api_key: str,
        neo4j_uri: str,
        neo4j_username: str,
        neo4j_password: str,
        qdrant_url: Optional[str] = None,
        qdrant_api_key: Optional[str] = None,
        elasticsearch_url: Optional[str] = None,
        elasticsearch_api_key: Optional[str] = None,
        chunk_size: int = 500,
        chunk_overlap: int = 100,
        embedding_model: str = EmbeddingModels.TEXT_EMBEDDING_3_LARGE.value,
        llm_model: str = LLMModels.GPT_4_POINT_1.value,
        redis_cache: Optional[RedisCache] = None,
    ):
        self.chunker = TextChunker(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        self.embedder = EmbeddingGenerator(
            openai_api_key, embedding_model, redis_cache=redis_cache
        )
        self.extractor = EntityRelationshipExtractor(
            openai_api_key, llm_model, redis_cache=redis_cache
        )

        dimension = self.embedder.get_dimension()
        self.vector_store = QdrantVectorStore(
            collection_name=IndexNames.LEGAL_DOCS.value,
            url=qdrant_url,
            api_key=qdrant_api_key,
            dimension=dimension,
        )
        self.graph_store = Neo4jGraphStore(
            uri=neo4j_uri, username=neo4j_username, password=neo4j_password
        )
        self.elasticsearch_store = ElasticsearchStore(
            index_name=IndexNames.LEGAL_DOCS.value,
            url=elasticsearch_url,
            api_key=elasticsearch_api_key,
        )

    async def initialize(self):
        await self.graph_store._initialize()

    async def async_build_from_text_batch(
        self, text: str, document_id: Optional[str] = None, batch_offset: int = 0
    ) -> Dict[str, Any]:
        if not document_id:
            document_id = str(uuid.uuid4())

        chunks = self.chunker.chunk_text(text)

        if not chunks:
            return {
                "document_id": document_id,
                "chunks_created": 0,
                "entities_extracted": 0,
                "relationships_extracted": 0,
                "embeddings_generated": 0,
            }

        chunk_texts = [chunk["text"] for chunk in chunks]

        embeddings_task = self.embedder.async_embed_batch(chunk_texts)
        extractions_task = self.extractor.async_extract_batch(chunk_texts)

        embeddings, extractions = await asyncio.gather(
            embeddings_task, extractions_task
        )

        all_entities = []
        all_relationships = []
        chunk_ids = []

        for i, chunk in enumerate[dict[Any, Any]](chunks):
            chunk_id = f"{document_id}_chunk_{batch_offset + i}"
            chunk["chunk_id"] = chunk_id
            chunk["document_id"] = document_id
            chunk_ids.append(chunk_id)

            extraction = extractions[i]
            entities = extraction.get("nodes", [])
            relationships = extraction.get("relationships", [])

            all_entities.extend(entities)
            all_relationships.extend(relationships)

        log.debug(
            f"Processing {len(chunks)} chunks, {len(all_entities)} entities, {len(all_relationships)} relationships"
        )

        qdrant_task = self.vector_store.async_add_chunks(chunks, embeddings)
        elasticsearch_task = self.elasticsearch_store.async_add_chunks(chunks)

        await asyncio.gather(qdrant_task, elasticsearch_task)

        await self.graph_store.async_add_chunks_batch(chunks, chunk_ids)

        for i, (chunk, chunk_id) in enumerate(zip(chunks, chunk_ids)):
            extraction = extractions[i]
            entities = extraction.get("nodes", [])
            if entities:
                await self.graph_store.async_add_entities(entities, chunk_id)

        await self.graph_store.async_add_relationships(all_relationships)

        return {
            "document_id": document_id,
            "chunks_created": len(chunks),
            "entities_extracted": len(all_entities),
            "relationships_extracted": len(all_relationships),
            "embeddings_generated": len(embeddings),
        }

    async def async_build_from_text_batches(
        self,
        text_batches: List[str],
        document_id: Optional[str] = None,
        max_concurrent_batches: int = 3,
    ) -> Dict[str, Any]:
        if not document_id:
            document_id = str(uuid.uuid4())

        semaphore = asyncio.Semaphore(max_concurrent_batches)

        async def process_batch_with_offset(
            batch_text: str, batch_idx: int
        ) -> Dict[str, Any]:
            async with semaphore:
                batch_offset = batch_idx * 10000

                log.info(f"Processing batch {batch_idx} of {len(text_batches)}")
                return await self.async_build_from_text_batch(
                    batch_text, document_id=document_id, batch_offset=batch_offset
                )

        tasks = [
            process_batch_with_offset(batch, idx)
            for idx, batch in enumerate[str](text_batches)
        ]
        results = await asyncio.gather(*tasks, return_exceptions=False)

        total_chunks = sum(r["chunks_created"] for r in results)
        total_entities = sum(r["entities_extracted"] for r in results if r is not None)
        total_relationships = sum(
            r["relationships_extracted"] for r in results if r is not None
        )
        total_embeddings = sum(
            r["embeddings_generated"] for r in results if r is not None
        )

        return {
            "document_id": document_id,
            "chunks_created": total_chunks,
            "entities_extracted": total_entities,
            "relationships_extracted": total_relationships,
            "embeddings_generated": total_embeddings,
            "batches_processed": len(text_batches),
        }

    async def clear_all(self):
        log.info("Clearing all data...")
        try:
            await asyncio.gather(
                asyncio.to_thread(self.vector_store.delete_collection),
                asyncio.to_thread(self.elasticsearch_store.delete_index),
                self.graph_store.clear_all(),
                return_exceptions=True,
            )
        except Exception as e:
            log.warning(f"Error during cleanup: {e}")

        log.info("All data cleared")
