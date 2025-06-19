# Usage Guide

## Command Line Interface

### Basic Commands

#### Index a Project

```bash
# Index the current directory
python src/agentic_code_indexer/code_indexer.py index --folder .

# Index a specific project
python src/agentic_code_indexer/code_indexer.py index --folder /path/to/your/project

# Index with verbose output
python src/agentic_code_indexer/code_indexer.py index --folder ./my-project --verbose
```

#### Query Indexed Code

```bash
# Basic semantic search
python src/agentic_code_indexer/code_indexer.py query --query "authentication functions"

# Limit the number of results
python src/agentic_code_indexer/code_indexer.py query --query "database connection" --max-results 5

# Search for specific patterns
python src/agentic_code_indexer/code_indexer.py query --query "error handling middleware"
```

### Command Line Options

```bash
python src/agentic_code_indexer/code_indexer.py --help

Usage: code_indexer.py [COMMAND] [OPTIONS]

Commands:
  index    Index a code repository
  query    Search indexed code

Index Options:
  --folder PATH    Path to the project folder to index

Query Options:
  --query TEXT         Search query string
  --max-results INT    Maximum number of results to return (default: 10)
```

## Programmatic Usage

### Basic Example

```python
from src.agentic_code_indexer.code_indexer import CodeIndexer

# Initialize the indexer
indexer = CodeIndexer()

try:
    # Index a project
    indexer.index_folder('/path/to/your/project')
    
    # Perform semantic search
    results = indexer.query_code("authentication middleware", max_results=10)
    
    # Process results
    for result in results:
        node = result['node']
        similarity = result['similarity']
        
        print(f"Found: {node['name']} (similarity: {similarity:.3f})")
        print(f"Type: {node['type']}")
        print(f"Description: {node.get('description', 'N/A')}")
        print("-" * 50)
        
finally:
    # Always close connections
    indexer.close()
```

### Advanced Usage

#### Custom Configuration

```python
from src.agentic_code_indexer.code_indexer import CodeIndexer

class CustomCodeIndexer(CodeIndexer):
    def __init__(self, custom_config=None):
        super().__init__()
        self.config = custom_config or {}
    
    def index_with_custom_settings(self, folder_path):
        # Detect project type
        project_type = self.detect_project_type(folder_path)
        
        # Apply custom chunking configuration
        if project_type == 'python':
            graph = self._chunk_python_code_with_config(folder_path)
        elif project_type == 'nodejs':
            graph = self._chunk_nodejs_code_with_config(folder_path)
        
        # Continue with standard indexing
        self.load_to_neo4j(graph)
        self.generate_descriptions()
        self.generate_embeddings()

# Usage
config = {
    'include_variables': True,
    'track_external_libraries': True,
    'capture_content': True
}

indexer = CustomCodeIndexer(config)
indexer.index_with_custom_settings('./my-project')
```

#### Batch Processing

```python
import os
from pathlib import Path
from src.agentic_code_indexer.code_indexer import CodeIndexer

def index_multiple_projects(project_paths):
    """Index multiple projects in batch"""
    indexer = CodeIndexer()
    
    try:
        for project_path in project_paths:
            if os.path.exists(project_path):
                print(f"Indexing {project_path}...")
                indexer.index_folder(project_path)
                print(f"Completed {project_path}")
            else:
                print(f"Skipping {project_path} - not found")
    finally:
        indexer.close()

# Usage
projects = [
    './project1',
    './project2',
    '/path/to/project3'
]

index_multiple_projects(projects)
```

#### Advanced Querying

```python
from src.agentic_code_indexer.code_indexer import CodeIndexer

def advanced_search_example():
    indexer = CodeIndexer()
    
    try:
        # Multiple related searches
        search_terms = [
            "user authentication",
            "database models",
            "API endpoints",
            "error handling"
        ]
        
        all_results = {}
        
        for term in search_terms:
            results = indexer.query_code(term, max_results=5)
            all_results[term] = results
            
            print(f"\n=== Results for '{term}' ===")
            for i, result in enumerate(results, 1):
                node = result['node']
                print(f"{i}. {node['name']} ({node['type']})")
                print(f"   Similarity: {result['similarity']:.3f}")
                print(f"   Description: {node.get('description', 'N/A')[:100]}...")
        
        return all_results
        
    finally:
        indexer.close()

# Run advanced search
results = advanced_search_example()
```

## Working with Results

### Understanding Search Results

Each search result contains:

```python
{
    'node': {
        'id': 'unique_node_id',
        'name': 'function_name',
        'type': 'Function',
        'description': 'Generated description',
        'code_scope': 'actual_code_content',
        'content': 'file_content_if_file_node'
    },
    'similarity': 0.8542,  # Cosine similarity score
    'context': [
        {
            'id': 'related_node_id',
            'name': 'related_name',
            'type': 'Class',
            'description': 'Related node description'
        }
    ]
}
```

### Processing Different Node Types

```python
def process_search_results(results):
    """Process search results based on node type"""
    
    for result in results:
        node = result['node']
        node_type = node['type']
        
        if node_type == 'Function':
            print(f"Function: {node['name']}")
            if 'code_scope' in node:
                print(f"Code preview: {node['code_scope'][:200]}...")
                
        elif node_type == 'Class':
            print(f"Class: {node['name']}")
            # Show related methods from context
            methods = [ctx for ctx in result['context'] if ctx['type'] == 'Method']
            print(f"Methods: {[m['name'] for m in methods[:5]]}")
            
        elif node_type == 'File':
            print(f"File: {node['name']}")
            print(f"Description: {node.get('description', 'N/A')}")
            
        print(f"Similarity: {result['similarity']:.3f}")
        print("-" * 40)
```

## Integration Examples

### Jupyter Notebook Integration

```python
# In a Jupyter notebook cell
import sys
sys.path.append('/path/to/agentic-code-indexer')

from src.agentic_code_indexer.code_indexer import CodeIndexer
import pandas as pd

def search_and_display(query, max_results=10):
    """Search and display results in a nice format"""
    indexer = CodeIndexer()
    
    try:
        results = indexer.query_code(query, max_results)
        
        # Convert to DataFrame for nice display
        data = []
        for result in results:
            node = result['node']
            data.append({
                'Name': node['name'],
                'Type': node['type'],
                'Similarity': f"{result['similarity']:.3f}",
                'Description': node.get('description', 'N/A')[:100] + '...'
            })
        
        df = pd.DataFrame(data)
        return df.style.set_properties(**{'text-align': 'left'})
        
    finally:
        indexer.close()

# Usage in notebook
search_and_display("authentication functions")
```

### Flask Web API Integration

```python
from flask import Flask, request, jsonify
from src.agentic_code_indexer.code_indexer import CodeIndexer

app = Flask(__name__)
indexer = CodeIndexer()

@app.route('/search', methods=['POST'])
def search_code():
    """API endpoint for code search"""
    try:
        data = request.get_json()
        query = data.get('query')
        max_results = data.get('max_results', 10)
        
        if not query:
            return jsonify({'error': 'Query is required'}), 400
        
        results = indexer.query_code(query, max_results)
        
        # Format results for API response
        formatted_results = []
        for result in results:
            formatted_results.append({
                'name': result['node']['name'],
                'type': result['node']['type'],
                'description': result['node'].get('description'),
                'similarity': result['similarity'],
                'context_count': len(result['context'])
            })
        
        return jsonify({
            'query': query,
            'results': formatted_results,
            'total': len(formatted_results)
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/index', methods=['POST'])
def index_project():
    """API endpoint to index a project"""
    try:
        data = request.get_json()
        folder_path = data.get('folder_path')
        
        if not folder_path:
            return jsonify({'error': 'folder_path is required'}), 400
        
        indexer.index_folder(folder_path)
        
        return jsonify({
            'message': f'Successfully indexed {folder_path}',
            'status': 'completed'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
```

## Best Practices

### 1. Project Organization

- Index projects at the root level for best results
- Ensure clean project structure before indexing
- Consider excluding test files and build directories

### 2. Query Optimization

- Use specific, descriptive queries
- Combine multiple related searches for comprehensive results
- Leverage the context information in results

### 3. Performance Tips

- Index incrementally for large codebases
- Monitor OpenAI API usage and costs
- Use appropriate batch sizes for processing

### 4. Result Interpretation

- Pay attention to similarity scores (higher is better)
- Use context information to understand relationships
- Combine multiple search approaches for thorough analysis 