import argparse
from enum import Enum
from ..builders.kg_builder import KnowledgeGraphBuilder
from ..builders.graphrag import GraphRAG
from ..processors.pdf_processor import PDFProcessor
from ..core.logger import log
from ..config.config import (
    OPENAI_API_KEY,
    NEO4J_URI,
    NEO4J_USERNAME,
    NEO4J_PASSWORD,
    QDRANT_URL,
    QDRANT_API_KEY,
    ELASTICSEARCH_URL,
    ELASTICSEARCH_API_KEY,
    REDIS_HOST,
    REDIS_PORT,
    REDIS_PASSWORD,
    REDIS_DB,
    REDIS_DEFAULT_TTL,
)
from ..storage.redis_cache import RedisCache


class Commands(Enum):
    UPLOAD = "upload"
    SEARCH = "search"
    DELETE = "delete"


async def upload_pdf(
    pdf_path: str,
    chunk_size: int = 500,
    chunk_overlap: int = 100,
    pages_per_batch: int = 10,
    max_concurrent_batches: int = 3,
    clear_existing: bool = False,
):
    log.info("=" * 60)
    log.info("Initializing Redis Cache")
    log.info("=" * 60)

    redis_cache = RedisCache(
        host=REDIS_HOST,
        port=REDIS_PORT,
        password=REDIS_PASSWORD,
        db=REDIS_DB,
        default_ttl=REDIS_DEFAULT_TTL,
    )

    log.info("=" * 60)
    log.info("Initializing Knowledge Graph Builder")
    log.info("=" * 60)

    kg_builder = KnowledgeGraphBuilder(
        openai_api_key=OPENAI_API_KEY,
        neo4j_uri=NEO4J_URI,
        neo4j_username=NEO4J_USERNAME,
        neo4j_password=NEO4J_PASSWORD,
        qdrant_url=QDRANT_URL,
        qdrant_api_key=QDRANT_API_KEY,
        elasticsearch_url=ELASTICSEARCH_URL,
        elasticsearch_api_key=ELASTICSEARCH_API_KEY,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        redis_cache=redis_cache,
    )

    await kg_builder.initialize()

    if clear_existing:
        log.info("Clearing existing data...")
        await kg_builder.clear_all()

    pdf_processor = PDFProcessor(pdf_path)
    total_pages = pdf_processor.get_total_pages()
    log.info(f"PDF has {total_pages} pages")

    page_batches = pdf_processor.get_page_batches(pages_per_batch=pages_per_batch)
    log.info(
        f"Processing PDF in {len(page_batches)} batches ({pages_per_batch} pages per batch)"
    )

    from concurrent.futures import ThreadPoolExecutor, as_completed
    from multiprocessing import cpu_count
    from typing import List, Optional

    max_workers = min(cpu_count(), 4)

    batch_results: List[Optional[str]] = [None] * len(page_batches)

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        future_to_batch = {
            executor.submit(pdf_processor.process_batch, start, end): (i, start, end)
            for i, (start, end) in enumerate(page_batches)
        }

        for future in as_completed(future_to_batch):
            i, start, end = future_to_batch[future]
            try:
                batch_text = future.result()
                if batch_text and batch_text.strip():
                    batch_results[i] = batch_text
            except Exception as e:
                log.warning(f"Failed to process batch {i} (pages {start}-{end}): {e}")

    text_batches: List[str] = [batch for batch in batch_results if batch is not None]

    log.info(f"Extracted {len(text_batches)} text batches")

    log.info("=" * 60)
    log.info("Building Knowledge Graph (Async Batch Processing)")
    log.info("=" * 60)

    result = await kg_builder.async_build_from_text_batches(
        text_batches,
        max_concurrent_batches=max_concurrent_batches,
    )
    log.info("Build complete!")
    log.info(f"Batches processed: {result.get('batches_processed', len(text_batches))}")
    log.info(f"Chunks: {result['chunks_created']}")
    log.info(f"Entities: {result['entities_extracted']}")
    log.info(f"Relationships: {result['relationships_extracted']}")


async def search_query(
    query: str,
    top_k_chunks: int = 5,
    max_depth: int = 2,
    use_hybrid_search: bool = True,
    vector_weight: float = 0.7,
    keyword_weight: float = 0.3,
):
    log.info("=" * 60)
    log.info("Initializing Redis Cache")
    log.info("=" * 60)

    redis_cache = RedisCache(
        host=REDIS_HOST,
        port=REDIS_PORT,
        password=REDIS_PASSWORD,
        db=REDIS_DB,
        default_ttl=REDIS_DEFAULT_TTL,
    )

    log.info("=" * 60)
    log.info("Initializing Knowledge Graph Builder")
    log.info("=" * 60)

    kg_builder = KnowledgeGraphBuilder(
        openai_api_key=OPENAI_API_KEY,
        neo4j_uri=NEO4J_URI,
        neo4j_username=NEO4J_USERNAME,
        neo4j_password=NEO4J_PASSWORD,
        qdrant_url=QDRANT_URL,
        qdrant_api_key=QDRANT_API_KEY,
        elasticsearch_url=ELASTICSEARCH_URL,
        elasticsearch_api_key=ELASTICSEARCH_API_KEY,
        redis_cache=redis_cache,
    )

    await kg_builder.initialize()

    log.info("=" * 60)
    log.info("Initializing GraphRAG")
    log.info("=" * 60)

    graphrag = GraphRAG(
        openai_api_key=OPENAI_API_KEY,
        vector_store=kg_builder.vector_store,
        graph_store=kg_builder.graph_store,
        elasticsearch_store=kg_builder.elasticsearch_store,
        top_k_chunks=top_k_chunks,
        max_depth=max_depth,
        use_hybrid_search=use_hybrid_search,
        vector_weight=vector_weight,
        keyword_weight=keyword_weight,
        redis_cache=redis_cache,
    )

    search_type = (
        "Hybrid (Vector + Keyword + Graph)" if use_hybrid_search else "Vector + Graph"
    )
    log.info(f"Search mode: {search_type}")

    log.info("=" * 60)
    log.info("Searching with GraphRAG")
    log.info("=" * 60)

    log.info(f"Query: {query}")

    result = await graphrag.search(query)

    log.info("Answer:")
    log.info("-" * 60)
    log.info(result["answer"])
    log.info("-" * 60)
    log.info(f"Chunks used: {result['chunks_used']}")
    log.info(f"Entities found: {result['entities_found']}")
    log.info(f"Search type: {result.get('search_type', 'unknown')}")


async def delete_all():
    log.info("=" * 60)
    log.info("Deleting All Data")
    log.info("=" * 60)

    kg_builder = KnowledgeGraphBuilder(
        openai_api_key=OPENAI_API_KEY,
        neo4j_uri=NEO4J_URI,
        neo4j_username=NEO4J_USERNAME,
        neo4j_password=NEO4J_PASSWORD,
        qdrant_url=QDRANT_URL,
        qdrant_api_key=QDRANT_API_KEY,
        elasticsearch_url=ELASTICSEARCH_URL,
        elasticsearch_api_key=ELASTICSEARCH_API_KEY,
    )

    await kg_builder.initialize()

    log.info("Clearing all data from Qdrant, Elasticsearch, and Neo4j...")
    await kg_builder.clear_all()
    log.info("All data deleted successfully!")


async def main():
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
    search_parser.add_argument(
        "--no-hybrid",
        action="store_true",
        help="Disable hybrid search (use vector search only)",
    )
    search_parser.add_argument(
        "--vector-weight",
        type=float,
        default=0.7,
        help="Weight for vector search in hybrid mode (default: 0.7)",
    )
    search_parser.add_argument(
        "--keyword-weight",
        type=float,
        default=0.3,
        help="Weight for keyword search in hybrid mode (default: 0.3)",
    )

    delete_parser = subparsers.add_parser(
        "delete", help="Delete all data from Qdrant, Elasticsearch, and Neo4j"
    )
    delete_parser.add_argument(
        "--confirm",
        action="store_true",
        help="Confirm deletion (required for safety)",
    )

    args = parser.parse_args()

    if args.command == Commands.UPLOAD.value:
        await upload_pdf(
            pdf_path=args.pdf_path,
            chunk_size=args.chunk_size,
            chunk_overlap=args.chunk_overlap,
            pages_per_batch=args.pages_per_batch,
            max_concurrent_batches=args.max_concurrent_batches,
            clear_existing=args.clear,
        )
    elif args.command == Commands.SEARCH.value:
        await search_query(
            query=args.query,
            top_k_chunks=args.top_k,
            max_depth=args.max_depth,
            use_hybrid_search=not args.no_hybrid,
            vector_weight=args.vector_weight,
            keyword_weight=args.keyword_weight,
        )
    elif args.command == Commands.DELETE.value:
        if not args.confirm:
            log.warning(
                "WARNING: This will delete ALL data from Qdrant, Elasticsearch, and Neo4j!"
            )
            log.warning("Use --confirm flag to proceed with deletion.")
            log.warning("Example: python src/main.py delete --confirm")
            return
        await delete_all()
    else:
        parser.print_help()
