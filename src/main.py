import asyncio
from kg_builder import KnowledgeGraphBuilder
from graphrag import GraphRAG
from pdf_processor import PDFProcessor
from config import (
    OPENAI_API_KEY,
    NEO4J_URI,
    NEO4J_USERNAME,
    NEO4J_PASSWORD,
    QDRANT_URL,
    QDRANT_API_KEY,
)


async def main():
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

    pdf_processor = PDFProcessor("static/docs/note.pdf")
    total_pages = pdf_processor.get_total_pages()
    print(f"\nPDF has {total_pages} pages")

    pages_per_batch = 10
    page_batches = pdf_processor.get_page_batches(pages_per_batch=pages_per_batch)
    print(
        f"Processing PDF in {len(page_batches)} batches ({pages_per_batch} pages per batch)"
    )

    text_batches = []
    for i, (start_page, end_page) in enumerate(page_batches):
        print(
            f"  Batch {i + 1}/{len(page_batches)}: Processing pages {start_page}-{end_page - 1}..."
        )
        batch_text = pdf_processor.process_batch(start_page, end_page)
        if batch_text.strip():
            text_batches.append(batch_text)

    print(f"Extracted {len(text_batches)} text batches")

    print("\n" + "=" * 60)
    print("Building Knowledge Graph (Async Batch Processing)")
    print("=" * 60)

    result = await kg_builder.async_build_from_text_batches(
        text_batches,
        max_concurrent_batches=3,
    )
    print("\nBuild complete!")
    print(f"Batches processed: {result.get('batches_processed', len(text_batches))}")
    print(f"Chunks: {result['chunks_created']}")
    print(f"Entities: {result['entities_extracted']}")
    print(f"Relationships: {result['relationships_extracted']}")

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

    kg_builder.clear_all()


if __name__ == "__main__":
    asyncio.run(main())
