"""
Knowledge Graph Builder
Main pipeline that builds knowledge graph from text
"""

from typing import Dict, Any, Optional, List
import uuid
import asyncio
from text_chunker import TextChunker
from embeddings import EmbeddingGenerator
from entity_extractor import EntityRelationshipExtractor
from qdrant_store import QdrantVectorStore
from neo4j_store import Neo4jGraphStore
from models import LLMModels, EmbeddingModels


class KnowledgeGraphBuilder:
    """Builds knowledge graph from text using Qdrant and Neo4j"""

    def __init__(
        self,
        openai_api_key: str,
        neo4j_uri: str,
        neo4j_username: str,
        neo4j_password: str,
        qdrant_url: Optional[str] = None,
        qdrant_api_key: Optional[str] = None,
        chunk_size: int = 500,
        chunk_overlap: int = 100,
        embedding_model: str = EmbeddingModels.TEXT_EMBEDDING_3_LARGE.value,
        llm_model: str = LLMModels.GPT_4_POINT_1.value,
    ):
        """
        Initialize knowledge graph builder

        Args:
            openai_api_key: OpenAI API key
            neo4j_uri: Neo4j database URI
            neo4j_username: Neo4j username
            neo4j_password: Neo4j password
            qdrant_url: Qdrant server URL (None for local)
            qdrant_api_key: Qdrant API key (if using cloud)
            chunk_size: Size of text chunks
            chunk_overlap: Overlap between chunks
            embedding_model: Embedding model name
            llm_model: LLM model name
        """
        # Initialize components
        self.chunker = TextChunker(chunk_size=chunk_size, chunk_overlap=chunk_overlap)
        self.embedder = EmbeddingGenerator(openai_api_key, embedding_model)
        self.extractor = EntityRelationshipExtractor(openai_api_key, llm_model)

        # Initialize stores
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

    def build_from_text(
        self, text: str, document_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Build knowledge graph from text

        Args:
            text: Input text
            document_id: Optional document ID

        Returns:
            Dictionary with build statistics
        """
        if not document_id:
            document_id = str(uuid.uuid4())

        # Step 1: Chunk text
        print("Step 1: Chunking text...")
        chunks = self.chunker.chunk_text(text)
        print(f"Created {len(chunks)} chunks")

        # Step 2: Generate embeddings
        print("Step 2: Generating embeddings...")
        chunk_texts = [chunk["text"] for chunk in chunks]
        embeddings = self.embedder.embed_batch(chunk_texts)
        print(f"Generated {len(embeddings)} embeddings")

        # Step 3: Extract entities and relationships
        print("Step 3: Extracting entities and relationships...")
        all_entities = []
        all_relationships = []

        for i, chunk in enumerate(chunks):
            chunk_id = f"{document_id}_chunk_{i}"
            chunk["chunk_id"] = chunk_id
            chunk["document_id"] = document_id

            # Extract from chunk
            extraction = self.extractor.extract(chunk["text"])
            entities = extraction.get("nodes", [])
            relationships = extraction.get("relationships", [])

            all_entities.extend(entities)
            all_relationships.extend(relationships)

            # Store chunk in Neo4j
            self.graph_store.add_chunk(chunk, chunk_id)

            # Store entities linked to chunk
            self.graph_store.add_entities(entities, chunk_id)

        print(
            f"Extracted {len(all_entities)} entities and {len(all_relationships)} relationships"
        )

        # Step 4: Store chunks in Qdrant
        print("Step 4: Storing chunks in Qdrant...")
        self.vector_store.add_chunks(chunks, embeddings)
        print("Chunks stored in Qdrant")

        # Step 5: Store relationships in Neo4j
        print("Step 5: Storing relationships in Neo4j...")
        self.graph_store.add_relationships(all_relationships)
        print("Relationships stored in Neo4j")

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
        """
        Build knowledge graph from text batch asynchronously

        Args:
            text: Input text for this batch
            document_id: Document ID (should be same across batches)
            batch_offset: Offset for chunk numbering (for multi-batch processing)

        Returns:
            Dictionary with build statistics
        """
        if not document_id:
            document_id = str(uuid.uuid4())

        # Step 1: Chunk text
        chunks = self.chunker.chunk_text(text)

        if not chunks:
            return {
                "document_id": document_id,
                "chunks_created": 0,
                "entities_extracted": 0,
                "relationships_extracted": 0,
                "embeddings_generated": 0,
            }

        # Step 2 & 3: Generate embeddings and extract entities in parallel
        chunk_texts = [chunk["text"] for chunk in chunks]

        # Run embeddings and extractions in parallel
        embeddings_task = self.embedder.async_embed_batch(chunk_texts)
        extractions_task = self.extractor.async_extract_batch(chunk_texts)

        embeddings, extractions = await asyncio.gather(
            embeddings_task, extractions_task
        )

        # Step 4: Process chunks, entities, and relationships
        all_entities = []
        all_relationships = []

        for i, chunk in enumerate(chunks):
            chunk_id = f"{document_id}_chunk_{batch_offset + i}"
            chunk["chunk_id"] = chunk_id
            chunk["document_id"] = document_id

            # Get extraction results
            extraction = extractions[i]
            entities = extraction.get("nodes", [])
            relationships = extraction.get("relationships", [])

            all_entities.extend(entities)
            all_relationships.extend(relationships)

            # Store chunk in Neo4j
            self.graph_store.add_chunk(chunk, chunk_id)

            # Store entities linked to chunk
            self.graph_store.add_entities(entities, chunk_id)

        # Step 5: Store chunks in Qdrant
        self.vector_store.add_chunks(chunks, embeddings)

        # Step 6: Store relationships in Neo4j
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
        """
        Build knowledge graph from multiple text batches in parallel

        Args:
            text_batches: List of text batches to process
            document_id: Optional document ID (same across all batches)
            max_concurrent_batches: Maximum number of batches to process concurrently

        Returns:
            Dictionary with aggregated build statistics
        """
        if not document_id:
            document_id = str(uuid.uuid4())

        semaphore = asyncio.Semaphore(max_concurrent_batches)

        async def process_batch_with_offset(
            batch_text: str, batch_idx: int
        ) -> Dict[str, Any]:
            async with semaphore:
                # Use batch index as offset to ensure unique chunk IDs
                # Each batch gets a large offset range to avoid collisions
                # Using 10000 per batch to ensure no overlap
                batch_offset = batch_idx * 10000

                return await self.async_build_from_text_batch(
                    batch_text, document_id=document_id, batch_offset=batch_offset
                )

        # Process all batches in parallel
        tasks = [
            process_batch_with_offset(batch, idx)
            for idx, batch in enumerate(text_batches)
        ]
        results = await asyncio.gather(*tasks)

        # Aggregate statistics
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
        """Clear all data from both stores"""
        print("Clearing all data...")
        self.vector_store.delete_collection()
        self.graph_store.clear_all()
        print("All data cleared")
