"""
Example Usage of Custom Knowledge Graph Builder
"""

import os
from dotenv import load_dotenv
from kg_builder import KnowledgeGraphBuilder
from graphrag import GraphRAG
from pdf_reader import PDFReader

# Load environment variables
load_dotenv()


def example_build_and_search():
    """Example: Build knowledge graph and search"""

    # Configuration
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    NEO4J_URI = os.getenv("NEO4J_URI", "neo4j+s://your-instance.databases.neo4j.io")
    NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
    NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "your-password")

    # Optional: Qdrant cloud
    QDRANT_URL = os.getenv("QDRANT_URL", None)
    QDRANT_API_KEY = os.getenv("QDRANT_API_KEY", None)

    # PDF file path
    PDF_PATH = os.getenv(
        "PDF_PATH", "../note.pdf"
    )  # Default to note.pdf in parent directory

    if not OPENAI_API_KEY:
        print("Error: OPENAI_API_KEY not set")
        return

    if not NEO4J_PASSWORD:
        print("Error: NEO4J_PASSWORD not set")
        return

    print("=" * 60)
    print("CUSTOM KNOWLEDGE GRAPH BUILDER")
    print("=" * 60)

    # Read text from PDF
    print("\n0. Reading PDF file...")
    pdf_reader = PDFReader()
    try:
        text = pdf_reader.read_pdf(PDF_PATH)
        print(f"✅ Successfully loaded PDF: {PDF_PATH}")
        print(f"   Text length: {len(text)} characters")
    except FileNotFoundError:
        print(f"❌ Error: PDF file not found: {PDF_PATH}")
        print(
            "   Please set PDF_PATH environment variable or place note.pdf in parent directory"
        )
        return
    except Exception as e:
        print(f"❌ Error reading PDF: {e}")
        return

    # Initialize builder
    print("\n1. Initializing Knowledge Graph Builder...")
    kg_builder = KnowledgeGraphBuilder(
        openai_api_key=OPENAI_API_KEY,
        neo4j_uri=NEO4J_URI,
        neo4j_username=NEO4J_USERNAME,
        neo4j_password=NEO4J_PASSWORD,
        qdrant_url=QDRANT_URL,
        qdrant_api_key=QDRANT_API_KEY,
        chunk_size=500,
        chunk_overlap=100,
    )

    # Build knowledge graph
    print("\n2. Building Knowledge Graph from text...")
    result = kg_builder.build_from_text(text)

    print("\n✅ Build Complete!")
    print(f"   Chunks created: {result['chunks_created']}")
    print(f"   Entities extracted: {result['entities_extracted']}")
    print(f"   Relationships extracted: {result['relationships_extracted']}")

    # Initialize GraphRAG
    print("\n3. Initializing GraphRAG...")
    graphrag = GraphRAG(
        openai_api_key=OPENAI_API_KEY,
        vector_store=kg_builder.vector_store,
        graph_store=kg_builder.graph_store,
        top_k_chunks=5,
        max_depth=2,
    )

    # Search queries (adjust based on your PDF content)
    queries = [
        "What is the main topic of this document?",
        "What are the key concepts discussed?",
        "What are the important relationships mentioned?",
    ]

    print("\n4. Searching with GraphRAG...")
    print("=" * 60)

    for query in queries:
        print(f"\nQuery: {query}")
        print("-" * 60)

        result = graphrag.search(query)

        print(f"Answer: {result['answer']}")
        print("\nContext used:")
        print(f"  - Chunks: {result['chunks_used']}")
        print(f"  - Entities: {result['entities_found']}")

    print("\n" + "=" * 60)
    print("Example Complete!")
    print("=" * 60)


if __name__ == "__main__":
    example_build_and_search()
