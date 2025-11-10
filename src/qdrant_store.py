"""
Qdrant Vector Store Integration
Stores and retrieves text chunks with embeddings
"""

from typing import List, Dict, Any, Optional
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct
import uuid


class QdrantVectorStore:
    """Manages vector storage in Qdrant"""
    
    def __init__(self, collection_name: str = "text_chunks", 
                 url: Optional[str] = None,
                 api_key: Optional[str] = None,
                 dimension: int = 1536):
        """
        Initialize Qdrant vector store
        
        Args:
            collection_name: Name of the Qdrant collection
            url: Qdrant server URL (None for local)
            api_key: Qdrant API key (if using cloud)
            dimension: Dimension of embedding vectors
        """
        self.collection_name = collection_name
        self.dimension = dimension
        
        # Initialize Qdrant client
        if url:
            self.client = QdrantClient(url=url, api_key=api_key)
        else:
            # Local Qdrant - use local path or in-memory
            try:
                # Try to use local path
                self.client = QdrantClient(path="./qdrant_db")
            except:
                # Fallback to in-memory
                self.client = QdrantClient(location=":memory:")
        
        # Create collection if it doesn't exist
        self._ensure_collection()
    
    def _ensure_collection(self):
        """Create collection if it doesn't exist"""
        try:
            collections = self.client.get_collections()
            collection_names = [col.name for col in collections.collections]
            
            if self.collection_name not in collection_names:
                self.client.create_collection(
                    collection_name=self.collection_name,
                    vectors_config=VectorParams(
                        size=self.dimension,
                        distance=Distance.COSINE
                    )
                )
        except Exception as e:
            # Collection might already exist
            pass
    
    def add_chunks(self, chunks: List[Dict[str, Any]], embeddings: List[List[float]]):
        """
        Add text chunks with embeddings to Qdrant
        
        Args:
            chunks: List of chunk dictionaries with text and metadata
            embeddings: List of embedding vectors
        """
        if len(chunks) != len(embeddings):
            raise ValueError("Number of chunks must match number of embeddings")
        
        points = []
        for i, (chunk, embedding) in enumerate(zip(chunks, embeddings)):
            # Qdrant requires point ID to be UUID (string) or integer
            # Generate a proper UUID for the point ID
            point_id = str(uuid.uuid4())
            original_chunk_id = chunk.get("chunk_id", point_id)
            
            point = PointStruct(
                id=point_id,
                vector=embedding,
                payload={
                    "chunk_id": original_chunk_id,  # Store original chunk_id in payload
                    "text": chunk["text"],
                    "chunk_index": chunk.get("chunk_index", i),
                    "start_char": chunk.get("start_char", 0),
                    "end_char": chunk.get("end_char", 0),
                    "document_id": chunk.get("document_id", "default")
                }
            )
            points.append(point)
        
        self.client.upsert(
            collection_name=self.collection_name,
            points=points
        )
    
    def search(self, query_embedding: List[float], top_k: int = 5) -> List[Dict[str, Any]]:
        """
        Search for similar chunks
        
        Args:
            query_embedding: Query embedding vector
            top_k: Number of results to return
            
        Returns:
            List of similar chunks with scores
        """
        results = self.client.search(
            collection_name=self.collection_name,
            query_vector=query_embedding,
            limit=top_k
        )
        
        chunks = []
        for result in results:
            payload = result.payload or {}
            chunks.append({
                "chunk_id": payload.get("chunk_id", str(result.id)),  # Use original chunk_id from payload
                "point_id": str(result.id),  # Also include Qdrant point ID
                "text": payload.get("text", ""),
                "score": result.score,
                "chunk_index": payload.get("chunk_index", 0),
                "start_char": payload.get("start_char", 0),
                "end_char": payload.get("end_char", 0),
                "document_id": payload.get("document_id", "default")
            })
        
        return chunks
    
    def delete_collection(self):
        """Delete the collection"""
        try:
            self.client.delete_collection(self.collection_name)
        except Exception as e:
            pass

