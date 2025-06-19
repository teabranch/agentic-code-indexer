# Troubleshooting Guide

## Common Issues and Solutions

### Installation Issues

#### 1. Python Package Conflicts

**Problem**: Conflicting package versions or dependency issues

**Solution**:
```bash
# Use a virtual environment
python -m venv agentic-indexer-env
source agentic-indexer-env/bin/activate  # Linux/Mac
# or
agentic-indexer-env\Scripts\activate     # Windows

pip install --upgrade pip
pip install openai neo4j python-dotenv numpy
```

#### 2. Node.js Version Issues

**Problem**: Incompatible Node.js version

**Solution**:
```bash
# Check current version
node --version

# Install Node.js 16+ from https://nodejs.org/
# Or use nvm (Node Version Manager)
curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.0/install.sh | bash
nvm install 18
nvm use 18

# Install chunker dependencies
cd src/agentic_code_indexer/nodejs-chunker
npm install
```

#### 3. Neo4j Connection Issues

**Problem**: Cannot connect to Neo4j database

**Solutions**:

```python
# Test connection manually
from neo4j import GraphDatabase

try:
    driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "password"))
    with driver.session() as session:
        result = session.run("RETURN 'Connection successful' AS message")
        print(result.single()["message"])
    driver.close()
    print("Neo4j connection successful")
except Exception as e:
    print(f"Connection failed: {e}")
```

**Common fixes**:
- Ensure Neo4j is running: `neo4j status`
- Check firewall settings (port 7687)
- Verify credentials in `.env` file
- For Neo4j AuraDB, use `neo4j+s://` URI scheme

### Runtime Issues

#### 1. OpenAI API Errors

**Problem**: API key invalid or rate limits exceeded

**Error Messages**:
```
openai.error.AuthenticationError: Invalid API key provided
openai.error.RateLimitError: Rate limit reached
```

**Solutions**:
```python
# Check API key validity
import openai
import os
from dotenv import load_dotenv

load_dotenv()
client = openai.OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

try:
    response = client.embeddings.create(
        model="text-embedding-ada-002",
        input="test"
    )
    print("API key is valid")
except Exception as e:
    print(f"API error: {e}")
```

**Rate limit handling**:
```python
import time
import random

def retry_with_backoff(func, max_retries=3):
    for attempt in range(max_retries):
        try:
            return func()
        except openai.RateLimitError:
            if attempt == max_retries - 1:
                raise
            wait_time = (2 ** attempt) + random.uniform(0, 1)
            time.sleep(wait_time)
```

#### 2. Memory Issues with Large Codebases

**Problem**: Out of memory errors during indexing

**Solutions**:

1. **Process in batches**:
```python
def index_large_project(folder_path, batch_size=100):
    indexer = CodeIndexer()
    
    # Get all files first
    all_files = []
    for root, dirs, files in os.walk(folder_path):
        for file in files:
            if file.endswith(('.py', '.js', '.ts')):
                all_files.append(os.path.join(root, file))
    
    # Process in batches
    for i in range(0, len(all_files), batch_size):
        batch = all_files[i:i + batch_size]
        print(f"Processing batch {i//batch_size + 1}/{(len(all_files) + batch_size - 1)//batch_size}")
        
        # Process batch...
        # Implementation depends on chunker modifications
```

2. **Increase system memory limits**:
```python
import resource

# Increase memory limit (Linux/Mac)
resource.setrlimit(resource.RLIMIT_AS, (4 * 1024 * 1024 * 1024, -1))  # 4GB
```

#### 3. File Parsing Errors

**Problem**: Syntax errors in source files causing crashes

**Error Messages**:
```
SyntaxError: invalid syntax (file.py, line 42)
babel.parser.ParserError: Unexpected token
```

**Solutions**:

1. **Graceful error handling in Python chunker**:
```python
def safe_parse_file(file_path):
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            source = f.read()
        
        tree = ast.parse(source, filename=file_path)
        return tree
    except SyntaxError as e:
        logger.warning(f"Syntax error in {file_path}: {e}")
        return None
    except UnicodeDecodeError as e:
        logger.warning(f"Encoding error in {file_path}: {e}")
        return None
```

2. **Skip problematic files**:
```python
def should_skip_file(file_path):
    skip_patterns = [
        '*.min.js',      # Minified files
        '*.bundle.js',   # Bundled files
        '*/node_modules/*',  # Dependencies
        '*/venv/*',      # Virtual environments
        '*/__pycache__/*'    # Python cache
    ]
    
    for pattern in skip_patterns:
        if fnmatch.fnmatch(file_path, pattern):
            return True
    return False
```

### Performance Issues

#### 1. Slow Indexing

**Problem**: Indexing takes too long

**Diagnosis**:
```python
import time
import logging

# Enable detailed logging
logging.basicConfig(level=logging.DEBUG)

# Profile individual steps
start_time = time.time()
graph = indexer.chunk_code(folder_path, project_type)
print(f"Chunking took: {time.time() - start_time:.2f} seconds")

start_time = time.time()
indexer.load_to_neo4j(graph)
print(f"Neo4j loading took: {time.time() - start_time:.2f} seconds")

start_time = time.time()
indexer.generate_descriptions()
print(f"Description generation took: {time.time() - start_time:.2f} seconds")
```

**Solutions**:

1. **Parallel processing**:
```python
from concurrent.futures import ThreadPoolExecutor
import threading

class OptimizedCodeIndexer(CodeIndexer):
    def __init__(self, max_workers=4):
        super().__init__()
        self.max_workers = max_workers
        self.thread_local = threading.local()
    
    def generate_descriptions_parallel(self):
        with self.neo4j_driver.session() as session:
            query = """
            MATCH (n)
            WHERE n:Class OR n:Method OR n:Function OR n:File
            AND NOT EXISTS(n.description)
            RETURN n.id as id, n.type as type, n.name as name, 
                   n.code_scope as code_scope, n.content as content
            LIMIT 100
            """
            
            results = session.run(query)
            nodes_to_process = [record.data() for record in results]
            
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                futures = []
                for node_data in nodes_to_process:
                    future = executor.submit(self._process_node_description, node_data)
                    futures.append(future)
                
                for future in futures:
                    try:
                        future.result(timeout=30)
                    except Exception as e:
                        logger.error(f"Error processing node: {e}")
```

2. **Optimize Neo4j operations**:
```python
def batch_load_to_neo4j(self, graph, batch_size=1000):
    with self.neo4j_driver.session() as session:
        # Load nodes in batches
        nodes = graph['nodes']
        for i in range(0, len(nodes), batch_size):
            batch = nodes[i:i + batch_size]
            
            query = """
            UNWIND $nodes as node
            CALL apoc.merge.node([node.type], {id: node.id}, node) YIELD node as n
            RETURN count(n)
            """
            
            session.run(query, nodes=batch)
```

#### 2. Slow Queries

**Problem**: Semantic search queries are slow

**Diagnosis**:
```python
import time

def profile_query(query_text):
    start_time = time.time()
    
    # Profile embedding generation
    query_embedding = indexer.openai_client.embeddings.create(
        model="text-embedding-ada-002",
        input=query_text
    ).data[0].embedding
    embedding_time = time.time() - start_time
    
    # Profile similarity calculation
    start_time = time.time()
    results = indexer.query_code(query_text, max_results=10)
    total_time = time.time() - start_time
    
    print(f"Embedding generation: {embedding_time:.2f}s")
    print(f"Total query time: {total_time:.2f}s")
    print(f"Results found: {len(results)}")
```

**Solutions**:

1. **Optimize similarity calculation**:
```python
import numpy as np
from scipy.spatial.distance import cosine

def optimized_cosine_similarity(a, b):
    """Faster cosine similarity using scipy"""
    return 1 - cosine(a, b)

# Use vectorized operations for multiple comparisons
def batch_similarity_search(query_embedding, node_embeddings):
    """Vectorized similarity calculation"""
    query_vec = np.array(query_embedding)
    node_vecs = np.array(node_embeddings)
    
    # Normalize vectors
    query_norm = query_vec / np.linalg.norm(query_vec)
    node_norms = node_vecs / np.linalg.norm(node_vecs, axis=1, keepdims=True)
    
    # Calculate similarities
    similarities = np.dot(node_norms, query_norm)
    return similarities
```

2. **Add database indexes**:
```cypher
-- Create indexes for frequently queried properties
CREATE INDEX node_type_index IF NOT EXISTS FOR (n) ON (n.type);
CREATE INDEX node_name_text_index IF NOT EXISTS FOR (n) ON (n.name);
```

### Configuration Issues

#### 1. Environment Variables Not Loading

**Problem**: `.env` file not being read

**Solutions**:

1. **Check file location**:
```python
import os
from pathlib import Path

# .env should be in project root
env_path = Path(__file__).parent / '.env'
print(f"Looking for .env at: {env_path}")
print(f"File exists: {env_path.exists()}")

if env_path.exists():
    with open(env_path) as f:
        print("Contents:")
        print(f.read())
```

2. **Load explicitly**:
```python
from dotenv import load_dotenv
import os

# Load from specific path
load_dotenv('.env')

# Or load from custom location
load_dotenv('/path/to/your/.env')

# Verify loading
print(f"OPENAI_API_KEY loaded: {'OPENAI_API_KEY' in os.environ}")
print(f"NEO4J_URI loaded: {'NEO4J_URI' in os.environ}")
```

#### 2. Chunker Configuration Issues

**Problem**: Chunker not respecting configuration

**Debug configuration**:
```python
def debug_chunker_config():
    from scanner import DEFAULT_CONFIG
    
    print("Default Python chunker config:")
    for key, value in DEFAULT_CONFIG.items():
        print(f"  {key}: {value}")
    
    # Test Node.js chunker
    import subprocess
    result = subprocess.run([
        'node', 'src/agentic_code_indexer/nodejs-chunker/main.js', '--help'
    ], capture_output=True, text=True)
    
    print("\nNode.js chunker help:")
    print(result.stdout)
```

### Data Quality Issues

#### 1. Missing Descriptions or Embeddings

**Problem**: Some nodes don't have AI-generated content

**Diagnosis**:
```cypher
// Check for nodes without descriptions
MATCH (n)
WHERE (n:Class OR n:Method OR n:Function OR n:File)
AND NOT EXISTS(n.description)
RETURN count(n) as nodes_without_descriptions;

// Check for nodes without embeddings
MATCH (n)
WHERE (n:Class OR n:Method OR n:Function OR n:File)
AND NOT EXISTS(n.embedding)
RETURN count(n) as nodes_without_embeddings;
```

**Solutions**:

1. **Regenerate missing content**:
```python
def fix_missing_descriptions(indexer):
    """Regenerate descriptions for nodes that are missing them"""
    with indexer.neo4j_driver.session() as session:
        # Find nodes without descriptions
        query = """
        MATCH (n)
        WHERE (n:Class OR n:Method OR n:Function OR n:File)
        AND NOT EXISTS(n.description)
        RETURN n.id as id, n.type as type, n.name as name,
               n.code_scope as code_scope, n.content as content
        LIMIT 50
        """
        
        results = session.run(query)
        for record in results:
            try:
                node_data = record.data()
                description = indexer._generate_node_description(node_data)
                
                update_query = "MATCH (n {id: $id}) SET n.description = $description"
                session.run(update_query, id=node_data['id'], description=description)
                
                print(f"Fixed description for {node_data['name']}")
            except Exception as e:
                print(f"Error fixing {node_data['id']}: {e}")
```

#### 2. Inconsistent Node Relationships

**Problem**: Missing or incorrect relationships between nodes

**Diagnosis**:
```cypher
// Find files without any CONTAINS relationships
MATCH (f:File)
WHERE NOT EXISTS((f)-[:CONTAINS]->())
AND f.extension IN ['.py', '.js', '.ts']
RETURN f.name, f.path;

// Find classes without methods
MATCH (c:Class)
WHERE NOT EXISTS((c)-[:CONTAINS]->(:Method))
RETURN c.name, c.description;
```

**Solutions**:

1. **Re-run analysis**:
```python
def fix_relationships(indexer, file_path):
    """Re-analyze a specific file to fix relationships"""
    project_type = indexer.detect_project_type(os.path.dirname(file_path))
    
    if project_type == 'python':
        # Re-run Python analysis for this file
        graph = indexer._chunk_python_code(os.path.dirname(file_path))
    elif project_type == 'nodejs':
        # Re-run Node.js analysis
        graph = indexer._chunk_nodejs_code(os.path.dirname(file_path))
    
    # Update relationships in Neo4j
    indexer.load_to_neo4j(graph)
```

## Debugging Tools

### 1. Enable Debug Logging

```python
import logging

# Set up detailed logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('indexer_debug.log'),
        logging.StreamHandler()
    ]
)

# Enable specific loggers
logging.getLogger('neo4j').setLevel(logging.DEBUG)
logging.getLogger('openai').setLevel(logging.DEBUG)
```

### 2. Health Check Script

```python
#!/usr/bin/env python3
"""Health check script for Agentic Code Indexer"""

import os
import sys
from pathlib import Path

def health_check():
    """Comprehensive health check"""
    issues = []
    
    # Check Python dependencies
    try:
        import openai
        import neo4j
        import numpy as np
        from dotenv import load_dotenv
        print("✓ Python dependencies installed")
    except ImportError as e:
        issues.append(f"Missing Python dependency: {e}")
    
    # Check environment variables
    load_dotenv()
    required_env_vars = ['OPENAI_API_KEY', 'NEO4J_URI', 'NEO4J_USER', 'NEO4J_PASSWORD']
    for var in required_env_vars:
        if not os.getenv(var):
            issues.append(f"Missing environment variable: {var}")
    
    if not issues:
        print("✓ Environment variables configured")
    
    # Check Neo4j connection
    try:
        from neo4j import GraphDatabase
        driver = GraphDatabase.driver(
            os.getenv('NEO4J_URI'), 
            auth=(os.getenv('NEO4J_USER'), os.getenv('NEO4J_PASSWORD'))
        )
        with driver.session() as session:
            session.run("RETURN 1")
        driver.close()
        print("✓ Neo4j connection successful")
    except Exception as e:
        issues.append(f"Neo4j connection failed: {e}")
    
    # Check OpenAI API
    try:
        import openai
        client = openai.OpenAI(api_key=os.getenv('OPENAI_API_KEY'))
        client.embeddings.create(model="text-embedding-ada-002", input="test")
        print("✓ OpenAI API connection successful")
    except Exception as e:
        issues.append(f"OpenAI API failed: {e}")
    
    # Check Node.js chunker
    nodejs_path = Path(__file__).parent / 'src/agentic_code_indexer/nodejs-chunker'
    if (nodejs_path / 'package.json').exists():
        print("✓ Node.js chunker found")
    else:
        issues.append("Node.js chunker not found")
    
    # Report results
    if issues:
        print("\n❌ Issues found:")
        for issue in issues:
            print(f"  - {issue}")
        return False
    else:
        print("\n✅ All checks passed!")
        return True

if __name__ == '__main__':
    success = health_check()
    sys.exit(0 if success else 1)
```

### 3. Performance Profiler

```python
import cProfile
import pstats
from io import StringIO

def profile_indexing(folder_path):
    """Profile the indexing process"""
    pr = cProfile.Profile()
    pr.enable()
    
    # Your indexing code here
    indexer = CodeIndexer()
    indexer.index_folder(folder_path)
    
    pr.disable()
    
    # Generate report
    s = StringIO()
    ps = pstats.Stats(pr, stream=s).sort_stats('cumulative')
    ps.print_stats()
    
    print(s.getvalue())
    
    # Save to file
    ps.dump_stats('indexing_profile.prof')
```

## Getting Help

### 1. Collect System Information

```python
def collect_system_info():
    """Collect system information for bug reports"""
    import platform
    import sys
    
    info = {
        'python_version': sys.version,
        'platform': platform.platform(),
        'architecture': platform.architecture(),
        'processor': platform.processor(),
    }
    
    # Check package versions
    try:
        import openai
        info['openai_version'] = openai.__version__
    except:
        info['openai_version'] = 'Not installed'
    
    try:
        import neo4j
        info['neo4j_version'] = neo4j.__version__
    except:
        info['neo4j_version'] = 'Not installed'
    
    print("System Information:")
    for key, value in info.items():
        print(f"  {key}: {value}")
    
    return info
```

### 2. Create Minimal Reproduction

When reporting issues, create a minimal example:

```python
#!/usr/bin/env python3
"""Minimal reproduction script"""

from src.agentic_code_indexer.code_indexer import CodeIndexer
import tempfile
import os

# Create a minimal test project
with tempfile.TemporaryDirectory() as temp_dir:
    # Create a simple Python file
    test_file = os.path.join(temp_dir, 'test.py')
    with open(test_file, 'w') as f:
        f.write('''
def hello_world():
    """A simple test function"""
    return "Hello, World!"

class TestClass:
    def test_method(self):
        return hello_world()
''')
    
    # Try to index it
    try:
        indexer = CodeIndexer()
        indexer.index_folder(temp_dir)
        print("✓ Indexing successful")
        
        # Try a query
        results = indexer.query_code("hello world function")
        print(f"✓ Query successful: {len(results)} results")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if 'indexer' in locals():
            indexer.close()
``` 