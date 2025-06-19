# API Reference

## CodeIndexer Class

The main class that orchestrates the entire indexing and querying process.

### Constructor

```python
CodeIndexer()
```

Creates a new instance of the code indexer with automatic connection setup to Neo4j and OpenAI.

**Raises**:
- `ValueError`: If required environment variables are missing
- `Exception`: If database or API connections fail

### Methods

#### `index_folder(folder_path: str) -> None`

Index a complete folder/project.

**Parameters**:
- `folder_path` (str): Path to the project folder to index

**Example**:
```python
indexer = CodeIndexer()
indexer.index_folder('/path/to/project')
```

#### `detect_project_type(folder_path: str) -> str`

Automatically detect the project type based on files and structure.

**Parameters**:
- `folder_path` (str): Path to analyze

**Returns**:
- `str`: Project type ('python', 'nodejs', or 'other')

**Example**:
```python
project_type = indexer.detect_project_type('./my-project')
print(f"Detected: {project_type}")
```

#### `chunk_code(folder_path: str, project_type: str) -> Dict[str, Any]`

Chunk code using the appropriate language-specific chunker.

**Parameters**:
- `folder_path` (str): Path to the project
- `project_type` (str): Type of project ('python' or 'nodejs')

**Returns**:
- `Dict[str, Any]`: Graph data with 'nodes' and 'relationships' keys

**Example**:
```python
graph = indexer.chunk_code('./project', 'python')
print(f"Found {len(graph['nodes'])} nodes")
```

#### `load_to_neo4j(graph: Dict[str, Any]) -> None`

Load graph data into Neo4j database.

**Parameters**:
- `graph` (Dict[str, Any]): Graph data from chunker

**Example**:
```python
graph = indexer.chunk_code('./project', 'python')
indexer.load_to_neo4j(graph)
```

#### `generate_descriptions() -> None`

Generate AI descriptions for nodes using OpenAI GPT.

**Note**: Processes up to 100 nodes per call to manage API costs.

**Example**:
```python
indexer.generate_descriptions()
```

#### `generate_embeddings() -> None`

Generate vector embeddings for nodes using OpenAI embeddings API.

**Note**: Processes up to 100 nodes per call to manage API costs.

**Example**:
```python
indexer.generate_embeddings()
```

#### `query_code(query: str, max_results: int = 10) -> List[Dict[str, Any]]`

Perform semantic search on indexed code.

**Parameters**:
- `query` (str): Natural language search query
- `max_results` (int, optional): Maximum number of results. Defaults to 10.

**Returns**:
- `List[Dict[str, Any]]`: Search results with similarity scores and context

**Example**:
```python
results = indexer.query_code("authentication functions", max_results=5)
for result in results:
    print(f"{result['node']['name']}: {result['similarity']:.3f}")
```

#### `close() -> None`

Close database connections and clean up resources.

**Example**:
```python
try:
    indexer = CodeIndexer()
    # ... use indexer
finally:
    indexer.close()
```

### Private Methods

#### `_chunk_python_code(folder_path: str) -> Dict[str, Any]`

Internal method to chunk Python code using the Python chunker.

#### `_chunk_nodejs_code(folder_path: str) -> Dict[str, Any]`

Internal method to chunk Node.js code using the Node.js chunker.

#### `_generate_node_description(node_data: Dict[str, Any]) -> str`

Generate description for a single node using OpenAI.

#### `_generate_node_embedding(node_data: Dict[str, Any]) -> List[float]`

Generate embedding vector for a single node.

#### `_cosine_similarity(a: List[float], b: List[float]) -> float`

Calculate cosine similarity between two vectors.

#### `_get_node_context(session, node_id: str, depth: int = 3) -> Dict[str, Any]`

Get context nodes around a specific node.

## Data Structures

### Graph Structure

The graph data returned by chunkers follows this structure:

```python
{
    "nodes": [
        {
            "id": "unique_node_id",
            "type": "Class|Method|Function|File|Folder|Variable|Import|ExternalLibrary",
            "name": "node_name",
            "description": "AI_generated_description",  # Optional
            "embedding": [0.1, 0.2, ...],  # Optional, 1536 dimensions
            # Type-specific properties...
        }
    ],
    "relationships": [
        {
            "id": "unique_relationship_id",
            "type": "CONTAINS|IMPORTS|CALLS|EXTENDS|REFERENCES|DECLARES",
            "source": "source_node_id",
            "target": "target_node_id",
            # Relationship-specific properties...
        }
    ]
}
```

### Node Types

#### Folder Node
```python
{
    "id": "folder_unique_id",
    "type": "Folder",
    "name": "folder_name",
    "path": "/absolute/path",
    "file_count": 10,
    "subfolder_count": 3,
    "description": "AI description",  # Optional
    "embedding": [...]  # Optional
}
```

#### File Node
```python
{
    "id": "file_unique_id",
    "type": "File",
    "name": "filename.py",
    "path": "/absolute/path/filename.py",
    "extension": ".py",
    "size": 2048,
    "line_count": 100,
    "content": "file_content",  # If capture_content=True
    "description": "AI description",
    "embedding": [...]
}
```

#### Class Node
```python
{
    "id": "class_unique_id",
    "type": "Class",
    "name": "ClassName",
    "code_scope": "class definition code",
    "line_start": 10,
    "line_end": 50,
    "inheritance": ["BaseClass"],  # Python
    "is_abstract": false,
    "description": "AI description",
    "embedding": [...]
}
```

#### Method Node
```python
{
    "id": "method_unique_id",
    "type": "Method",
    "name": "method_name",
    "code_scope": "method code",
    "line_start": 15,
    "line_end": 25,
    "is_static": false,
    "is_private": false,
    "parameters": ["self", "param1"],
    "return_type": "str",  # If available
    "description": "AI description",
    "embedding": [...]
}
```

#### Function Node
```python
{
    "id": "function_unique_id",
    "type": "Function",
    "name": "function_name",
    "code_scope": "function code",
    "line_start": 5,
    "line_end": 15,
    "parameters": ["param1", "param2"],
    "return_type": "dict",
    "is_async": false,
    "description": "AI description",
    "embedding": [...]
}
```

#### Variable Node
```python
{
    "id": "var_unique_id",
    "type": "Variable",
    "name": "variable_name",
    "value": "initial_value",  # If simple
    "type": "str",
    "line_number": 8,
    "scope": "global|local|class"
}
```

#### Import Node
```python
{
    "id": "import_unique_id",
    "type": "Import",
    "name": "module_name",
    "alias": "module_alias",  # Optional
    "import_type": "from|import|require",
    "line_number": 2,
    "is_relative": false
}
```

#### External Library Node
```python
{
    "id": "lib_unique_id",
    "type": "ExternalLibrary",
    "name": "library_name",
    "version": "1.2.3",  # If available
    "package_manager": "pip|npm"
}
```

### Relationship Types

#### CONTAINS
```python
{
    "id": "rel_unique_id",
    "type": "CONTAINS",
    "source": "container_node_id",
    "target": "contained_node_id"
}
```

#### IMPORTS
```python
{
    "id": "rel_unique_id",
    "type": "IMPORTS",
    "source": "file_node_id",
    "target": "imported_node_id",
    "alias": "import_alias",  # Optional
    "line_number": 5
}
```

#### CALLS
```python
{
    "id": "rel_unique_id",
    "type": "CALLS",
    "source": "caller_node_id",
    "target": "called_node_id",
    "call_count": 3,  # Optional
    "line_numbers": [10, 15, 20]  # Optional
}
```

#### EXTENDS
```python
{
    "id": "rel_unique_id",
    "type": "EXTENDS",
    "source": "child_class_id",
    "target": "parent_class_id"
}
```

### Query Results

Query results from `query_code()` have this structure:

```python
[
    {
        "node": {
            # Full node data as above
        },
        "similarity": 0.8542,  # Cosine similarity score (0-1)
        "context": [
            {
                "id": "related_node_id",
                "name": "related_name",
                "type": "related_type",
                "description": "related_description"
            },
            # ... more context nodes
        ]
    },
    # ... more results
]
```

## Configuration Constants

### Python Chunker Configuration

From `src/agentic_code_indexer/python-chunker/constants.py`:

```python
DEFAULT_CONFIG = {
    'include_variables': False,
    'include_imports': True,
    'include_folders': True,
    'include_files': True,
    'include_classes': True,
    'include_methods': True,
    'include_functions': True,
    'ignore_venv': True,
    'track_external_libraries': False,
    'capture_content': True
}

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

RELATIONSHIP_TYPES = {
    'CONTAINS': 'CONTAINS',
    'IMPORTS': 'IMPORTS',
    'CALLS': 'CALLS',
    'EXTENDS': 'EXTENDS',
    'REFERENCES': 'REFERENCES',
    'DECLARES': 'DECLARES'
}
```

### Node.js Chunker Configuration

The Node.js chunker accepts these command-line options:

```bash
node main.js [folder] [options]

Options:
  --capture-content=true/false    Capture source code content
  --include-variables=true/false  Include variable nodes
  --track-external=true/false     Track external libraries
```

## Environment Variables

Required environment variables in `.env` file:

```env
# OpenAI Configuration
OPENAI_API_KEY=your_api_key_here

# Neo4j Configuration  
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password

# Optional: Custom model configurations
OPENAI_EMBEDDING_MODEL=text-embedding-ada-002
OPENAI_COMPLETION_MODEL=gpt-3.5-turbo
```

## Error Handling

### Common Exceptions

#### `ValueError`
Raised when:
- Required environment variables are missing
- Invalid parameters are provided

#### `ConnectionError`
Raised when:
- Neo4j database connection fails
- Network issues with OpenAI API

#### `openai.RateLimitError`
Raised when:
- OpenAI API rate limits are exceeded
- Insufficient API credits

#### `SyntaxError`
Raised when:
- Source code has syntax errors during parsing
- Malformed configuration files

### Exception Handling Example

```python
try:
    indexer = CodeIndexer()
    indexer.index_folder('./my-project')
    
    results = indexer.query_code("search query")
    
except ValueError as e:
    print(f"Configuration error: {e}")
except ConnectionError as e:
    print(f"Connection failed: {e}")
except Exception as e:
    print(f"Unexpected error: {e}")
finally:
    if 'indexer' in locals():
        indexer.close()
```

## Usage Patterns

### Context Manager Pattern

```python
class CodeIndexerContext:
    def __enter__(self):
        self.indexer = CodeIndexer()
        return self.indexer
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.indexer.close()

# Usage
with CodeIndexerContext() as indexer:
    indexer.index_folder('./project')
    results = indexer.query_code("search terms")
```

### Batch Processing Pattern

```python
def process_multiple_projects(project_paths):
    indexer = CodeIndexer()
    try:
        for path in project_paths:
            print(f"Processing {path}...")
            indexer.index_folder(path)
            
        # Query across all indexed projects
        results = indexer.query_code("common patterns")
        return results
    finally:
        indexer.close()
```

### Custom Configuration Pattern

```python
class ConfigurableIndexer(CodeIndexer):
    def __init__(self, config=None):
        super().__init__()
        self.config = config or {}
    
    def index_with_config(self, folder_path):
        # Apply custom configuration
        project_type = self.detect_project_type(folder_path)
        
        if project_type == 'python':
            # Pass config to Python chunker
            pass
        elif project_type == 'nodejs':
            # Pass config to Node.js chunker
            pass
``` 