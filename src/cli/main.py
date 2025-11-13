import asyncio
import argparse
from ..builders.kg_builder import KnowledgeGraphBuilder
from ..builders.graphrag import GraphRAG
from ..processors.pdf_processor import PDFProcessor
from ..config.config import (
    OPENAI_API_KEY,
    NEO4J_URI,
    NEO4J_USERNAME,
    NEO4J_PASSWORD,
    QDRANT_URL,
    QDRANT_API_KEY,
)


async def upload_pdf(
    pdf_path: str,
    chunk_size: int = 500,
    chunk_overlap: int = 100,
    pages_per_batch: int = 10,
    max_concurrent_batches: int = 3,
    clear_existing: bool = False,
):
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
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )

    if clear_existing:
        print("\nClearing existing data...")
        kg_builder.clear_all()

    pdf_processor = PDFProcessor(pdf_path)
    total_pages = pdf_processor.get_total_pages()
    print(f"\nPDF has {total_pages} pages")

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
        max_concurrent_batches=max_concurrent_batches,
    )
    print("\nBuild complete!")
    print(f"Batches processed: {result.get('batches_processed', len(text_batches))}")
    print(f"Chunks: {result['chunks_created']}")
    print(f"Entities: {result['entities_extracted']}")
    print(f"Relationships: {result['relationships_extracted']}")


async def search_query(
    query: str,
    top_k_chunks: int = 5,
    max_depth: int = 2,
):
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
    )

    print("\n" + "=" * 60)
    print("Initializing GraphRAG")
    print("=" * 60)

    graphrag = GraphRAG(
        openai_api_key=OPENAI_API_KEY,
        vector_store=kg_builder.vector_store,
        graph_store=kg_builder.graph_store,
        top_k_chunks=top_k_chunks,
        max_depth=max_depth,
    )

    print("\n" + "=" * 60)
    print("Searching with GraphRAG")
    print("=" * 60)

    print(f"\nQuery: {query}\n")

    result = graphrag.search(query)

    print("Answer:")
    print("-" * 60)
    print(result["answer"])
    print("-" * 60)
    print(f"\nChunks used: {result['chunks_used']}")
    print(f"Entities found: {result['entities_found']}")


async def delete_all():
    print("=" * 60)
    print("Deleting All Data")
    print("=" * 60)

    kg_builder = KnowledgeGraphBuilder(
        openai_api_key=OPENAI_API_KEY,
        neo4j_uri=NEO4J_URI,
        neo4j_username=NEO4J_USERNAME,
        neo4j_password=NEO4J_PASSWORD,
        qdrant_url=QDRANT_URL,
        qdrant_api_key=QDRANT_API_KEY,
    )

    print("\nClearing all data from Qdrant and Neo4j...")
    kg_builder.clear_all()
    print("\n✅ All data deleted successfully!")


def main():
    parser = argparse.ArgumentParser(
        description="Knowledge Graph Builder - Upload PDFs and Search"
    )
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    upload_parser = subparsers.add_parser("upload", help="Upload and process PDF file")
    upload_parser.add_argument(
        "pdf_path",
        type=str,
        help="Path to the PDF file to process",
    )
    upload_parser.add_argument(
        "--chunk-size",
        type=int,
        default=500,
        help="Size of text chunks (default: 500)",
    )
    upload_parser.add_argument(
        "--chunk-overlap",
        type=int,
        default=100,
        help="Overlap between chunks (default: 100)",
    )
    upload_parser.add_argument(
        "--pages-per-batch",
        type=int,
        default=10,
        help="Number of pages per batch (default: 10)",
    )
    upload_parser.add_argument(
        "--max-concurrent-batches",
        type=int,
        default=3,
        help="Maximum concurrent batches (default: 3)",
    )
    upload_parser.add_argument(
        "--clear",
        action="store_true",
        help="Clear existing data before uploading",
    )

    search_parser = subparsers.add_parser("search", help="Search the knowledge graph")
    search_parser.add_argument(
        "query",
        type=str,
        help="Search query",
    )
    search_parser.add_argument(
        "--top-k",
        type=int,
        default=5,
        help="Number of top chunks to retrieve (default: 5)",
    )
    search_parser.add_argument(
        "--max-depth",
        type=int,
        default=2,
        help="Maximum graph traversal depth (default: 2)",
    )

    delete_parser = subparsers.add_parser(
        "delete", help="Delete all data from Qdrant and Neo4j"
    )
    delete_parser.add_argument(
        "--confirm",
        action="store_true",
        help="Confirm deletion (required for safety)",
    )

    args = parser.parse_args()

    if args.command == "upload":
        asyncio.run(
            upload_pdf(
                pdf_path=args.pdf_path,
                chunk_size=args.chunk_size,
                chunk_overlap=args.chunk_overlap,
                pages_per_batch=args.pages_per_batch,
                max_concurrent_batches=args.max_concurrent_batches,
                clear_existing=args.clear,
            )
        )
    elif args.command == "search":
        asyncio.run(
            search_query(
                query=args.query,
                top_k_chunks=args.top_k,
                max_depth=args.max_depth,
            )
        )
    elif args.command == "delete":
        if not args.confirm:
            print("⚠️  WARNING: This will delete ALL data from Qdrant and Neo4j!")
            print("Use --confirm flag to proceed with deletion.")
            print("\nExample: python src/main.py delete --confirm")
            return
        asyncio.run(delete_all())
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
