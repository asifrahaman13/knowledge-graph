from typing import List, Dict, Any
from ..core.embeddings import EmbeddingGenerator
from ..storage.qdrant_store import QdrantVectorStore
from ..storage.neo4j_store import Neo4jGraphStore
from openai import OpenAI
from ..config.models import LLMModels


class GraphRAG:
    def __init__(
        self,
        openai_api_key: str,
        vector_store: QdrantVectorStore,
        graph_store: Neo4jGraphStore,
        llm_model: str = LLMModels.GPT_4_POINT_1.value,
        top_k_chunks: int = 5,
        max_depth: int = 2,
    ):
        self.embedder = EmbeddingGenerator(openai_api_key)
        self.vector_store = vector_store
        self.graph_store = graph_store
        self.llm_client = OpenAI(api_key=openai_api_key)
        self.llm_model = llm_model
        self.top_k_chunks = top_k_chunks
        self.max_depth = max_depth

    def search(self, query: str) -> Dict[str, Any]:
        query_embedding = self.embedder.embed_text(query)

        similar_chunks = self.vector_store.search(
            query_embedding, top_k=self.top_k_chunks
        )

        chunk_ids = [chunk["chunk_id"] for chunk in similar_chunks]
        entities = self.graph_store.get_entities_from_chunks(
            chunk_ids, max_depth=self.max_depth
        )

        context = self._build_context(similar_chunks, entities)

        answer = self._generate_answer(query, context)

        return {
            "answer": answer,
            "chunks_used": len(similar_chunks),
            "entities_found": len(entities),
            "context": context,
        }

    def _build_context(
        self, chunks: List[Dict[str, Any]], entities: List[Dict[str, Any]]
    ) -> str:
        context_parts = []

        context_parts.append("=== Relevant Text Chunks ===")
        for i, chunk in enumerate(chunks, 1):
            context_parts.append(f"\nChunk {i} (score: {chunk['score']:.3f}):")
            context_parts.append(chunk["text"])

        if entities:
            context_parts.append("\n\n=== Related Entities ===")
            for entity in entities[:10]:
                entity_info = f"\n{entity['name']} ({', '.join(entity['labels'])}):"
                if entity.get("properties"):
                    props = {
                        k: v
                        for k, v in entity["properties"].items()
                        if k not in ["name"] and not k.startswith("__")
                    }
                    if props:
                        entity_info += f" {props}"
                context_parts.append(entity_info)

        return "\n".join(context_parts)

    def _generate_answer(self, query: str, context: str) -> str:
        prompt = f"""Based on the following context, answer the question.

Context:
{context}

Question: {query}

Provide a comprehensive answer based on the context. If the context doesn't contain enough information, say so."""

        try:
            response = self.llm_client.chat.completions.create(
                model=self.llm_model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are a helpful assistant that answers questions based on provided context.",
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.7,
            )

            content = response.choices[0].message.content
            return content if content else "No answer generated"
        except Exception as e:
            return f"Error generating answer: {e}"
