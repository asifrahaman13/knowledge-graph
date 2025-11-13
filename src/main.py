"""
Main Entry Point
Example usage of the custom knowledge graph builder
"""

import os
import asyncio
from dotenv import load_dotenv
from kg_builder import KnowledgeGraphBuilder
from graphrag import GraphRAG
from pdf_processor import PDFProcessor

load_dotenv()


async def main():
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
        chunk_overlap=100,
    )

    # Process PDF in batches
    pdf_processor = PDFProcessor("static/docs/note.pdf")
    total_pages = pdf_processor.get_total_pages()
    print(f"\nPDF has {total_pages} pages")

    # Get page batches (process 10 pages at a time)
    pages_per_batch = 10
    page_batches = pdf_processor.get_page_batches(pages_per_batch=pages_per_batch)
    print(
        f"Processing PDF in {len(page_batches)} batches ({pages_per_batch} pages per batch)"
    )

    # Process each batch to extract text
    text_batches = []
    for i, (start_page, end_page) in enumerate(page_batches):
        print(
            f"  Batch {i + 1}/{len(page_batches)}: Processing pages {start_page}-{end_page - 1}..."
        )
        batch_text = pdf_processor.process_batch(start_page, end_page)
        if batch_text.strip():  # Only add non-empty batches
            text_batches.append(batch_text)

    print(f"Extracted {len(text_batches)} text batches")

    # Build knowledge graph from batches (async, parallel processing)
    print("\n" + "=" * 60)
    print("Building Knowledge Graph (Async Batch Processing)")
    print("=" * 60)

    result = await kg_builder.async_build_from_text_batches(
        text_batches,
        max_concurrent_batches=3,  # Process 3 batches in parallel
    )
    print("\nBuild complete!")
    print(f"Batches processed: {result.get('batches_processed', len(text_batches))}")
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
        max_depth=2,
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
    kg_builder.clear_all()


if __name__ == "__main__":
    asyncio.run(main())
