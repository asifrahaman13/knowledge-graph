from typing import List, Dict, Any, Optional
from elasticsearch import Elasticsearch
from elasticsearch.helpers import bulk
import uuid
import warnings
from ..core.logger import log


class ElasticsearchStore:
    def __init__(
        self,
        index_name: str = "legal-docs",
        url: Optional[str] = None,
        api_key: Optional[str] = None,
    ):
        self.index_name = index_name
        self._connected = False

        try:
            if url:
                log.info(f"Connecting to Elasticsearch at: {url}")
                if api_key:
                    log.debug("Using API key authentication")
                    self.client = Elasticsearch(
                        url,
                        api_key=api_key,
                    )
                else:
                    log.warning(
                        "No API key provided, connecting without authentication"
                    )
                    self.client = Elasticsearch(url)
            else:
                log.info("Connecting to Elasticsearch at: http://localhost:9200")
                self.client = Elasticsearch(
                    hosts=["http://localhost:9200"],
                )

            ping_result = self.client.ping()
            if ping_result:
                self._connected = True
                self._ensure_index()
                log.info(
                    f"Elasticsearch connected successfully (Index: {self.index_name})"
                )
            else:
                log.warning(
                    "Elasticsearch connection failed: ping() returned False. Keyword search will be disabled."
                )
                warnings.warn(
                    "Elasticsearch connection failed: ping() returned False. Keyword search will be disabled.",
                    UserWarning,
                )
                self._connected = False
        except Exception as e:
            error_msg = str(e)
            log.error(f"Elasticsearch connection error: {error_msg}")
            warnings.warn(
                f"Elasticsearch initialization failed: {error_msg}. Keyword search will be disabled.",
                UserWarning,
            )
            self._connected = False
            self.client = None

    def _check_connection(self) -> bool:
        if not self._connected or not self.client:
            return False
        try:
            return self.client.ping()
        except Exception:
            self._connected = False
            return False

    def _ensure_index(self):
        if not self._check_connection() or not self.client:
            return

        try:
            if not self.client.indices.exists(index=self.index_name):
                mapping = {
                    "mappings": {
                        "properties": {
                            "chunk_id": {"type": "keyword"},
                            "text": {
                                "type": "text",
                                "analyzer": "standard",
                                "fields": {
                                    "keyword": {"type": "keyword"},
                                },
                            },
                            "chunk_index": {"type": "integer"},
                            "start_char": {"type": "integer"},
                            "end_char": {"type": "integer"},
                            "document_id": {"type": "keyword"},
                        }
                    }
                }
                self.client.indices.create(index=self.index_name, body=mapping)
        except Exception as e:
            warnings.warn(f"Failed to create Elasticsearch index: {e}", UserWarning)

    def add_chunks(self, chunks: List[Dict[str, Any]]):
        if not self._check_connection() or not self.client:
            log.warning(
                f"Skipping Elasticsearch upload: Not connected (chunks: {len(chunks)})"
            )
            return

        try:
            actions = []
            for chunk in chunks:
                doc = {
                    "_index": self.index_name,
                    "_id": chunk.get("chunk_id", str(uuid.uuid4())),
                    "_source": {
                        "chunk_id": chunk.get("chunk_id", str(uuid.uuid4())),
                        "text": chunk.get("text", ""),
                        "chunk_index": chunk.get("chunk_index", 0),
                        "start_char": chunk.get("start_char", 0),
                        "end_char": chunk.get("end_char", 0),
                        "document_id": chunk.get("document_id", "default"),
                    },
                }
                actions.append(doc)

            if actions:
                bulk(self.client, actions)
                self.client.indices.refresh(index=self.index_name)
                log.info(
                    f"Uploaded {len(actions)} chunks to Elasticsearch index '{self.index_name}'"
                )
        except Exception as e:
            error_msg = str(e)
            log.error(f"Failed to add chunks to Elasticsearch: {error_msg}")
            warnings.warn(
                f"Failed to add chunks to Elasticsearch: {error_msg}", UserWarning
            )

    def search(
        self, query: str, top_k: int = 5, boost: float = 1.0
    ) -> List[Dict[str, Any]]:
        if not self._check_connection() or not self.client:
            return []

        try:
            search_body = {
                "query": {
                    "multi_match": {
                        "query": query,
                        "fields": ["text^2", "text.keyword"],
                        "type": "best_fields",
                        "fuzziness": "AUTO",
                    }
                },
                "size": top_k,
            }

            response = self.client.search(index=self.index_name, body=search_body)

            chunks = []
            for hit in response["hits"]["hits"]:
                source = hit["_source"]
                score = hit["_score"] * boost
                chunks.append(
                    {
                        "chunk_id": source.get("chunk_id", hit["_id"]),
                        "text": source.get("text", ""),
                        "score": score,
                        "chunk_index": source.get("chunk_index", 0),
                        "start_char": source.get("start_char", 0),
                        "end_char": source.get("end_char", 0),
                        "document_id": source.get("document_id", "default"),
                    }
                )

            return chunks
        except Exception as e:
            warnings.warn(f"Elasticsearch search failed: {e}", UserWarning)
            return []

    def delete_index(self):
        if not self._check_connection() or not self.client:
            return

        try:
            if self.client.indices.exists(index=self.index_name):
                self.client.indices.delete(index=self.index_name)
        except Exception as e:
            warnings.warn(f"Failed to delete Elasticsearch index: {e}", UserWarning)
