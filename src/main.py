"""
Main Entry Point
Example usage of the custom knowledge graph builder
"""

import os
from kg_builder import KnowledgeGraphBuilder
from graphrag import GraphRAG


def main():
    """Example usage"""
    
    # Configuration
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "your-api-key")
    NEO4J_URI = os.getenv("NEO4J_URI", "neo4j+s://your-instance.databases.neo4j.io")
    NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
    NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "your-password")
    
    # Optional: Qdrant cloud configuration
    QDRANT_URL = os.getenv("QDRANT_URL", None)  # None for local
    QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", None)
    
    # Initialize knowledge graph builder
    print("=" * 60)
    print("Initializing Knowledge Graph Builder")
    print("=" * 60)
    
    kg_builder = KnowledgeGraphBuilder(
        openai_api_key=OPENAI_API_KEY,
        neo4j_uri=NEO4J_URI,
        neo4j_username=NEO4J_USERNAME,
        neo4j_password=NEO4J_PASSWORD,
        qdrant_url=QDRANT_URL,
        qdrant_api_key=QDRANT_API_KEY,
        chunk_size=500,
        chunk_overlap=100
    )
    
    # Example text
    text = """Scientists have recently announced the discovery of a remarkable new species they've named Kleros, 
    a creature that has quickly captured the imagination of the global scientific community. Found deep within 
    the dense rainforests of the Amazon, Kleros is unlike any known animal — a fascinating blend of mammalian 
    intelligence and reptilian resilience. Its translucent skin reveals a complex network of bioluminescent veins 
    that glow softly at night, possibly used for communication or camouflage. Early observations suggest Kleros 
    possesses advanced problem-solving abilities, hinting at a level of cognition previously unseen in wild species. 
    Researchers are still puzzled by its diet, as it appears to absorb nutrients both from small insects and from 
    a symbiotic relationship with luminous fungi growing on its back."""
    
    # Build knowledge graph
    print("\n" + "=" * 60)
    print("Building Knowledge Graph")
    print("=" * 60)
    
    result = kg_builder.build_from_text(text)
    print(f"\nBuild complete!")
    print(f"Chunks: {result['chunks_created']}")
    print(f"Entities: {result['entities_extracted']}")
    print(f"Relationships: {result['relationships_extracted']}")
    
    # Initialize GraphRAG
    print("\n" + "=" * 60)
    print("Initializing GraphRAG")
    print("=" * 60)
    
    graphrag = GraphRAG(
        openai_api_key=OPENAI_API_KEY,
        vector_store=kg_builder.vector_store,
        graph_store=kg_builder.graph_store,
        top_k_chunks=5,
        max_depth=2
    )
    
    # Search
    print("\n" + "=" * 60)
    print("Searching with GraphRAG")
    print("=" * 60)
    
    query = "What is Kleros?"
    print(f"\nQuery: {query}\n")
    
    result = graphrag.search(query)
    
    print("Answer:")
    print("-" * 60)
    print(result["answer"])
    print("-" * 60)
    print(f"\nChunks used: {result['chunks_used']}")
    print(f"Entities found: {result['entities_found']}")
    
    # Cleanup (optional)
    # kg_builder.clear_all()


if __name__ == "__main__":
    main()

