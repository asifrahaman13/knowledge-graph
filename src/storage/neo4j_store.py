from typing import List, Dict, Any, Optional
import neo4j
import warnings


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

        try:
            with self.driver.session(database=self.database) as session:
                for entity in entities:
                    labels = entity.get("labels", ["Entity"])
                    properties = entity.get("properties", {})

                    if "name" not in properties:
                        continue

                    label_str = ":".join(labels)
                    query = f"""
                        MERGE (e:__Entity__:{label_str} {{name: $name}})
                        SET e += $properties
                        RETURN elementId(e) as node_id
                    """

                    result = session.run(
                        query,  # type: ignore
                        name=properties["name"],
                        properties=properties,
                    )
                    single_result = result.single()
                    node_id = single_result["node_id"] if single_result else None

                    if chunk_id and node_id:
                        session.run(  # type: ignore
                            """
                            MATCH (c:Chunk {chunk_id: $chunk_id})
                            MATCH (e) WHERE elementId(e) = $node_id
                            MERGE (c)-[:CONTAINS_ENTITY]->(e)
                        """,
                            chunk_id=chunk_id,
                            node_id=node_id,
                        )
        except Exception as e:
            warnings.warn(f"Failed to add entities to Neo4j: {e}", UserWarning)

    def add_relationships(self, relationships: List[Dict[str, Any]]):
        if not self._check_connection() or not self.driver:
            return

        try:
            with self.driver.session(database=self.database) as session:
                for rel in relationships:
                    rel_type = rel.get("type", "RELATED_TO")
                    source_name = rel.get("source")
                    target_name = rel.get("target")
                    properties = rel.get("properties", {})

                    if not source_name or not target_name:
                        continue

                    query = f"""
                        MATCH (source:__Entity__ {{name: $source_name}})
                        MATCH (target:__Entity__ {{name: $target_name}})
                        MERGE (source)-[r:{rel_type}]->(target)
                        SET r += $properties
                    """

                    session.run(
                        query,  # type: ignore
                        source_name=source_name,
                        target_name=target_name,
                        properties=properties,
                    )
        except Exception as e:
            warnings.warn(f"Failed to add relationships to Neo4j: {e}", UserWarning)

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
