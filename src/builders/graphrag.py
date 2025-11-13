from typing import List, Dict, Any, Optional
import hashlib
import json
from ..core.embeddings import EmbeddingGenerator
from ..storage.qdrant_store import QdrantVectorStore
from ..storage.neo4j_store import Neo4jGraphStore
from ..storage.elasticsearch_store import ElasticsearchStore
from ..storage.redis_cache import RedisCache
from openai import OpenAI
from ..config.models import LLMModels


class GraphRAG:
    def __init__(
        self,
        openai_api_key: str,
        vector_store: QdrantVectorStore,
        graph_store: Neo4jGraphStore,
        elasticsearch_store: Optional[ElasticsearchStore] = None,
        llm_model: str = LLMModels.GPT_4_POINT_1.value,
        top_k_chunks: int = 5,
        max_depth: int = 2,
        use_hybrid_search: bool = True,
        vector_weight: float = 0.7,
        keyword_weight: float = 0.3,
        redis_cache: Optional[RedisCache] = None,
        cache_ttl: int = 3600,  # 1 hour for search results
    ):
        self.embedder = EmbeddingGenerator(openai_api_key, redis_cache=redis_cache)
        self.vector_store = vector_store
        self.graph_store = graph_store
        self.elasticsearch_store = elasticsearch_store
        self.llm_client = OpenAI(api_key=openai_api_key)
        self.llm_model = llm_model
        self.top_k_chunks = top_k_chunks
        self.max_depth = max_depth
        self.use_hybrid_search = use_hybrid_search and elasticsearch_store is not None
        self.vector_weight = vector_weight
        self.keyword_weight = keyword_weight
        self.cache = redis_cache
        self.cache_ttl = cache_ttl

    def _get_cache_key(self, query: str) -> str:
        """Generate cache key for search query."""
        cache_params = {
            "query": query,
            "top_k": self.top_k_chunks,
            "max_depth": self.max_depth,
            "use_hybrid": self.use_hybrid_search,
            "vector_weight": self.vector_weight,
            "keyword_weight": self.keyword_weight,
        }
        cache_string = json.dumps(cache_params, sort_keys=True)
        cache_hash = hashlib.sha256(cache_string.encode()).hexdigest()
        return f"search:{cache_hash}"

    def search(self, query: str) -> Dict[str, Any]:
        # Check cache first
        if self.cache:
            cache_key = self._get_cache_key(query)
            cached = self.cache.get(cache_key)
            if cached is not None:
                return cached

        if self.use_hybrid_search:
            similar_chunks = self._hybrid_search(query)
        else:
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

        result = {
            "answer": answer,
            "chunks_used": len(similar_chunks),
            "entities_found": len(entities),
            "context": context,
            "search_type": "hybrid" if self.use_hybrid_search else "vector",
        }

        # Cache the result
        if self.cache:
            cache_key = self._get_cache_key(query)
            self.cache.set(cache_key, result, ttl=self.cache_ttl, serialize=True)

        return result

    def _hybrid_search(self, query: str) -> List[Dict[str, Any]]:
        query_embedding = self.embedder.embed_text(query)

        vector_results = self.vector_store.search(
            query_embedding, top_k=self.top_k_chunks * 2
        )

        keyword_results = []
        if self.elasticsearch_store:
            keyword_results = self.elasticsearch_store.search(
                query, top_k=self.top_k_chunks * 2
            )

        combined_results = self._fuse_results(vector_results, keyword_results, query)

        return combined_results[: self.top_k_chunks]

    def _fuse_results(
        self,
        vector_results: List[Dict[str, Any]],
        keyword_results: List[Dict[str, Any]],
        query: str,
    ) -> List[Dict[str, Any]]:
        chunk_scores: Dict[str, Dict[str, Any]] = {}

        for chunk in vector_results:
            chunk_id = chunk["chunk_id"]
            normalized_score = self._normalize_score(chunk["score"], "vector")
            chunk_scores[chunk_id] = {
                **chunk,
                "vector_score": normalized_score,
                "keyword_score": 0.0,
                "combined_score": normalized_score * self.vector_weight,
            }

        for chunk in keyword_results:
            chunk_id = chunk["chunk_id"]
            normalized_score = self._normalize_score(chunk["score"], "keyword")

            if chunk_id in chunk_scores:
                chunk_scores[chunk_id]["keyword_score"] = normalized_score
                chunk_scores[chunk_id]["combined_score"] = (
                    chunk_scores[chunk_id]["vector_score"] * self.vector_weight
                    + normalized_score * self.keyword_weight
                )
            else:
                chunk_scores[chunk_id] = {
                    **chunk,
                    "vector_score": 0.0,
                    "keyword_score": normalized_score,
                    "combined_score": normalized_score * self.keyword_weight,
                }

        sorted_results = sorted(
            chunk_scores.values(),
            key=lambda x: x["combined_score"],
            reverse=True,
        )

        for result in sorted_results:
            result["score"] = result["combined_score"]

        return sorted_results

    def _normalize_score(self, score: float, score_type: str) -> float:
        if score_type == "vector":
            return max(0.0, min(1.0, (1.0 + score) / 2.0))
        else:
            return max(0.0, min(1.0, score / 10.0))

    def _build_context(
        self, chunks: List[Dict[str, Any]], entities: List[Dict[str, Any]]
    ) -> str:
        context_parts = []

        context_parts.append("=== Relevant Text Chunks ===")
        for i, chunk in enumerate[Dict[str, Any]](chunks, 1):
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
