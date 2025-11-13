from typing import List, Dict, Any, Optional
import neo4j
import warnings
import re


def sanitize_label(label: str) -> str:
    if not label:
        return "Entity"

    sanitized = re.sub(r"[^a-zA-Z0-9_]", "_", label)
    if sanitized and not sanitized[0].isalpha() and sanitized[0] != "_":
        sanitized = "_" + sanitized

    return sanitized if sanitized else "Entity"


class Neo4jGraphStore:
    def __init__(self, uri: str, username: str, password: str, database: str = "neo4j"):
        self.uri = uri
        self.username = username
        self.password = password
        self.database = database
        self.driver = None
        self._connected = False

        try:
            self.driver = neo4j.GraphDatabase.driver(uri, auth=(username, password))
            self._ensure_indexes()
            self._connected = True
        except Exception as e:
            warnings.warn(
                f"Failed to connect to Neo4j at {uri}: {e}\n"
                f"Graph storage will be disabled. Please check your Neo4j connection settings.",
                UserWarning,
            )
            self._connected = False

    def _ensure_indexes(self):
        if not self.driver:
            return

        try:
            with self.driver.session(database=self.database) as session:
                session.run("""
                    CREATE INDEX entity_name_index IF NOT EXISTS
                    FOR (n:__Entity__)
                    ON (n.name)
                """)
        except Exception as e:
            warnings.warn(f"Failed to create Neo4j indexes: {e}", UserWarning)

    def _check_connection(self):
        if not self._connected or not self.driver:
            return False
        try:
            with self.driver.session(database=self.database) as session:
                session.run("RETURN 1")
            return True
        except Exception:
            self._connected = False
            return False

    def _get_session(self):
        if not self._check_connection() or not self.driver:
            return None
        return self.driver.session(database=self.database)

    def add_entities(
        self, entities: List[Dict[str, Any]], chunk_id: Optional[str] = None
    ):
        if not self._check_connection() or not self.driver:
            return

        if not entities:
            return

        try:
            with self.driver.session(database=self.database) as session:
                if chunk_id:
                    for entity in entities:
                        labels = entity.get("labels", ["Entity"])
                        properties = entity.get("properties", {})

                        if "name" not in properties:
                            continue

                        sanitized_labels = [sanitize_label(label) for label in labels]
                        label_str = ":".join(sanitized_labels)
                        query = f"""
                            MERGE (e:__Entity__:{label_str} {{name: $name}})
                            SET e += $properties
                            WITH e, elementId(e) as node_id
                            MATCH (c:Chunk {{chunk_id: $chunk_id}})
                            MERGE (c)-[:CONTAINS_ENTITY]->(e)
                            RETURN node_id
                        """

                        session.run(
                            query,  # type: ignore
                            name=properties["name"],
                            properties=properties,
                            chunk_id=chunk_id,
                        )
                else:
                    batch_size = 100
                    for i in range(0, len(entities), batch_size):
                        batch = entities[i : i + batch_size]
                        query_parts = []
                        params = {}

                        for idx, entity in enumerate(batch):
                            labels = entity.get("labels", ["Entity"])
                            properties = entity.get("properties", {})

                            if "name" not in properties:
                                continue

                            sanitized_labels = [
                                sanitize_label(label) for label in labels
                            ]
                            label_str = ":".join(sanitized_labels)
                            name_key = f"name_{idx}"
                            props_key = f"props_{idx}"

                            query_parts.append(f"""
                                MERGE (e{idx}:__Entity__:{label_str} {{name: ${name_key}}})
                                SET e{idx} += ${props_key}
                            """)
                            params[name_key] = properties["name"]
                            params[props_key] = properties

                        if query_parts:
                            batch_query = " ".join(query_parts)
                            session.run(batch_query, **params)  # type: ignore
        except Exception as e:
            warnings.warn(f"Failed to add entities to Neo4j: {e}", UserWarning)

    def add_relationships(self, relationships: List[Dict[str, Any]]):
        if not self._check_connection() or not self.driver:
            return

        if not relationships:
            return

        try:
            with self.driver.session(database=self.database) as session:
                batch_size = 50
                for i in range(0, len(relationships), batch_size):
                    batch = relationships[i : i + batch_size]
                    query_parts = []
                    params = {}

                    for idx, rel in enumerate(batch):
                        rel_type = rel.get("type", "RELATED_TO")
                        source_name = rel.get("source")
                        target_name = rel.get("target")
                        properties = rel.get("properties", {})

                        if not source_name or not target_name:
                            continue

                        sanitized_rel_type = sanitize_label(rel_type)
                        source_key = f"source_{idx}"
                        target_key = f"target_{idx}"
                        props_key = f"props_{idx}"

                        query_parts.append(f"""
                            MATCH (s{idx}:__Entity__ {{name: ${source_key}}})
                            MATCH (t{idx}:__Entity__ {{name: ${target_key}}})
                            MERGE (s{idx})-[r{idx}:{sanitized_rel_type}]->(t{idx})
                            SET r{idx} += ${props_key}
                        """)
                        params[source_key] = source_name
                        params[target_key] = target_name
                        params[props_key] = properties

                    if query_parts:
                        batch_query = " ".join(query_parts)
                        session.run(batch_query, **params)  # type: ignore
        except Exception as e:
            warnings.warn(f"Failed to add relationships to Neo4j: {e}", UserWarning)

    def add_chunks_batch(self, chunks: List[Dict[str, Any]], chunk_ids: List[str]):
        """Add multiple chunks in a single batch operation."""
        if not self._check_connection() or not self.driver:
            return

        if not chunks or not chunk_ids or len(chunks) != len(chunk_ids):
            return

        try:
            with self.driver.session(database=self.database) as session:
                batch_size = 100
                for i in range(0, len(chunks), batch_size):
                    batch_chunks = chunks[i : i + batch_size]
                    batch_ids = chunk_ids[i : i + batch_size]

                    query_parts = []
                    params = {}

                    for idx, (chunk, chunk_id) in enumerate(
                        zip(batch_chunks, batch_ids)
                    ):
                        cid_key = f"chunk_id_{idx}"
                        text_key = f"text_{idx}"
                        idx_key = f"chunk_index_{idx}"
                        start_key = f"start_char_{idx}"
                        end_key = f"end_char_{idx}"

                        query_parts.append(f"""
                            MERGE (c{idx}:Chunk {{chunk_id: ${cid_key}}})
                            SET c{idx}.text = ${text_key},
                                c{idx}.chunk_index = ${idx_key},
                                c{idx}.start_char = ${start_key},
                                c{idx}.end_char = ${end_key}
                        """)
                        params[cid_key] = chunk_id
                        params[text_key] = chunk.get("text", "")
                        params[idx_key] = chunk.get("chunk_index", 0)
                        params[start_key] = chunk.get("start_char", 0)
                        params[end_key] = chunk.get("end_char", 0)

                    if query_parts:
                        batch_query = " ".join(query_parts)
                        session.run(batch_query, **params)  # type: ignore
        except Exception as e:
            warnings.warn(f"Failed to add chunks batch to Neo4j: {e}", UserWarning)

    def add_chunk(self, chunk: Dict[str, Any], chunk_id: str):
        if not self._check_connection() or not self.driver:
            return

        try:
            with self.driver.session(database=self.database) as session:
                query = """
                    MERGE (c:Chunk {chunk_id: $chunk_id})
                    SET c.text = $text,
                        c.chunk_index = $chunk_index,
                        c.start_char = $start_char,
                        c.end_char = $end_char
                """

                session.run(
                    query,  # type: ignore
                    chunk_id=chunk_id,
                    text=chunk.get("text", ""),
                    chunk_index=chunk.get("chunk_index", 0),
                    start_char=chunk.get("start_char", 0),
                    end_char=chunk.get("end_char", 0),
                )
        except Exception as e:
            warnings.warn(f"Failed to add chunk to Neo4j: {e}", UserWarning)

    def get_entities_from_chunks(
        self, chunk_ids: List[str], max_depth: int = 2
    ) -> List[Dict[str, Any]]:
        if not self._check_connection() or not self.driver:
            return []

        try:
            with self.driver.session(database=self.database) as session:
                query = f"""
                    MATCH path = (c:Chunk)-[:CONTAINS_ENTITY*1..{max_depth}]-(e:__Entity__)
                    WHERE c.chunk_id IN $chunk_ids
                    RETURN DISTINCT e, labels(e) as labels, 
                           [r IN relationships(path) | type(r)] as rel_types
                    LIMIT 100
                """

                result = session.run(query, chunk_ids=chunk_ids)  # type: ignore
                entities = []

                for record in result:
                    entity_node = record["e"]
                    entities.append(
                        {
                            "name": entity_node.get("name"),
                            "labels": record["labels"],
                            "properties": dict(entity_node),
                            "relationship_types": record["rel_types"],
                        }
                    )

                return entities
        except Exception as e:
            warnings.warn(f"Failed to get entities from Neo4j: {e}", UserWarning)
            return []

    def get_related_entities(
        self, entity_name: str, max_depth: int = 2
    ) -> List[Dict[str, Any]]:
        if not self._check_connection() or not self.driver:
            return []

        try:
            with self.driver.session(database=self.database) as session:
                query = f"""
                    MATCH path = (e1:__Entity__ {{name: $entity_name}})-[*1..{max_depth}]-(e2:__Entity__)
                    WHERE e1 <> e2
                    RETURN DISTINCT e2, labels(e2) as labels,
                           [r IN relationships(path) | type(r)] as rel_types
                    LIMIT 50
                """

                result = session.run(query, entity_name=entity_name)  # type: ignore
                entities = []

                for record in result:
                    entity_node = record["e2"]
                    entities.append(
                        {
                            "name": entity_node.get("name"),
                            "labels": record["labels"],
                            "properties": dict(entity_node),
                            "relationship_types": record["rel_types"],
                        }
                    )

                return entities
        except Exception as e:
            warnings.warn(
                f"Failed to get related entities from Neo4j: {e}", UserWarning
            )
            return []

    def clear_all(self):
        if not self._check_connection() or not self.driver:
            return

        try:
            with self.driver.session(database=self.database) as session:
                session.run("MATCH (n) DETACH DELETE n")
        except Exception as e:
            warnings.warn(f"Failed to clear Neo4j data: {e}", UserWarning)

    def close(self):
        if self.driver:
            try:
                self.driver.close()
            except Exception:
                pass
