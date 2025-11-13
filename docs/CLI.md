# CLI Reference

Complete command-line interface reference for the Knowledge Graph Builder.

## Overview

The CLI provides two main commands:
- `upload` - Process PDF files and build knowledge graphs
- `search` - Query the knowledge graph

## General Syntax

```bash
python src/main.py <command> [arguments] [options]
```

## Commands

### delete

Delete all data from both Qdrant vector database and Neo4j graph database.

**Syntax:**
```bash
python src/main.py delete [--confirm]
```

**Options:**

| Option | Type | Required | Description |
|--------|------|----------|-------------|
| `--confirm` | flag | Yes | Confirmation flag required to proceed with deletion |

**Examples:**

```bash
# Attempt deletion without confirmation (shows warning)
python src/main.py delete

# Delete all data with confirmation
python src/main.py delete --confirm
```

**Output:**
- Warning message if `--confirm` is not provided
- Confirmation of data deletion from both databases
- Success message upon completion

**Safety:**
- The `--confirm` flag is required to prevent accidental deletions
- Without the flag, the command will only display a warning message
- This operation is irreversible

### upload

Upload and process PDF files to build the knowledge graph.

**Syntax:**
```bash
python src/main.py upload <pdf_path> [options]
```

**Arguments:**
- `pdf_path` (required) - Path to the PDF file to process

**Options:**

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--chunk-size` | int | 500 | Size of text chunks in characters |
| `--chunk-overlap` | int | 100 | Overlap between chunks in characters |
| `--pages-per-batch` | int | 10 | Number of pages to process per batch |
| `--max-concurrent-batches` | int | 3 | Maximum concurrent batch processing |
| `--clear` | flag | False | Clear existing data before uploading |

**Examples:**

```bash
# Basic upload
python src/main.py upload static/docs/note.pdf

# Upload with custom chunk size
python src/main.py upload document.pdf --chunk-size 1000 --chunk-overlap 200

# Upload with custom batch settings
python src/main.py upload document.pdf --pages-per-batch 5 --max-concurrent-batches 5

# Clear and upload
python src/main.py upload document.pdf --clear

# Full example with all options
python src/main.py upload document.pdf \
    --chunk-size 800 \
    --chunk-overlap 150 \
    --pages-per-batch 15 \
    --max-concurrent-batches 4 \
    --clear
```

**Output:**
- Progress information for each batch
- Total chunks created
- Total entities extracted
- Total relationships extracted

### search

Search the knowledge graph using natural language queries.

**Syntax:**
```bash
python src/main.py search "<query>" [options]
```

**Arguments:**
- `query` (required) - Search query (use quotes for multi-word queries)

**Options:**

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| `--top-k` | int | 5 | Number of top chunks to retrieve |
| `--max-depth` | int | 2 | Maximum graph traversal depth |

**Examples:**

```bash
# Basic search
python src/main.py search "What is Kleros?"

# Search with more chunks
python src/main.py search "What are the main concepts?" --top-k 10

# Search with deeper graph traversal
python src/main.py search "How does X relate to Y?" --max-depth 3

# Complex query
python src/main.py search "What are the relationships between A and B?" \
    --top-k 15 \
    --max-depth 4
```

**Output:**
- Query being processed
- Generated answer
- Number of chunks used
- Number of entities found

## Help Commands

### General Help

```bash
python src/main.py --help
```

Displays:
- Available commands
- General usage information

### Command-Specific Help

```bash
python src/main.py upload --help
python src/main.py search --help
```

Displays:
- Command-specific arguments and options
- Detailed descriptions
- Default values

## Option Details

### Upload Options

#### `--chunk-size`

Controls the size of text chunks. Larger chunks provide more context but may be less precise.

- **Small (300-500)**: Better for detailed analysis, more chunks
- **Medium (500-800)**: Balanced approach (default)
- **Large (800-1500)**: Better for broader context, fewer chunks

#### `--chunk-overlap`

Overlap between chunks helps maintain context across boundaries.

- **Low (50-100)**: Less redundancy, faster processing
- **Medium (100-200)**: Balanced (default)
- **High (200-300)**: Better context preservation, slower processing

#### `--pages-per-batch`

Number of PDF pages processed in each batch. Affects memory usage and processing speed.

- **Small (5-10)**: Lower memory, more batches
- **Medium (10-20)**: Balanced (default)
- **Large (20-50)**: Higher memory, fewer batches

#### `--max-concurrent-batches`

Maximum number of batches processed in parallel. Affects API rate limits and processing speed.

- **Low (1-2)**: Safer for API limits, slower
- **Medium (3-5)**: Balanced (default)
- **High (5-10)**: Faster but may hit rate limits

#### `--clear`

Clears all existing data before uploading. Useful when:
- Testing different configurations
- Replacing old data
- Starting fresh

**Warning:** This permanently deletes all stored data!

### Search Options

#### `--top-k`

Number of most relevant chunks to retrieve. More chunks provide more context but may include less relevant information.

- **Low (3-5)**: Focused, precise answers
- **Medium (5-10)**: Balanced (default)
- **High (10-20)**: Comprehensive, may include noise

#### `--max-depth`

Maximum depth for graph traversal. Deeper traversal finds more related entities but may include less relevant connections.

- **Shallow (1-2)**: Direct connections only (default)
- **Medium (2-3)**: Extended relationships
- **Deep (3-5)**: Comprehensive graph exploration

## Exit Codes

- `0` - Success
- `1` - Error (invalid arguments, file not found, etc.)
- `2` - Configuration error (missing API keys, etc.)

## Error Messages

### Common Errors

**File not found:**
```
Error: PDF file not found: path/to/file.pdf
```

**Missing API key:**
```
Error: OPENAI_API_KEY not set
```

**Invalid arguments:**
```
usage: main.py upload [-h] [--chunk-size CHUNK_SIZE] ...
main.py upload: error: the following arguments are required: pdf_path
```

**Connection errors:**
```
Failed to connect to Neo4j at neo4j+s://...
Graph storage will be disabled.
```

## Tips

1. **Start with defaults** and adjust based on results
2. **Use quotes** for multi-word search queries
3. **Monitor API usage** when processing large documents
4. **Use `--clear` carefully** - it deletes all data
5. **Adjust batch sizes** based on your system resources
6. **Test with small documents** before processing large ones

## Examples

### Complete Workflow

```bash
# 1. Upload a document
python src/main.py upload document.pdf --clear

# 2. Search for information
python src/main.py search "What is the main topic?"

# 3. Search for relationships
python src/main.py search "How are A and B related?" --max-depth 3

# 4. Upload another document (appends to existing data)
python src/main.py upload another_document.pdf

# 5. Search across all documents
python src/main.py search "What are the common themes?" --top-k 10

# 6. Delete all data (when needed)
python src/main.py delete --confirm
```

### Processing Large Documents

```bash
# Process in smaller batches to manage memory
python src/main.py upload large_document.pdf \
    --pages-per-batch 5 \
    --max-concurrent-batches 2
```

### Fine-Tuned Search

```bash
# Get comprehensive answers with more context
python src/main.py search "Complex question about relationships" \
    --top-k 15 \
    --max-depth 4
```

