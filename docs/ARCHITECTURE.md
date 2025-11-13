# Architecture Overview

## System Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Knowledge Graph Builder                   │
└─────────────────────────────────────────────────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
        ▼                   ▼                   ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│ Text Chunker │    │  Embeddings  │    │   Extractor  │
└──────────────┘    └──────────────┘    └──────────────┘
        │                   │                   │
        └───────────────────┼───────────────────┘
                            │
        ┌───────────────────┼───────────────────┐
        │                   │                   │
        ▼                   ▼                   ▼
┌──────────────┐    ┌──────────────┐    ┌──────────────┐
│ Qdrant Store │    │ Neo4j Store   │    │  GraphRAG    │
│  (Vectors)   │    │   (Graph)     │    │  (Search)    │
└──────────────┘    └──────────────┘    └──────────────┘
```

## Component Details

### 1. Text Processing Layer
- **text_chunker.py**: Splits text into chunks
- **embeddings.py**: Generates vector embeddings
- **entity_extractor.py**: Extracts entities/relationships using LLM

### 2. Storage Layer
- **qdrant_store.py**: Vector storage (Qdrant)
- **neo4j_store.py**: Graph storage (Neo4j)

### 3. Orchestration Layer
- **kg_builder.py**: Main pipeline orchestrator
- **graphrag.py**: Search and retrieval system

### 4. Application Layer
- **main.py**: Entry point
- **example.py**: Usage examples

## Data Flow

### Building Phase:
```
Text → Chunker → Chunks
                ↓
            Embeddings → Qdrant
                ↓
            Extractor → Entities/Relationships → Neo4j
```

### Search Phase:
```
Query → Embedding → Qdrant Search → Relevant Chunks
                                    ↓
                                Neo4j Traversal → Related Entities
                                    ↓
                                Context Building → LLM → Answer
```

## Key Features

1. **Custom Implementation**: Built from scratch, no dependencies on neo4j_graphrag
2. **Dual Storage**: Qdrant for vectors, Neo4j for graph
3. **LLM-Powered**: Uses GPT for extraction and answer generation
4. **Configurable**: All parameters customizable
5. **Scalable**: Handles large documents efficiently

## File Structure

```
.
├── src/
│   ├── __init__.py           # Package initialization
│   ├── main.py               # CLI entry point
│   ├── core/                 # Core processing components
│   │   ├── __init__.py
│   │   ├── text_chunker.py  # Text chunking logic
│   │   ├── embeddings.py     # Embedding generation
│   │   └── entity_extractor.py  # Entity/relationship extraction
│   ├── storage/              # Storage components
│   │   ├── __init__.py
│   │   ├── qdrant_store.py  # Qdrant vector store
│   │   └── neo4j_store.py   # Neo4j graph store
│   ├── builders/             # Main builders/orchestrators
│   │   ├── __init__.py
│   │   ├── kg_builder.py    # Knowledge graph builder
│   │   └── graphrag.py      # GraphRAG search
│   ├── processors/           # File processors
│   │   ├── __init__.py
│   │   ├── pdf_reader.py    # PDF reading
│   │   └── pdf_processor.py # PDF processing
│   ├── config/               # Configuration
│   │   ├── __init__.py
│   │   ├── config.py        # Configuration management
│   │   └── models.py        # Model enums
│   └── cli/                  # CLI interface
│       ├── __init__.py
│       └── main.py          # CLI implementation
├── docs/
│   ├── ARCHITECTURE.md      # This file
│   ├── USAGE.md             # Usage guide
│   └── CLI.md               # CLI reference
├── static/
│   └── docs/                # Sample PDF files
├── qdrant_db/               # Local Qdrant storage
├── requirements.txt         # Dependencies
├── README.md                # Main documentation
└── .env                     # Environment variables
```

## Module Organization

### Core (`src/core/`)
Core processing components that handle text processing and AI operations:
- **text_chunker.py**: Splits text into chunks with overlap
- **embeddings.py**: Generates vector embeddings using OpenAI
- **entity_extractor.py**: Extracts entities and relationships using LLM

### Storage (`src/storage/`)
Storage backends for vectors and graphs:
- **qdrant_store.py**: Vector storage using Qdrant
- **neo4j_store.py**: Graph storage using Neo4j

### Builders (`src/builders/`)
High-level orchestrators that coordinate components:
- **kg_builder.py**: Main knowledge graph building pipeline
- **graphrag.py**: GraphRAG search and retrieval system

### Processors (`src/processors/`)
File processing utilities:
- **pdf_reader.py**: Low-level PDF text extraction
- **pdf_processor.py**: High-level PDF processing with batch support

### Config (`src/config/`)
Configuration and model definitions:
- **config.py**: Environment variable management
- **models.py**: Model enums (LLM and embedding models)

### CLI (`src/cli/`)
Command-line interface:
- **main.py**: CLI implementation with upload and search commands

