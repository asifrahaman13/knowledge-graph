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
        │                   │                   │
        │         ┌──────────▼──────────┐       │
        │         │   Redis Cache       │       │
        │         │   (Performance)     │       │
        │         └──────────┬──────────┘       │
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
- **embeddings.py**: Generates vector embeddings (with Redis caching)
- **entity_extractor.py**: Extracts entities/relationships using LLM (with Redis caching)

### 2. Caching Layer
- **redis_cache.py**: Redis-based caching for embeddings and entity extractions
  - Reduces API calls to OpenAI
  - Improves performance and reduces costs
  - Configurable TTL (default: 7 days for embeddings/extractions)
  - Gracefully degrades if Redis is unavailable

### 3. Storage Layer
- **qdrant_store.py**: Vector storage (Qdrant)
- **neo4j_store.py**: Graph storage (Neo4j)
- **elasticsearch_store.py**: Full-text search storage (Elasticsearch)

### 4. Orchestration Layer
- **kg_builder.py**: Main pipeline orchestrator
- **graphrag.py**: Search and retrieval system

### 5. Application Layer
- **main.py**: Entry point
- **example.py**: Usage examples

## Data Flow

### Building Phase:
```
Text → Chunker → Chunks
                ↓
            Embeddings → Redis Cache (if cached) → Qdrant
                ↓                    ↓
            (if not cached)    OpenAI API
                ↓
            Extractor → Redis Cache (if cached) → Entities/Relationships → Neo4j
                ↓                    ↓
            (if not cached)    OpenAI API
```

### Search Phase:
```
Query → Embedding → Redis Cache (if cached) → Qdrant Search → Relevant Chunks
                ↓                    ↓                              ↓
            (if not cached)    OpenAI API                    Neo4j Traversal → Related Entities
                                                                        ↓
                                                                Context Building → LLM → Answer
```

## Overall Flow: Upload and Search Operations

This section provides a detailed walkthrough of what happens during the two main operations: uploading documents and searching the knowledge graph.

### Upload Flow (Document Processing)

When a PDF is uploaded, the system processes it through the following steps:

#### 1. **Initialization Phase**
- Initialize Redis cache connection (gracefully degrades if unavailable)
- Initialize Knowledge Graph Builder with all storage backends:
  - Qdrant (vector store)
  - Neo4j (graph store)
  - Elasticsearch (full-text search store)
- Optionally clear existing data if `clear_existing` flag is set

#### 2. **PDF Processing Phase**
- **PDF Reading**: Extract text from PDF file using PDF reader
- **Batch Creation**: Split PDF into page batches (default: 10 pages per batch)
- **Parallel Text Extraction**: Process multiple batches concurrently using ThreadPoolExecutor
  - Each batch extracts text from its assigned page range
  - Results are collected and ordered by batch index

#### 3. **Knowledge Graph Building Phase** (Async Batch Processing)
For each text batch, the following steps occur in parallel (up to `max_concurrent_batches`):

   **Step 3.1: Text Chunking**
   - Split text into overlapping chunks (default: 500 chars with 100 char overlap)
   - Each chunk gets metadata: `chunk_index`, `start_char`, `end_char`
   - Generate unique `chunk_id` for each chunk

   **Step 3.2: Embedding Generation** (Parallel with Extraction)
   - For each chunk text:
     - Check Redis cache first using hash-based key
     - If cached: return cached embedding (fast path)
     - If not cached: call OpenAI API to generate embedding
     - Cache the result in Redis (TTL: 7 days)
   - Process embeddings in batches for efficiency

   **Step 3.3: Entity/Relationship Extraction** (Parallel with Embeddings)
   - For each chunk text:
     - Check Redis cache first using hash-based key
     - If cached: return cached extraction result (fast path)
     - If not cached: call OpenAI LLM API to extract entities and relationships
     - Cache the result in Redis (TTL: 7 days)
   - Process extractions in batches for efficiency

   **Step 3.4: Storage Operations** (Parallel)
   - **Qdrant Storage**: Store chunks with their embeddings as vectors
     - Enables semantic similarity search
   - **Elasticsearch Storage**: Index chunks for full-text keyword search
     - Enables fast keyword-based retrieval
   - **Neo4j Storage**: 
     - Create chunk nodes with metadata
     - Create entity nodes (Person, Organization, Law, Case, etc.)
     - Create relationships between entities (SUES, REPRESENTS, CITES, etc.)
     - Link entities to their source chunks
     - Enables graph traversal and relationship queries

#### 4. **Completion Phase**
- Aggregate statistics:
  - Total batches processed
  - Total chunks created
  - Total entities extracted
  - Total relationships extracted
- Log completion status

**Key Optimizations:**
- **Caching**: Redis caches expensive LLM operations (embeddings, extractions)
- **Parallelism**: Multiple batches processed concurrently
- **Async Operations**: Embedding and extraction happen in parallel within each batch
- **Batch Processing**: Efficient handling of large documents

### Search Flow (Query Processing)

When a search query is executed, the system follows this process:

#### 1. **Initialization Phase**
- Initialize Redis cache connection
- Initialize Knowledge Graph Builder (connects to existing stores)
- Initialize GraphRAG search system with:
  - Vector store (Qdrant)
  - Graph store (Neo4j)
  - Full-text store (Elasticsearch, if hybrid search enabled)
  - Embedding generator with caching

#### 2. **Cache Check Phase**
- Generate cache key from query + search parameters
- Check Redis cache for previous search results
- If cached: return cached result immediately (fast path, TTL: 1 hour)

#### 3. **Search Phase** (if not cached)

   **Step 3.1: Query Embedding**
   - Check Redis cache for query embedding
   - If not cached: generate embedding using OpenAI API
   - Cache the embedding for future use

   **Step 3.2: Chunk Retrieval** (Hybrid or Vector-only)
   
   **If Hybrid Search Enabled:**
   - **Vector Search**: 
     - Search Qdrant using query embedding
     - Retrieve top `top_k * 2` similar chunks (expanded for fusion)
   - **Keyword Search**:
     - Search Elasticsearch using full-text query
     - Retrieve top `top_k * 2` matching chunks
   - **Result Fusion**:
     - Combine vector and keyword results
     - Normalize scores from both sources
     - Weighted combination: `vector_score * vector_weight + keyword_score * keyword_weight`
     - Sort by combined score
     - Select top `top_k` chunks

   **If Vector-Only Search:**
   - Search Qdrant using query embedding
   - Retrieve top `top_k` similar chunks

#### 4. **Graph Traversal Phase**
- Extract `chunk_id`s from retrieved chunks
- Query Neo4j to find entities connected to these chunks
- Traverse graph up to `max_depth` levels:
  - Level 1: Entities directly linked to chunks
  - Level 2+: Entities connected to Level 1 entities via relationships
- Collect all related entities and their relationships

#### 5. **Context Building Phase**
- Combine information from:
  - **Chunk Text**: Actual text content from retrieved chunks
  - **Entity Information**: Names, types, and properties of related entities
  - **Relationship Information**: Connections between entities
- Format context for LLM consumption

#### 6. **Answer Generation Phase**
- Send query + context to OpenAI LLM (GPT-4)
- LLM generates comprehensive answer based on:
  - Relevant chunk text (semantic matches)
  - Related entities and relationships (graph context)
  - Query intent
- Return structured answer

#### 7. **Result Caching Phase**
- Cache complete search result in Redis
- Include: answer, chunks used, entities found, context
- TTL: 1 hour (configurable)

#### 8. **Response Phase**
- Return result with:
  - Generated answer
  - Number of chunks used
  - Number of entities found
  - Search type (hybrid or vector-only)
  - Full context (for debugging/transparency)

**Key Features:**
- **Multi-Modal Search**: Combines semantic (vector), keyword (full-text), and graph (relationships)
- **Intelligent Caching**: Caches at multiple levels (embeddings, extractions, search results)
- **Graph-Enhanced Answers**: Leverages entity relationships for richer context
- **Configurable**: Adjustable weights, depths, and result counts

## Key Features

1. **Custom Implementation**: Built from scratch, no dependencies on neo4j_graphrag
2. **Dual Storage**: Qdrant for vectors, Neo4j for graph, Elasticsearch for full-text search
3. **Redis Caching**: Intelligent caching layer for embeddings and entity extractions
   - Reduces OpenAI API calls and costs
   - Improves response times for repeated operations
   - Graceful degradation if Redis is unavailable
4. **LLM-Powered**: Uses GPT for extraction and answer generation
5. **Configurable**: All parameters customizable
6. **Scalable**: Handles large documents efficiently

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
│   │   ├── neo4j_store.py   # Neo4j graph store
│   │   ├── elasticsearch_store.py  # Elasticsearch full-text store
│   │   └── redis_cache.py   # Redis caching layer
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
- **embeddings.py**: Generates vector embeddings using OpenAI (with Redis caching)
- **entity_extractor.py**: Extracts entities and relationships using LLM (with Redis caching)

### Storage (`src/storage/`)
Storage backends for vectors, graphs, and caching:
- **qdrant_store.py**: Vector storage using Qdrant
- **neo4j_store.py**: Graph storage using Neo4j
- **elasticsearch_store.py**: Full-text search using Elasticsearch
- **redis_cache.py**: Redis-based caching for embeddings and entity extractions
  - Caches expensive LLM operations (embeddings, extractions)
  - Configurable TTL per cache type
  - Automatic key generation with hashing for long keys
  - Supports both sync and async operations

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

