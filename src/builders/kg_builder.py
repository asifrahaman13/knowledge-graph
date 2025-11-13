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
    ):
        self.chunker = TextChunker(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        self.embedder = EmbeddingGenerator(openai_api_key, embedding_model)
        self.extractor = EntityRelationshipExtractor(openai_api_key, llm_model)

        dimension = self.embedder.get_dimension()
        self.vector_store = QdrantVectorStore(
            collection_name="text_chunks",
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

    def build_from_text(
        self, text: str, document_id: Optional[str] = None
    ) -> Dict[str, Any]:
        if not document_id:
            document_id = str(uuid.uuid4())

        log.info("Step 1: Chunking text...")
        chunks = self.chunker.chunk_text(text)
        log.info(f"Created {len(chunks)} chunks")

        log.info("Step 2: Generating embeddings...")
        chunk_texts = [chunk["text"] for chunk in chunks]
        embeddings = self.embedder.embed_batch(chunk_texts)
        log.info(f"Generated {len(embeddings)} embeddings")

        log.info("Step 3: Extracting entities and relationships...")
        all_entities = []
        all_relationships = []

        for i, chunk in enumerate(chunks):
            chunk_id = f"{document_id}_chunk_{i}"
            chunk["chunk_id"] = chunk_id
            chunk["document_id"] = document_id

            extraction = self.extractor.extract(chunk["text"])
            entities = extraction.get("nodes", [])
            relationships = extraction.get("relationships", [])

            all_entities.extend(entities)
            all_relationships.extend(relationships)

            self.graph_store.add_chunk(chunk, chunk_id)

            self.graph_store.add_entities(entities, chunk_id)

        log.info(
            f"Extracted {len(all_entities)} entities and {len(all_relationships)} relationships"
        )

        log.info("Step 4: Storing chunks in Qdrant...")
        self.vector_store.add_chunks(chunks, embeddings)
        log.info("Chunks stored in Qdrant")

        log.info("Step 5: Storing chunks in Elasticsearch...")
        self.elasticsearch_store.add_chunks(chunks)
        log.info("Chunks stored in Elasticsearch")

        log.info("Step 6: Storing relationships in Neo4j...")
        self.graph_store.add_relationships(all_relationships)
        log.info("Relationships stored in Neo4j")

        return {
            "document_id": document_id,
            "chunks_created": len(chunks),
            "entities_extracted": len(all_entities),
            "relationships_extracted": len(all_relationships),
            "embeddings_generated": len(embeddings),
        }

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

        for i, chunk in enumerate(chunks):
            chunk_id = f"{document_id}_chunk_{batch_offset + i}"
            chunk["chunk_id"] = chunk_id
            chunk["document_id"] = document_id

            extraction = extractions[i]
            entities = extraction.get("nodes", [])
            relationships = extraction.get("relationships", [])

            all_entities.extend(entities)
            all_relationships.extend(relationships)

            self.graph_store.add_chunk(chunk, chunk_id)

            self.graph_store.add_entities(entities, chunk_id)

        self.vector_store.add_chunks(chunks, embeddings)

        self.elasticsearch_store.add_chunks(chunks)

        self.graph_store.add_relationships(all_relationships)

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

                return await self.async_build_from_text_batch(
                    batch_text, document_id=document_id, batch_offset=batch_offset
                )

        tasks = [
            process_batch_with_offset(batch, idx)
            for idx, batch in enumerate(text_batches)
        ]
        results = await asyncio.gather(*tasks)

        total_chunks = sum(r["chunks_created"] for r in results)
        total_entities = sum(r["entities_extracted"] for r in results)
        total_relationships = sum(r["relationships_extracted"] for r in results)
        total_embeddings = sum(r["embeddings_generated"] for r in results)

        return {
            "document_id": document_id,
            "chunks_created": total_chunks,
            "entities_extracted": total_entities,
            "relationships_extracted": total_relationships,
            "embeddings_generated": total_embeddings,
            "batches_processed": len(text_batches),
        }

    def clear_all(self):
        log.info("Clearing all data...")
        self.vector_store.delete_collection()
        self.elasticsearch_store.delete_index()
        self.graph_store.clear_all()
        log.info("All data cleared")
