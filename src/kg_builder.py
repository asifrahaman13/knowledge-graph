"""
Knowledge Graph Builder
Main pipeline that builds knowledge graph from text
"""

from typing import Dict, Any, Optional
import uuid
from text_chunker import TextChunker
from embeddings import EmbeddingGenerator
from entity_extractor import EntityRelationshipExtractor
from qdrant_store import QdrantVectorStore
from neo4j_store import Neo4jGraphStore


class KnowledgeGraphBuilder:
    """Builds knowledge graph from text using Qdrant and Neo4j"""
    
    def __init__(self,
                 openai_api_key: str,
                 neo4j_uri: str,
                 neo4j_username: str,
                 neo4j_password: str,
                 qdrant_url: Optional[str] = None,
                 qdrant_api_key: Optional[str] = None,
                 chunk_size: int = 500,
                 chunk_overlap: int = 100,
                 embedding_model: str = "text-embedding-3-small",
                 llm_model: str = "gpt-4o-mini"):
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
            dimension=dimension
        )
        self.graph_store = Neo4jGraphStore(
            uri=neo4j_uri,
            username=neo4j_username,
            password=neo4j_password
        )
    
    def build_from_text(self, text: str, document_id: Optional[str] = None) -> Dict[str, Any]:
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
        
        print(f"Extracted {len(all_entities)} entities and {len(all_relationships)} relationships")
        
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
            "embeddings_generated": len(embeddings)
        }
    
    def clear_all(self):
        """Clear all data from both stores"""
        print("Clearing all data...")
        self.vector_store.delete_collection()
        self.graph_store.clear_all()
        print("All data cleared")

