"""
Neo4j Graph Store Integration
Stores entities and relationships in Neo4j
"""

from typing import List, Dict, Any, Optional
import neo4j


class Neo4jGraphStore:
    """Manages graph storage in Neo4j"""
    
    def __init__(self, uri: str, username: str, password: str, database: str = "neo4j"):
        """
        Initialize Neo4j graph store
        
        Args:
            uri: Neo4j database URI
            username: Neo4j username
            password: Neo4j password
            database: Database name
        """
        self.driver = neo4j.GraphDatabase.driver(uri, auth=(username, password))
        self.database = database
        self._ensure_indexes()
    
    def _ensure_indexes(self):
        """Create indexes for better performance"""
        with self.driver.session(database=self.database) as session:
            # Create index on entity name for faster lookups
            session.run("""
                CREATE INDEX entity_name_index IF NOT EXISTS
                FOR (n:__Entity__)
                ON (n.name)
            """)
    
    def add_entities(self, entities: List[Dict[str, Any]], chunk_id: Optional[str] = None):
        """
        Add entities to Neo4j
        
        Args:
            entities: List of entity dictionaries
            chunk_id: Optional chunk ID to link entities to
        """
        with self.driver.session(database=self.database) as session:
            for entity in entities:
                labels = entity.get("labels", ["Entity"])
                properties = entity.get("properties", {})
                
                # Ensure name exists
                if "name" not in properties:
                    continue
                
                # Create entity node
                label_str = ":".join(labels)
                query = f"""
                    MERGE (e:__Entity__:{label_str} {{name: $name}})
                    SET e += $properties
                    RETURN id(e) as node_id
                """
                
                result = session.run(query, name=properties["name"], properties=properties)
                node_id = result.single()["node_id"] if result.peek() else None
                
                # Link to chunk if provided
                if chunk_id and node_id:
                    session.run("""
                        MATCH (c:Chunk {chunk_id: $chunk_id})
                        MATCH (e) WHERE id(e) = $node_id
                        MERGE (c)-[:CONTAINS_ENTITY]->(e)
                    """, chunk_id=chunk_id, node_id=node_id)
    
    def add_relationships(self, relationships: List[Dict[str, Any]]):
        """
        Add relationships to Neo4j
        
        Args:
            relationships: List of relationship dictionaries
        """
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
                
                session.run(query, 
                           source_name=source_name,
                           target_name=target_name,
                           properties=properties)
    
    def add_chunk(self, chunk: Dict[str, Any], chunk_id: str):
        """
        Add chunk node to Neo4j
        
        Args:
            chunk: Chunk dictionary
            chunk_id: Unique chunk ID
        """
        with self.driver.session(database=self.database) as session:
            query = """
                MERGE (c:Chunk {chunk_id: $chunk_id})
                SET c.text = $text,
                    c.chunk_index = $chunk_index,
                    c.start_char = $start_char,
                    c.end_char = $end_char
            """
            
            session.run(query,
                       chunk_id=chunk_id,
                       text=chunk.get("text", ""),
                       chunk_index=chunk.get("chunk_index", 0),
                       start_char=chunk.get("start_char", 0),
                       end_char=chunk.get("end_char", 0))
    
    def get_entities_from_chunks(self, chunk_ids: List[str], max_depth: int = 2) -> List[Dict[str, Any]]:
        """
        Get entities connected to chunks, with graph traversal
        
        Args:
            chunk_ids: List of chunk IDs
            max_depth: Maximum depth to traverse from chunks
            
        Returns:
            List of entities with their relationships
        """
        with self.driver.session(database=self.database) as session:
            query = f"""
                MATCH path = (c:Chunk)-[:CONTAINS_ENTITY*1..{max_depth}]-(e:__Entity__)
                WHERE c.chunk_id IN $chunk_ids
                RETURN DISTINCT e, labels(e) as labels, 
                       [r IN relationships(path) | type(r)] as rel_types
                LIMIT 100
            """
            
            result = session.run(query, chunk_ids=chunk_ids)
            entities = []
            
            for record in result:
                entity_node = record["e"]
                entities.append({
                    "name": entity_node.get("name"),
                    "labels": record["labels"],
                    "properties": dict(entity_node),
                    "relationship_types": record["rel_types"]
                })
            
            return entities
    
    def get_related_entities(self, entity_name: str, max_depth: int = 2) -> List[Dict[str, Any]]:
        """
        Get entities related to a given entity
        
        Args:
            entity_name: Name of the entity
            max_depth: Maximum depth to traverse
            
        Returns:
            List of related entities
        """
        with self.driver.session(database=self.database) as session:
            query = f"""
                MATCH path = (e1:__Entity__ {{name: $entity_name}})-[*1..{max_depth}]-(e2:__Entity__)
                WHERE e1 <> e2
                RETURN DISTINCT e2, labels(e2) as labels,
                       [r IN relationships(path) | type(r)] as rel_types
                LIMIT 50
            """
            
            result = session.run(query, entity_name=entity_name)
            entities = []
            
            for record in result:
                entity_node = record["e2"]
                entities.append({
                    "name": entity_node.get("name"),
                    "labels": record["labels"],
                    "properties": dict(entity_node),
                    "relationship_types": record["rel_types"]
                })
            
            return entities
    
    def clear_all(self):
        """Clear all data from Neo4j"""
        with self.driver.session(database=self.database) as session:
            session.run("MATCH (n) DETACH DELETE n")
    
    def close(self):
        """Close the driver connection"""
        self.driver.close()

