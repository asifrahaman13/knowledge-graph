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
src/
├── __init__.py           # Package initialization
├── text_chunker.py       # Text chunking logic
├── embeddings.py         # Embedding generation
├── entity_extractor.py   # Entity/relationship extraction
├── qdrant_store.py       # Qdrant vector store
├── neo4j_store.py        # Neo4j graph store
├── kg_builder.py         # Main pipeline
├── graphrag.py           # GraphRAG search
├── main.py               # Entry point
├── example.py            # Usage examples
├── requirements.txt      # Dependencies
├── README.md             # Documentation
└── ARCHITECTURE.md       # This file
```

