from typing import List, Dict, Any, Optional
import neo4j
import warnings
import re
from ..core.logger import log


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

    async def _initialize(self):
        try:
            self.driver = neo4j.AsyncGraphDatabase.driver(
                self.uri, auth=(self.username, self.password)
            )
            await self._ensure_indexes()
            self._connected = True
        except Exception as e:
            warnings.warn(
                f"Failed to connect to Neo4j at {self.uri}: {e}\n"
                f"Graph storage will be disabled. Please check your Neo4j connection settings.",
                UserWarning,
            )
            self._connected = False

    async def _ensure_indexes(self):
        if not self.driver:
            return

        try:
            async with self.driver.session(database=self.database) as session:
                await session.run("""
                    CREATE INDEX entity_name_index IF NOT EXISTS
                    FOR (n:__Entity__)
                    ON (n.name)
                """)
        except Exception as e:
            warnings.warn(f"Failed to create Neo4j indexes: {e}", UserWarning)

    async def _check_connection(self):
        if not self._connected or not self.driver:
            return False
        try:
            async with self.driver.session(database=self.database) as session:
                await session.run("RETURN 1")
            return True
        except Exception:
            self._connected = False
            return False

    async def async_add_entities(
        self, entities: List[Dict[str, Any]], chunk_id: Optional[str] = None
    ):
        if not await self._check_connection() or not self.driver:
            return

        if not entities:
            return

        try:
            async with self.driver.session(database=self.database) as session:
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

                        await session.run(
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
                            await session.run(batch_query, **params)  # type: ignore
        except Exception as e:
            warnings.warn(f"Failed to add entities to Neo4j: {e}", UserWarning)

    async def async_add_relationships(self, relationships: List[Dict[str, Any]]):
        if not await self._check_connection() or not self.driver:
            return

        if not relationships:
            return

        try:
            async with self.driver.session(database=self.database) as session:
                for rel in relationships:
                    rel_type = rel.get("type", "RELATED_TO")
                    source_name = rel.get("source")
                    target_name = rel.get("target")
                    properties = rel.get("properties", {})

                    if not source_name or not target_name:
                        continue

                    sanitized_rel_type = sanitize_label(rel_type)
                    query = f"""
                        MATCH (s:__Entity__ {{name: $source}})
                        MATCH (t:__Entity__ {{name: $target}})
                        MERGE (s)-[r:{sanitized_rel_type}]->(t)
                        SET r += $properties
                    """

                    await session.run(
                        query,  # type: ignore
                        source=source_name,
                        target=target_name,
                        properties=properties,
                    )
        except Exception as e:
            warnings.warn(f"Failed to add relationships to Neo4j: {e}", UserWarning)

    async def async_add_chunks_batch(
        self, chunks: List[Dict[str, Any]], chunk_ids: List[str]
    ):
        if not await self._check_connection() or not self.driver:
            log.warning(
                "Neo4j connection not available - skipping chunk save. "
                "Make sure to call _initialize() after creating Neo4jGraphStore."
            )
            return

        if not chunks or not chunk_ids or len(chunks) != len(chunk_ids):
            warnings.warn(
                f"Invalid chunks/chunk_ids: chunks={len(chunks)}, chunk_ids={len(chunk_ids)}",
                UserWarning,
            )
            return

        try:
            async with self.driver.session(database=self.database) as session:
                batch_size = 100
                total_saved = 0
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
                        await session.run(batch_query, **params)  # type: ignore
                        total_saved += len(batch_chunks)

                if total_saved > 0:
                    log.debug(f"Saved {total_saved} chunks to Neo4j")
        except Exception as e:
            warnings.warn(f"Failed to add chunks batch to Neo4j: {e}", UserWarning)
            import traceback

            warnings.warn(traceback.format_exc(), UserWarning)

    async def async_add_chunk(self, chunk: Dict[str, Any], chunk_id: str):
        if not await self._check_connection() or not self.driver:
            return

        try:
            async with self.driver.session(database=self.database) as session:
                query = """
                    MERGE (c:Chunk {chunk_id: $chunk_id})
                    SET c.text = $text,
                        c.chunk_index = $chunk_index,
                        c.start_char = $start_char,
                        c.end_char = $end_char
                """

                await session.run(
                    query,  # type: ignore
                    chunk_id=chunk_id,
                    text=chunk.get("text", ""),
                    chunk_index=chunk.get("chunk_index", 0),
                    start_char=chunk.get("start_char", 0),
                    end_char=chunk.get("end_char", 0),
                )
        except Exception as e:
            warnings.warn(f"Failed to add chunk to Neo4j: {e}", UserWarning)

    async def get_entities_from_chunks(
        self, chunk_ids: List[str], max_depth: int = 2
    ) -> List[Dict[str, Any]]:
        if not await self._check_connection() or not self.driver:
            warnings.warn(
                "Neo4j connection not available for get_entities_from_chunks",
                UserWarning,
            )
            return []

        if not chunk_ids:
            return []

        try:
            async with self.driver.session(database=self.database) as session:
                check_query = """
                    MATCH (c:Chunk)
                    WHERE c.chunk_id IN $chunk_ids
                    RETURN c.chunk_id as chunk_id
                """
                check_result = await session.run(check_query, chunk_ids=chunk_ids)  # type: ignore
                found_chunks = []
                async for record in check_result:
                    found_chunks.append(record["chunk_id"])

                log.debug(
                    f"Found {len(found_chunks)} chunks in Neo4j out of {len(chunk_ids)} searched"
                )

                if not found_chunks:
                    sample_query = """
                        MATCH (c:Chunk)
                        RETURN c.chunk_id as chunk_id
                        LIMIT 5
                    """
                    sample_result = await session.run(sample_query)  # type: ignore
                    sample_chunks = []
                    async for record in sample_result:
                        sample_chunks.append(record["chunk_id"])

                    log.warning(
                        f"No chunks found in Neo4j for searched chunk_ids: {chunk_ids[:3]}... "
                        f"Sample of existing chunk_ids in Neo4j: {sample_chunks}"
                    )
                    return []

                entity_check_query = """
                    MATCH (c:Chunk)-[:CONTAINS_ENTITY]->(e:__Entity__)
                    WHERE c.chunk_id IN $chunk_ids
                    RETURN count(e) as entity_count
                """
                entity_check_result = await session.run(
                    entity_check_query, chunk_ids=found_chunks
                )  # type: ignore
                entity_count_record = await entity_check_result.single()
                entity_count = (
                    entity_count_record["entity_count"] if entity_count_record else 0
                )

                log.debug(
                    f"Found {entity_count} entities linked to the {len(found_chunks)} chunks"
                )

                if entity_count == 0:
                    log.warning(
                        "Chunks found in Neo4j but no entities are linked to them. "
                        "This suggests entities were not properly linked during upload."
                    )

                if max_depth == 1:
                    query = """
                        MATCH (c:Chunk)-[:CONTAINS_ENTITY]->(e:__Entity__)
                        WHERE c.chunk_id IN $chunk_ids
                        RETURN DISTINCT e, labels(e) as labels, 
                               ['CONTAINS_ENTITY'] as rel_types
                        LIMIT 100
                    """
                else:
                    query = f"""
                        MATCH path = (c:Chunk)-[:CONTAINS_ENTITY*1..{max_depth}]-(e:__Entity__)
                        WHERE c.chunk_id IN $chunk_ids
                        RETURN DISTINCT e, labels(e) as labels, 
                               [r IN relationships(path) | type(r)] as rel_types
                        LIMIT 100
                    """

                result = await session.run(query, chunk_ids=chunk_ids)  # type: ignore
                entities = []

                async for record in result:
                    entity_node = record["e"]
                    entities.append(
                        {
                            "name": entity_node.get("name"),
                            "labels": record["labels"],
                            "properties": dict(entity_node),
                            "relationship_types": record["rel_types"],
                        }
                    )

                log.debug(
                    f"Found {len(entities)} entities linked to {len(found_chunks)} chunks"
                )
                return entities
        except Exception as e:
            warnings.warn(f"Failed to get entities from Neo4j: {e}", UserWarning)
            import traceback

            warnings.warn(traceback.format_exc(), UserWarning)
            return []

    async def get_related_entities(
        self, entity_name: str, max_depth: int = 2
    ) -> List[Dict[str, Any]]:
        if not await self._check_connection() or not self.driver:
            return []

        try:
            async with self.driver.session(database=self.database) as session:
                query = f"""
                    MATCH path = (e1:__Entity__ {{name: $entity_name}})-[*1..{max_depth}]-(e2:__Entity__)
                    WHERE e1 <> e2
                    RETURN DISTINCT e2, labels(e2) as labels,
                           [r IN relationships(path) | type(r)] as rel_types
                    LIMIT 50
                """

                result = await session.run(query, entity_name=entity_name)  # type: ignore
                entities = []

                async for record in result:
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

    async def clear_all(self):
        if not await self._check_connection() or not self.driver:
            return

        try:
            async with self.driver.session(database=self.database) as session:
                await session.run("MATCH (n) DETACH DELETE n")
        except Exception as e:
            warnings.warn(f"Failed to clear Neo4j data: {e}", UserWarning)

    async def close(self):
        if self.driver:
            try:
                await self.driver.close()
            except Exception:
                pass
