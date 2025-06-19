# Architecture and Technical Details

## System Overview

The Agentic Code Indexer follows a modular architecture that separates concerns between code analysis, AI processing, and data storage. The system consists of three main layers:

1. **Analysis Layer**: Language-specific code chunkers
2. **Processing Layer**: AI-powered description and embedding generation
3. **Storage Layer**: Neo4j graph database with semantic search capabilities

```
┌─────────────────────────────────────────────────────────────┐
│                   Code Indexer Main                        │
│                 (code_indexer.py)                          │
└─────────────────┬─────────────────┬─────────────────────────┘
                  │                 │
         ┌────────▼────────┐       ┌▼──────────────────┐
         │  Python Chunker │       │   Node.js Chunker │
         │                 │       │                   │
         │ ├── scanner.py  │       │ ├── scanner.js    │
         │ ├── ast_analyzer│       │ ├── js-scanner.js │
         │ └── exporters.py│       │ └── exporters.js  │
         └─────────────────┘       └───────────────────┘
                  │                         │
                  └──────────┬──────────────┘
                             │
            ┌────────────────▼────────────────┐
            │          Neo4j Database         │
            │     ┌─────────────────────┐     │
            │     │   Graph Storage     │     │
            │     │  ┌─────────────────┐│     │
            │     │  │ Nodes & Rels   ││     │
            │     │  │ Descriptions   ││     │
            │     │  │ Embeddings     ││     │
            │     │  └─────────────────┘│     │
            │     └─────────────────────┘     │
            └─────────────────────────────────┘
                             │
            ┌────────────────▼────────────────┐
            │         OpenAI API              │
            │  ┌─────────────────────────┐    │
            │  │  GPT-3.5 Descriptions   │    │
            │  │  Ada-002 Embeddings     │    │
            │  └─────────────────────────┘    │
            └─────────────────────────────────┘
```

## Core Components

### 1. Main Orchestrator (`code_indexer.py`)

The main entry point that coordinates the entire indexing and querying process:

- **Project Detection**: Automatically identifies Python, Node.js, or other project types
- **Chunker Coordination**: Delegates to appropriate language-specific chunkers
- **AI Integration**: Manages OpenAI API calls for descriptions and embeddings
- **Neo4j Management**: Handles database operations and schema management
- **Query Processing**: Implements semantic search with cosine similarity

### 2. Python Chunker

Located in `src/agentic_code_indexer/python-chunker/`:

#### Core Modules:

- **`scanner.py`**: File system traversal and dependency detection
- **`ast_analyzer.py`**: Python AST parsing and code structure extraction
- **`helpers.py`**: Utility functions for node and relationship creation
- **`exporters.py`**: JSON and Neo4j Cypher export functionality
- **`constants.py`**: Configuration constants and node type definitions

#### Analysis Capabilities:

```python
# Node types extracted:
NODE_TYPES = {
    'FOLDER': 'Folder',
    'FILE': 'File', 
    'CLASS': 'Class',
    'METHOD': 'Method',
    'FUNCTION': 'Function',
    'VARIABLE': 'Variable',
    'IMPORT': 'Import',
    'EXTERNAL_LIBRARY': 'ExternalLibrary'
}

# Relationship types tracked:
RELATIONSHIP_TYPES = {
    'CONTAINS': 'CONTAINS',
    'IMPORTS': 'IMPORTS',
    'CALLS': 'CALLS',
    'EXTENDS': 'EXTENDS',
    'REFERENCES': 'REFERENCES',
    'DECLARES': 'DECLARES'
}
```

### 3. Node.js Chunker

Located in `src/agentic_code_indexer/nodejs-chunker/`:

#### Core Modules:

- **`main.js`**: Entry point and command-line interface
- **`js-scanner.js`**: Babel-powered JavaScript/TypeScript AST analysis
- **`scanner.js`**: File system scanning and project structure analysis
- **`ast.js`**: AST traversal utilities and node extraction
- **`exporters.js`**: JSON and Neo4j export functionality
- **`helpers.js`**: Utility functions and data processing

#### Analysis Capabilities:

- **ES6+ Support**: Modern JavaScript syntax including classes, arrow functions, destructuring
- **TypeScript Support**: Type annotations and TypeScript-specific constructs
- **Module Systems**: ES6 imports/exports and CommonJS require/module.exports
- **Framework Detection**: React components, Express routes, etc.

## Data Model

### Node Schema

Each node in the graph database contains:

```javascript
{
  id: "unique_identifier",           // UUID or generated ID
  type: "Class|Method|Function|File", // Node type classification
  name: "entity_name",               // Display name
  description: "AI_generated_desc",   // LLM-generated description
  embedding: [0.1, 0.2, ...],       // Vector embedding (1536 dimensions)
  
  // Type-specific properties:
  code_scope: "actual_code",         // Code content for functions/methods
  content: "file_content",           // Full content for files
  line_count: 42,                    // Number of lines
  size: 1024,                        // File size in bytes
  file_path: "/path/to/file",        // Absolute file path
  inheritance: ["BaseClass"],        // Parent classes
  external_libraries: ["requests"]   // Dependencies
}
```

### Relationship Schema

Relationships connect nodes with typed edges:

```javascript
{
  id: "relationship_id",
  type: "CONTAINS|IMPORTS|CALLS|EXTENDS",
  source: "source_node_id",
  target: "target_node_id",
  
  // Optional properties:
  call_count: 5,           // Number of calls (for CALLS relationships)
  import_alias: "pd",      // Import alias (for IMPORTS relationships)
  line_number: 42          // Source line number
}
```

### Database Constraints and Indexes

The system creates optimized database schema:

```cypher
-- Unique constraints
CREATE CONSTRAINT IF NOT EXISTS FOR (n:Folder) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (n:File) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (n:Class) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (n:Method) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT IF NOT EXISTS FOR (n:Function) REQUIRE n.id IS UNIQUE;

-- Performance indexes
CREATE INDEX IF NOT EXISTS FOR (n:Folder) ON (n.name);
CREATE INDEX IF NOT EXISTS FOR (n:File) ON (n.name);
CREATE INDEX IF NOT EXISTS FOR (n:Class) ON (n.name);
```

## AI Integration

### Description Generation

Uses OpenAI GPT-3.5-turbo for natural language descriptions:

```python
def _generate_node_description(self, node_data: Dict[str, Any]) -> str:
    prompt = f"""
    Analyze the following {node_type.lower()} named "{node_name}" 
    and provide a concise description of its purpose and functionality.
    
    Code:
    {code_content}
    
    Please provide a brief, clear description (1-2 sentences) 
    that explains what this {node_type.lower()} does.
    """
    
    response = self.openai_client.chat.completions.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "You are a code analysis assistant."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=200,
        temperature=0.3
    )
```

### Embedding Generation

Uses OpenAI text-embedding-ada-002 for semantic vectors:

```python
def _generate_node_embedding(self, node_data: Dict[str, Any]) -> List[float]:
    # Combine relevant text fields
    text_parts = [node_name, description, code_scope, content]
    text_to_embed = ' '.join(part for part in text_parts if part)
    
    # Truncate to model limits
    if len(text_to_embed) > 8000:
        text_to_embed = text_to_embed[:8000]
    
    response = self.openai_client.embeddings.create(
        model="text-embedding-ada-002",
        input=text_to_embed
    )
    
    return response.data[0].embedding
```

## Search Algorithm

### Semantic Search Process

1. **Query Embedding**: Convert search query to vector using same embedding model
2. **Similarity Calculation**: Compute cosine similarity against all stored embeddings
3. **Ranking**: Sort results by similarity score (descending)
4. **Context Expansion**: Retrieve related nodes within configurable depth
5. **Result Formatting**: Package results with node data and context

```python
def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
    """Calculate cosine similarity between two vectors"""
    a = np.array(a)
    b = np.array(b)
    return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))
```

### Context Expansion

Retrieves related nodes using graph traversal:

```cypher
MATCH (start {id: $node_id})
CALL apoc.path.subgraphNodes(start, {
    relationshipFilter: '<|>',
    minLevel: 0,
    maxLevel: 3
}) YIELD node
RETURN node.id, node.name, node.type, node.description
```

## Performance Characteristics

### Indexing Performance

- **Python Projects**: ~1000 nodes/minute (depends on AI API latency)
- **Node.js Projects**: ~800 nodes/minute (Babel parsing overhead)
- **Bottlenecks**: OpenAI API rate limits (3000 RPM for embeddings)

### Query Performance

- **Vector Search**: O(n) similarity calculation, sub-second for <10k nodes
- **Graph Traversal**: Optimized with Neo4j indexes, ~50ms for context expansion
- **Memory Usage**: ~1GB for 10k nodes with embeddings

### Scalability Considerations

1. **Horizontal Scaling**: Process multiple projects in parallel
2. **Batch Processing**: Group API calls to optimize throughput
3. **Incremental Updates**: Track file modifications for selective re-indexing
4. **Caching**: Cache embeddings and descriptions to avoid re-computation

## Error Handling and Resilience

### Fault Tolerance

- **API Failures**: Exponential backoff with retry logic
- **Database Disconnects**: Connection pooling and automatic reconnection
- **Parsing Errors**: Skip problematic files, continue processing
- **Memory Limits**: Streaming processing for large files

### Data Consistency

- **Transaction Management**: Use Neo4j transactions for atomic operations
- **Rollback Capabilities**: Clean rollback on indexing failures
- **Validation**: Schema validation before data insertion

## Configuration and Extensibility

### Chunker Configuration

Both chunkers support extensive configuration:

```python
DEFAULT_CONFIG = {
    'include_variables': False,        # Variable extraction (can be noisy)
    'include_imports': True,           # Import relationship tracking
    'track_external_libraries': False, # External dependency analysis
    'capture_content': True,          # Store source code content
    'ignore_venv': True,              # Skip virtual environments
    'max_file_size': 1024 * 1024,    # Skip files larger than 1MB
    'supported_extensions': ['.py', '.js', '.ts']
}
```

### Extending Language Support

To add new language support:

1. Create new chunker module following existing patterns
2. Implement AST parsing for the target language
3. Map language constructs to universal node types
4. Add detection logic to main orchestrator
5. Update configuration and documentation

### Custom Node Types

Add new node types by:

1. Extending `NODE_TYPES` constants
2. Updating database constraints
3. Implementing extraction logic in chunkers
4. Adding display logic in query results

## Security Considerations

### API Key Management

- Store keys in environment variables
- Use key rotation policies
- Monitor API usage and costs
- Implement rate limiting

### Database Security

- Use strong authentication credentials
- Enable SSL/TLS for connections
- Implement proper access controls
- Regular security updates

### Code Privacy

- Local processing by default
- Option to exclude sensitive files
- Configurable content capture
- Clear data retention policies 