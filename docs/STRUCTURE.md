# Project Structure

This document describes the organization of the codebase.

## Directory Structure

```
src/
├── __init__.py              # Package initialization with exports
├── main.py                   # CLI entry point
│
├── core/                     # Core processing components
│   ├── __init__.py
│   ├── text_chunker.py      # Text chunking with overlap
│   ├── embeddings.py        # Vector embedding generation
│   └── entity_extractor.py  # Entity/relationship extraction
│
├── storage/                  # Storage backends
│   ├── __init__.py
│   ├── qdrant_store.py      # Qdrant vector storage
│   └── neo4j_store.py       # Neo4j graph storage
│
├── builders/                 # High-level orchestrators
│   ├── __init__.py
│   ├── kg_builder.py        # Knowledge graph builder
│   └── graphrag.py         # GraphRAG search system
│
├── processors/               # File processors
│   ├── __init__.py
│   ├── pdf_reader.py        # PDF text extraction
│   └── pdf_processor.py    # PDF batch processing
│
├── config/                   # Configuration
│   ├── __init__.py
│   ├── config.py           # Environment variables
│   └── models.py           # Model enums
│
└── cli/                      # Command-line interface
    ├── __init__.py
    └── main.py             # CLI implementation
```

## Module Descriptions

### Core (`src/core/`)

Core processing components that handle text processing and AI operations.

- **text_chunker.py**: Splits text into chunks with configurable size and overlap
- **embeddings.py**: Generates vector embeddings using OpenAI API (sync and async)
- **entity_extractor.py**: Extracts entities and relationships using LLM (sync and async)

### Storage (`src/storage/`)

Storage backends for vectors and graphs.

- **qdrant_store.py**: Manages vector storage in Qdrant (local or cloud)
- **neo4j_store.py**: Manages graph storage in Neo4j with graceful error handling

### Builders (`src/builders/`)

High-level orchestrators that coordinate multiple components.

- **kg_builder.py**: Main knowledge graph building pipeline with async batch support
- **graphrag.py**: GraphRAG search and retrieval system combining vector and graph search

### Processors (`src/processors/`)

File processing utilities.

- **pdf_reader.py**: Low-level PDF text extraction
- **pdf_processor.py**: High-level PDF processing with batch support

### Config (`src/config/`)

Configuration and model definitions.

- **config.py**: Environment variable management using python-dotenv
- **models.py**: Enums for LLM and embedding models

### CLI (`src/cli/`)

Command-line interface.

- **main.py**: CLI implementation with `upload` and `search` commands

## Import Patterns

### From Package Root

```python
from src.core import TextChunker, EmbeddingGenerator, EntityRelationshipExtractor
from src.storage import QdrantVectorStore, Neo4jGraphStore
from src.builders import KnowledgeGraphBuilder, GraphRAG
from src.processors import PDFReader, PDFProcessor
from src.config import OPENAI_API_KEY, LLMModels, EmbeddingModels
```

### Direct Module Imports

```python
from src.core.text_chunker import TextChunker
from src.builders.kg_builder import KnowledgeGraphBuilder
from src.processors.pdf_processor import PDFProcessor
```

### Relative Imports (Within Package)

```python
# Within core/
from ..config.models import EmbeddingModels

# Within builders/
from ..core.text_chunker import TextChunker
from ..storage.qdrant_store import QdrantVectorStore
```

## Benefits of This Structure

1. **Clear Separation**: Each module has a specific responsibility
2. **Easy Navigation**: Related files are grouped together
3. **Scalability**: Easy to add new components to appropriate modules
4. **Maintainability**: Changes to one module don't affect others
5. **Testability**: Each module can be tested independently

## Adding New Components

### Adding a New Core Component

1. Add file to `src/core/`
2. Export in `src/core/__init__.py`
3. Update `src/__init__.py` if needed

### Adding a New Storage Backend

1. Add file to `src/storage/`
2. Export in `src/storage/__init__.py`
3. Update builders to use new storage

### Adding a New Processor

1. Add file to `src/processors/`
2. Export in `src/processors/__init__.py`
3. Update CLI or builders to use new processor

