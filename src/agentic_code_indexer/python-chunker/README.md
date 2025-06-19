# Python Code Indexer

A Python implementation of the agentic code indexer that analyzes Python codebases and generates Neo4j import statements for code structure visualization and analysis.

## Features

- **AST-based Analysis**: Uses Python's built-in `ast` module for accurate code parsing
- **Comprehensive Node Types**: Extracts folders, files, classes, methods, functions, variables, and imports
- **Relationship Mapping**: Tracks relationships like CONTAINS, IMPORTS, CALLS, EXTENDS, REFERENCES, DECLARES
- **External Library Detection**: Identifies and tracks external library dependencies
- **Neo4j Integration**: Generates Cypher statements for direct import into Neo4j
- **JSON Export**: Also exports to JSON format for other analysis tools
- **Configurable**: Flexible configuration options for what to include/exclude

## Usage

### Basic Usage

```bash
# Analyze current directory
python main.py

# Analyze specific directory
python main.py /path/to/your/python/project

# With custom configuration
python main.py ./src --include-variables --track-external-libraries
```

### Command Line Options

```bash
python main.py [ROOT_PATH] [OPTIONS]

Arguments:
  ROOT_PATH                    Root directory of your Python service (default: ./src)

Options:
  --include-variables         Include variable nodes in the graph
  --include-imports           Include import nodes in the graph (default: True)
  --include-folders           Include folder nodes in the graph (default: True)
  --include-files             Include file nodes in the graph (default: True)
  --include-classes           Include class nodes in the graph (default: True)
  --include-methods           Include method nodes in the graph (default: True)
  --include-functions         Include function nodes in the graph (default: True)
  --ignore-venv               Ignore virtual environment directories (default: True)
  --track-external-libraries  Track external library imports
  --capture-content           Capture code content for nodes (default: True)
  --output-json PATH          Output JSON file path (default: ./graph-data.json)
  --output-cypher PATH        Output Cypher file path (default: ./neo4j-import.cypher)
```

### Programmatic Usage

```python
from scanner import scan_python_service
from exporters import export_to_json, export_to_neo4j

# Configure the scanner
config = {
    'include_variables': False,
    'include_imports': True,
    'track_external_libraries': True,
    'capture_content': True
}

# Scan the codebase
graph = scan_python_service('/path/to/project', config)

# Export to JSON
export_to_json(graph, 'output.json')

# Export to Neo4j Cypher
cypher = export_to_neo4j(graph, config)
with open('import.cypher', 'w') as f:
    f.write(cypher)
```

## Node Types

The indexer creates the following types of nodes:

- **Folder**: Directory nodes with file/folder counts
- **File**: Python file nodes with size and line count information
- **Class**: Class definitions with inheritance relationships
- **Method**: Class methods and instance methods
- **Function**: Standalone functions
- **Variable**: Variable assignments (optional)
- **Import**: Import statements (optional)
- **ExternalLibrary**: External package dependencies

## Relationship Types

The following relationships are tracked:

- **CONTAINS**: Folder contains file, file contains class, class contains method, etc.
- **IMPORTS**: File imports external library or internal module
- **CALLS**: Function/method calls another function/method
- **EXTENDS**: Class extends another class (inheritance)
- **REFERENCES**: Variable references another variable
- **DECLARES**: Scope declares a variable

## External Library Detection

The indexer can detect external libraries from:

- `requirements.txt`
- `requirements-dev.txt`
- `dev-requirements.txt`
- `setup.py` (basic parsing)
- `pyproject.toml` (basic parsing)

It distinguishes between:
- Standard library modules (ignored by default)
- External packages (tracked when `track_external_libraries` is enabled)
- Relative imports (treated as internal)

## Output Formats

### JSON Export

Creates a JSON file with:
- Array of nodes with properties
- Array of relationships
- Content registry summary
- Metadata about the analysis

### Neo4j Cypher Export

Generates Cypher statements including:
- Constraint creation for unique node IDs
- Index creation for performance
- MERGE statements for nodes
- MATCH+MERGE statements for relationships
- Summary statistics as comments

## Example Neo4j Import

```bash
# After running the indexer
neo4j-admin database import \
  --nodes=graph-data.json \
  --relationships=graph-data.json \
  neo4j

# Or run the cypher file directly
cat neo4j-import.cypher | cypher-shell -u neo4j -p password
```

## Configuration

The indexer supports various configuration options:

```python
DEFAULT_CONFIG = {
    'include_variables': False,        # Variables can create noise
    'include_imports': True,           # Track import relationships
    'include_folders': True,           # Directory structure
    'include_files': True,             # File nodes
    'include_classes': True,           # Class definitions
    'include_methods': True,           # Method definitions
    'include_functions': True,         # Function definitions
    'ignore_venv': True,               # Skip virtual environments
    'track_external_libraries': False, # External dependencies
    'capture_content': True            # Include source code snippets
}
```

## Virtual Environment Detection

The indexer automatically skips common virtual environment and build directories:

- `venv`, `env`, `.venv`, `.env`
- `virtualenv`, `__pycache__`
- `.git`, `.pytest_cache`, `.mypy_cache`
- `node_modules`, `.tox`
- `site-packages`, `dist`, `build`
- Directories ending with `egg-info`

## Requirements

- Python 3.6+
- No external dependencies (uses only standard library)

## Architecture

The implementation consists of:

- `main.py`: Command-line interface and orchestration
- `constants.py`: Node types, relationship types, and configuration
- `helpers.py`: Utility functions for node/relationship creation
- `scanner.py`: Directory scanning and dependency parsing
- `ast_analyzer.py`: Python AST analysis and code structure extraction
- `exporters.py`: JSON and Neo4j Cypher export functionality

## Comparison with Node.js Version

This Python implementation provides equivalent functionality to the Node.js version but with Python-specific features:

- Uses Python's `ast` module instead of Babel for parsing
- Detects Python-specific patterns (decorators, async/await, etc.)
- Handles Python import mechanisms (from/import statements)
- Recognizes Python virtual environments and build artifacts
- Parses Python dependency files (requirements.txt, setup.py, pyproject.toml) 