"""
GraphRAG Implementation
Retrieves and combines information from vector store and graph store
"""

from typing import List, Dict, Any
from embeddings import EmbeddingGenerator
from qdrant_store import QdrantVectorStore
from neo4j_store import Neo4jGraphStore
from openai import OpenAI


class GraphRAG:
    """GraphRAG implementation for intelligent search"""
    
    def __init__(self,
                 openai_api_key: str,
                 vector_store: QdrantVectorStore,
                 graph_store: Neo4jGraphStore,
                 llm_model: str = "gpt-4o",
                 top_k_chunks: int = 5,
                 max_depth: int = 2):
        """
        Initialize GraphRAG
        
        Args:
            openai_api_key: OpenAI API key
            vector_store: Qdrant vector store instance
            graph_store: Neo4j graph store instance
            llm_model: LLM model for answer generation
            top_k_chunks: Number of chunks to retrieve
            max_depth: Maximum graph traversal depth
        """
        self.embedder = EmbeddingGenerator(openai_api_key)
        self.vector_store = vector_store
        self.graph_store = graph_store
        self.llm_client = OpenAI(api_key=openai_api_key)
        self.llm_model = llm_model
        self.top_k_chunks = top_k_chunks
        self.max_depth = max_depth
    
    def search(self, query: str) -> Dict[str, Any]:
        """
        Search and generate answer using GraphRAG
        
        Args:
            query: User query
            
        Returns:
            Dictionary with answer and context
        """
        # Step 1: Embed query
        query_embedding = self.embedder.embed_text(query)
        
        # Step 2: Vector search for relevant chunks
        similar_chunks = self.vector_store.search(query_embedding, top_k=self.top_k_chunks)
        
        # Step 3: Get entities from relevant chunks
        chunk_ids = [chunk["chunk_id"] for chunk in similar_chunks]
        entities = self.graph_store.get_entities_from_chunks(chunk_ids, max_depth=self.max_depth)
        
        # Step 4: Build context
        context = self._build_context(similar_chunks, entities)
        
        # Step 5: Generate answer
        answer = self._generate_answer(query, context)
        
        return {
            "answer": answer,
            "chunks_used": len(similar_chunks),
            "entities_found": len(entities),
            "context": context
        }
    
    def _build_context(self, chunks: List[Dict[str, Any]], entities: List[Dict[str, Any]]) -> str:
        """Build context string from chunks and entities"""
        context_parts = []
        
        # Add chunk text
        context_parts.append("=== Relevant Text Chunks ===")
        for i, chunk in enumerate(chunks, 1):
            context_parts.append(f"\nChunk {i} (score: {chunk['score']:.3f}):")
            context_parts.append(chunk["text"])
        
        # Add entity information
        if entities:
            context_parts.append("\n\n=== Related Entities ===")
            for entity in entities[:10]:  # Limit to top 10 entities
                entity_info = f"\n{entity['name']} ({', '.join(entity['labels'])}):"
                if entity.get("properties"):
                    props = {k: v for k, v in entity["properties"].items() 
                            if k not in ["name"] and not k.startswith("__")}
                    if props:
                        entity_info += f" {props}"
                context_parts.append(entity_info)
        
        return "\n".join(context_parts)
    
    def _generate_answer(self, query: str, context: str) -> str:
        """Generate answer using LLM"""
        prompt = f"""Based on the following context, answer the question.

Context:
{context}

Question: {query}

Provide a comprehensive answer based on the context. If the context doesn't contain enough information, say so."""

        try:
            response = self.llm_client.chat.completions.create(
                model=self.llm_model,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that answers questions based on provided context."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.7
            )
            
            content = response.choices[0].message.content
            return content if content else "No answer generated"
        except Exception as e:
            return f"Error generating answer: {e}"

