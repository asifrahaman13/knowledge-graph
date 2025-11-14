# Custom Knowledge Graph Builder from Scratch

A complete custom implementation of a knowledge graph builder using Qdrant for vector storage and Neo4j for graph storage. Process PDFs, extract entities and relationships, and perform intelligent search using GraphRAG.

<img width="1570" height="622" alt="Screenshot from 2025-11-13 23-33-05" src="https://github.com/user-attachments/assets/6bbba9b4-45ef-4503-a54d-09cbc52aa486" />


## Features

- ✅ **Custom Implementation**: Built from scratch, no dependencies on neo4j_graphrag
- ✅ **Qdrant Integration**: Fast vector similarity search
- ✅ **Neo4j Integration**: Powerful graph traversal
- ✅ **LLM-Powered**: Uses GPT for entity/relationship extraction
- ✅ **Configurable**: All parameters are customizable
- ✅ **Scalable**: Handles large documents efficiently
- ✅ **Async Processing**: Parallel batch processing for faster ingestion
- ✅ **CLI Interface**: Easy-to-use command-line interface

## Architecture

```
Text Input
    ↓
[Text Chunker] → Chunks
    ↓
[Embedding Generator] → Embeddings
    ↓
[Entity Extractor] → Entities & Relationships
    ↓
[Qdrant Store] ← Chunks + Embeddings
[Neo4j Store] ← Entities + Relationships
```

## Installation

```bash
pip install -r requirements.txt
```

## Configuration

Set environment variables in `.env` file or export them:

```bash
export OPENAI_API_KEY="your-openai-api-key"
export NEO4J_URI="neo4j+s://your-instance.databases.neo4j.io"
export NEO4J_USERNAME="neo4j"
export NEO4J_PASSWORD="your-password"

# Optional: Qdrant cloud
export QDRANT_URL="https://your-cluster.qdrant.io"
export QDRANT_API_KEY="your-qdrant-api-key"
```

Or use the `config.py` file with a `.env` file (recommended).

## Quick Start

### 1. Upload and Process a PDF

```bash
python src/main.py upload static/docs/note.pdf
```

### 2. Search the Knowledge Graph

```bash
python src/main.py search "What is Kleros?"
```

## CLI Usage

### Upload Command

Upload and process PDF files to build the knowledge graph:

```bash
python src/main.py upload <pdf_path> [options]
```

**Arguments:**
- `pdf_path` - Path to the PDF file to process

**Options:**
- `--chunk-size <int>` - Size of text chunks (default: 500)
- `--chunk-overlap <int>` - Overlap between chunks (default: 100)
- `--pages-per-batch <int>` - Number of pages per batch (default: 10)
- `--max-concurrent-batches <int>` - Maximum concurrent batches (default: 3)
- `--clear` - Clear existing data before uploading

**Examples:**

```bash
# Basic upload
python src/main.py upload static/docs/note.pdf

# Upload with custom chunk size
python src/main.py upload static/docs/note.pdf --chunk-size 1000 --chunk-overlap 200

# Upload with custom batch settings
python src/main.py upload static/docs/note.pdf --pages-per-batch 5 --max-concurrent-batches 5

# Clear existing data and upload
python src/main.py upload static/docs/note.pdf --clear
```

### Search Command

Search the knowledge graph using natural language queries:

```bash
python src/main.py search "<query>" [options]
```

**Arguments:**
- `query` - Search query (use quotes for multi-word queries)

**Options:**
- `--top-k <int>` - Number of top chunks to retrieve (default: 5)
- `--max-depth <int>` - Maximum graph traversal depth (default: 2)

**Examples:**

```bash
# Basic search
python src/main.py search "What is Kleros?"

# Search with more chunks
python src/main.py search "What are the main concepts?" --top-k 10

# Search with deeper graph traversal
python src/main.py search "How does X relate to Y?" --max-depth 3
```

### Delete Command

Delete all data from Qdrant and Neo4j:

```bash
python src/main.py delete --confirm
```

**Options:**
- `--confirm` (required) - Confirmation flag to proceed with deletion

**Example:**
```bash
# Without confirmation (shows warning)
python src/main.py delete

# With confirmation (deletes all data)
python src/main.py delete --confirm
```

### Help

```bash
# General help
python src/main.py --help

# Command-specific help
python src/main.py upload --help
python src/main.py search --help
python src/main.py delete --help
```

## Programmatic Usage

### Basic Usage

```python
from src.builders.kg_builder import KnowledgeGraphBuilder
from src.builders.graphrag import GraphRAG

# Initialize builder
kg_builder = KnowledgeGraphBuilder(
    openai_api_key="your-key",
    neo4j_uri="neo4j+s://...",
    neo4j_username="neo4j",
    neo4j_password="password"
)

# Build knowledge graph
text = "Your text here..."
result = kg_builder.build_from_text(text)

# Initialize GraphRAG
graphrag = GraphRAG(
    openai_api_key="your-key",
    vector_store=kg_builder.vector_store,
    graph_store=kg_builder.graph_store
)

# Search
query = "What is X?"
answer = graphrag.search(query)
print(answer["answer"])
```

### Async Batch Processing

```python
import asyncio
from src.processors.pdf_processor import PDFProcessor

pdf_processor = PDFProcessor("static/docs/note.pdf")
page_batches = pdf_processor.get_page_batches(pages_per_batch=10)

text_batches = []
for start_page, end_page in page_batches:
    text_batches.append(pdf_processor.process_batch(start_page, end_page))

# Process batches in parallel
result = await kg_builder.async_build_from_text_batches(
    text_batches,
    max_concurrent_batches=3
)
```

## Project Structure

The codebase is organized into logical modules:

### Core (`src/core/`)
Core processing components:
- **text_chunker.py**: Splits text into chunks with overlap
- **embeddings.py**: Generates vector embeddings (async support)
- **entity_extractor.py**: Extracts entities and relationships using LLM

### Storage (`src/storage/`)
Storage backends:
- **qdrant_store.py**: Vector storage (local or cloud)
- **neo4j_store.py**: Graph storage with graceful error handling

### Builders (`src/builders/`)
High-level orchestrators:
- **kg_builder.py**: Main knowledge graph building pipeline
- **graphrag.py**: GraphRAG search and retrieval

### Processors (`src/processors/`)
File processing:
- **pdf_reader.py**: PDF text extraction
- **pdf_processor.py**: PDF processing with batch support

### Config (`src/config/`)
Configuration:
- **config.py**: Environment variable management
- **models.py**: Model enums

### CLI (`src/cli/`)
Command-line interface:
- **main.py**: Upload and search commands

## How It Works

### Upload Process

1. **PDF Processing**: Extracts text from PDF in batches
2. **Text Chunking**: Splits text into manageable pieces
3. **Embedding**: Creates vector representations (parallel)
4. **Extraction**: LLM extracts entities and relationships (parallel)
5. **Storage**: Stores chunks in Qdrant, graph in Neo4j

### Search Process

1. **Vector Search**: Find similar chunks using embeddings
2. **Graph Traversal**: Get entities connected to relevant chunks
3. **Context Building**: Combine chunk text + entity information
4. **Answer Generation**: LLM generates answer from context

## Documentation

- [Architecture Overview](docs/ARCHITECTURE.md) - System architecture and design
- [Usage Guide](docs/USAGE.md) - Detailed usage instructions
- [CLI Reference](docs/CLI.md) - Complete CLI documentation

## Notes

- The implementation uses Neo4j driver for graph operations (standard approach)
- Qdrant can run locally (default) or in the cloud
- All LLM calls use OpenAI API
- The system handles 'id' property conflicts automatically
- Neo4j connection failures are handled gracefully (system continues with Qdrant only)

## License

MIT
