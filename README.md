# Custom Knowledge Graph Builder from Scratch

A complete custom implementation of a knowledge graph builder using Qdrant for vector storage and Neo4j for graph storage.

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

## Components

### 1. `text_chunker.py`
- Splits text into manageable chunks
- Configurable chunk size and overlap
- Sentence-aware splitting

### 2. `embeddings.py`
- Generates embeddings using OpenAI
- Supports batch processing
- Configurable embedding model

### 3. `entity_extractor.py`
- Uses LLM to extract entities and relationships
- Returns structured JSON
- Handles 'id' property conflicts

### 4. `qdrant_store.py`
- Manages vector storage in Qdrant
- Stores chunks with embeddings
- Provides similarity search

### 5. `neo4j_store.py`
- Manages graph storage in Neo4j
- Stores entities and relationships
- Provides graph traversal

### 6. `kg_builder.py`
- Main pipeline orchestrator
- Coordinates all components
- Builds complete knowledge graph

### 7. `graphrag.py`
- GraphRAG search implementation
- Combines vector search with graph traversal
- Generates intelligent answers

## Installation

```bash
pip install -r requirements.txt
```

## Configuration

Set environment variables:

```bash
export OPENAI_API_KEY="your-openai-api-key"
export NEO4J_URI="neo4j+s://your-instance.databases.neo4j.io"
export NEO4J_USERNAME="neo4j"
export NEO4J_PASSWORD="your-password"

# Optional: Qdrant cloud
export QDRANT_URL="https://your-cluster.qdrant.io"
export QDRANT_API_KEY="your-qdrant-api-key"
```

## Usage

### Basic Usage

```python
from kg_builder import KnowledgeGraphBuilder
from graphrag import GraphRAG

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

### Advanced Usage

```python
# Custom configuration
kg_builder = KnowledgeGraphBuilder(
    openai_api_key="your-key",
    neo4j_uri="neo4j+s://...",
    neo4j_username="neo4j",
    neo4j_password="password",
    chunk_size=1000,  # Larger chunks
    chunk_overlap=200,  # More overlap
    embedding_model="text-embedding-3-large",  # Better embeddings
    llm_model="gpt-4o"  # Better extraction
)

# GraphRAG with custom parameters
graphrag = GraphRAG(
    openai_api_key="your-key",
    vector_store=kg_builder.vector_store,
    graph_store=kg_builder.graph_store,
    top_k_chunks=10,  # More chunks
    max_depth=3  # Deeper traversal
)
```

## Features

- ✅ **Custom Implementation**: Built from scratch, no dependencies on neo4j_graphrag
- ✅ **Qdrant Integration**: Fast vector similarity search
- ✅ **Neo4j Integration**: Powerful graph traversal
- ✅ **LLM-Powered**: Uses GPT for entity/relationship extraction
- ✅ **Configurable**: All parameters are customizable
- ✅ **Scalable**: Handles large documents efficiently

## How It Works

1. **Text Chunking**: Splits text into manageable pieces
2. **Embedding**: Creates vector representations
3. **Extraction**: LLM extracts entities and relationships
4. **Storage**: Stores chunks in Qdrant, graph in Neo4j
5. **Search**: Combines vector search with graph traversal
6. **Answer Generation**: LLM generates answers from context

## Search Process

1. **Vector Search**: Find similar chunks using embeddings
2. **Graph Traversal**: Get entities connected to relevant chunks
3. **Context Building**: Combine chunk text + entity information
4. **Answer Generation**: LLM generates answer from context

## Notes

- The implementation uses Neo4j driver for graph operations (standard approach)
- Qdrant can run locally or in the cloud
- All LLM calls use OpenAI API
- The system handles 'id' property conflicts automatically

## License

MIT

