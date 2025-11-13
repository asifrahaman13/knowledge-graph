# Usage Guide

Complete guide to using the Knowledge Graph Builder.

## Table of Contents

1. [Installation](#installation)
2. [Configuration](#configuration)
3. [CLI Usage](#cli-usage)
4. [Programmatic Usage](#programmatic-usage)
5. [Advanced Features](#advanced-features)
6. [Troubleshooting](#troubleshooting)

## Installation

### Prerequisites

- Python 3.8+
- OpenAI API key
- Neo4j database (optional, but recommended)
- Qdrant (local or cloud)

### Install Dependencies

```bash
pip install -r requirements.txt
```

Required packages:
- `openai` - OpenAI API client
- `neo4j` - Neo4j driver
- `qdrant-client` - Qdrant client
- `pypdf` or `PyPDF2` - PDF processing
- `python-dotenv` - Environment variable management

## Configuration

### Environment Variables

Create a `.env` file in the project root:

```env
OPENAI_API_KEY=your-openai-api-key
NEO4J_URI=neo4j+s://your-instance.databases.neo4j.io
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=your-password

# Optional: Qdrant cloud
QDRANT_URL=https://your-cluster.qdrant.io
QDRANT_API_KEY=your-qdrant-api-key
```

Or export them in your shell:

```bash
export OPENAI_API_KEY="your-openai-api-key"
export NEO4J_URI="neo4j+s://your-instance.databases.neo4j.io"
export NEO4J_USERNAME="neo4j"
export NEO4J_PASSWORD="your-password"
```

### Configuration File

The `config.py` file automatically loads environment variables using `python-dotenv`.

## CLI Usage

### Upload Command

The `upload` command processes PDF files and builds the knowledge graph.

#### Basic Upload

```bash
python src/main.py upload static/docs/note.pdf
```

#### Upload Options

| Option | Description | Default |
|--------|-------------|---------|
| `--chunk-size` | Size of text chunks in characters | 500 |
| `--chunk-overlap` | Overlap between chunks in characters | 100 |
| `--pages-per-batch` | Number of pages to process per batch | 10 |
| `--max-concurrent-batches` | Maximum concurrent batch processing | 3 |
| `--clear` | Clear existing data before uploading | False |

#### Examples

**Small chunks for detailed analysis:**
```bash
python src/main.py upload document.pdf --chunk-size 300 --chunk-overlap 50
```

**Large chunks for broader context:**
```bash
python src/main.py upload document.pdf --chunk-size 1000 --chunk-overlap 200
```

**Fast processing with more concurrent batches:**
```bash
python src/main.py upload document.pdf --pages-per-batch 20 --max-concurrent-batches 5
```

**Replace existing data:**
```bash
python src/main.py upload document.pdf --clear
```

### Delete Command

Delete all data from Qdrant and Neo4j databases.

```bash
python src/main.py delete --confirm
```

**Options:**
- `--confirm` (required) - Confirmation flag to proceed with deletion

**Examples:**

```bash
# Shows warning without confirmation
python src/main.py delete

# Deletes all data
python src/main.py delete --confirm
```

**Warning:** This operation permanently deletes all data and cannot be undone!

### Search Command

The `search` command queries the knowledge graph using natural language.

#### Basic Search

```bash
python src/main.py search "What is Kleros?"
```

#### Search Options

| Option | Description | Default |
|--------|-------------|---------|
| `--top-k` | Number of top chunks to retrieve | 5 |
| `--max-depth` | Maximum graph traversal depth | 2 |

#### Examples

**Simple query:**
```bash
python src/main.py search "What is the main topic?"
```

**Complex query with more context:**
```bash
python src/main.py search "How does X relate to Y?" --top-k 10 --max-depth 3
```

**Finding relationships:**
```bash
python src/main.py search "What are the connections between A and B?" --max-depth 4
```

## Programmatic Usage

### Basic Example

```python
import asyncio
from src.builders.kg_builder import KnowledgeGraphBuilder
from src.builders.graphrag import GraphRAG
from src.config.config import (
    OPENAI_API_KEY,
    NEO4J_URI,
    NEO4J_USERNAME,
    NEO4J_PASSWORD,
    QDRANT_URL,
    QDRANT_API_KEY,
)

# Initialize builder
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
text = "Your text content here..."
result = kg_builder.build_from_text(text)
print(f"Created {result['chunks_created']} chunks")
print(f"Extracted {result['entities_extracted']} entities")

# Initialize GraphRAG
graphrag = GraphRAG(
    openai_api_key=OPENAI_API_KEY,
    vector_store=kg_builder.vector_store,
    graph_store=kg_builder.graph_store,
    top_k_chunks=5,
    max_depth=2,
)

# Search
query = "What is the main topic?"
result = graphrag.search(query)
print(result["answer"])
```

### Async Batch Processing

```python
import asyncio
from src.processors.pdf_processor import PDFProcessor
from src.builders.kg_builder import KnowledgeGraphBuilder

async def process_pdf(pdf_path: str):
    kg_builder = KnowledgeGraphBuilder(...)
    pdf_processor = PDFProcessor(pdf_path)
    
    # Get page batches
    page_batches = pdf_processor.get_page_batches(pages_per_batch=10)
    
    # Extract text batches
    text_batches = []
    for start_page, end_page in page_batches:
        text_batches.append(
            pdf_processor.process_batch(start_page, end_page)
        )
    
    # Process in parallel
    result = await kg_builder.async_build_from_text_batches(
        text_batches,
        max_concurrent_batches=3
    )
    
    return result

# Run
result = asyncio.run(process_pdf("document.pdf"))
```

### Custom Configuration

```python
from src.config.models import EmbeddingModels, LLMModels

kg_builder = KnowledgeGraphBuilder(
    openai_api_key=OPENAI_API_KEY,
    neo4j_uri=NEO4J_URI,
    neo4j_username=NEO4J_USERNAME,
    neo4j_password=NEO4J_PASSWORD,
    chunk_size=1000,
    chunk_overlap=200,
    embedding_model=EmbeddingModels.TEXT_EMBEDDING_3_LARGE.value,
    llm_model=LLMModels.GPT_4O.value,
)
```

## Advanced Features

### Batch Processing

Process large PDFs efficiently by splitting into batches:

```python
pdf_processor = PDFProcessor("large_document.pdf")
total_pages = pdf_processor.get_total_pages()

# Process in smaller batches
for i in range(0, total_pages, 50):
    start = i
    end = min(i + 50, total_pages)
    text = pdf_processor.process_batch(start, end)
    # Process batch...
```

### Custom Chunking Strategy

```python
from src.core.text_chunker import TextChunker

# Fine-grained chunks
chunker = TextChunker(chunk_size=300, chunk_overlap=50)

# Coarse-grained chunks
chunker = TextChunker(chunk_size=1500, chunk_overlap=300)
```

### Error Handling

```python
try:
    result = kg_builder.build_from_text(text)
except Exception as e:
    print(f"Error: {e}")
    # Handle error
```

### Clearing Data

```python
# Clear all data
kg_builder.clear_all()

# Clear only Qdrant
kg_builder.vector_store.delete_collection()

# Clear only Neo4j
kg_builder.graph_store.clear_all()
```

## Troubleshooting

### Common Issues

**1. Neo4j Connection Failed**
- The system will continue with Qdrant only
- Check your Neo4j credentials and URI
- Ensure Neo4j is accessible

**2. Qdrant Connection Issues**
- Local Qdrant is created automatically in `./qdrant_db`
- For cloud Qdrant, verify URL and API key

**3. OpenAI API Errors**
- Check your API key
- Verify you have sufficient credits
- Check rate limits

**4. PDF Processing Errors**
- Ensure `pypdf` or `PyPDF2` is installed
- Check PDF file path is correct
- Verify PDF is not corrupted

**5. Dimension Mismatch Errors**
- Ensure embedding model matches between upload and search
- Default is `text-embedding-3-large` (3072 dimensions)

### Performance Tips

1. **Adjust batch sizes** based on your system resources
2. **Use async processing** for faster ingestion
3. **Tune chunk sizes** based on your document type
4. **Monitor API rate limits** when processing large documents

### Best Practices

1. **Start with defaults** and adjust based on results
2. **Use appropriate chunk sizes** for your use case
3. **Clear data** when testing to avoid conflicts
4. **Monitor costs** when processing large documents
5. **Use cloud Qdrant** for production deployments

