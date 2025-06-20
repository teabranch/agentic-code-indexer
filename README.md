![image](https://github.com/user-attachments/assets/ffc8a373-60e8-46b0-a8c8-b211f4de57fa)


# 🤖 Agentic Code Indexer

An intelligent code analysis and graph-based indexing system that creates a comprehensive, searchable representation of your codebase using Neo4j, LLMs, and semantic embeddings.

## ✨ Features

- **🌐 Multi-language Support**: Python, C#, JavaScript/TypeScript
- **📊 Graph-based Representation**: Rich code relationships in Neo4j
- **🧠 LLM-powered Summarization**: Hierarchical code summaries using Claude
- **🔍 Hybrid Search System**: Vector similarity + entity lookup + graph context expansion
- **🎯 Natural Language Queries**: "Find authentication methods" or "PaymentService class"
- **🕸️ GraphRAG Context**: Expand search results with related code relationships
- **🌐 REST API**: FastAPI-based search API with interactive documentation
- **⚡ Incremental Processing**: Change detection with SHA-256 checksums
- **🚀 Concurrent Processing**: Async/await for high-performance indexing
- **🎨 Beautiful CLI**: Rich terminal interface with progress tracking

## 🏗️ Architecture

```
┌─────────────────────┐    ┌─────────────────────┐    ┌─────────────────────┐
│   File Traversal    │───▶│  Language Chunkers  │───▶│   Graph Ingestion   │
│  & Change Detection │    │  (Python/C#/JS/TS) │    │     (Neo4j)         │
└─────────────────────┘    └─────────────────────┘    └─────────────────────┘
                                                                   │
┌─────────────────────┐    ┌─────────────────────┐                │
│  Embedding Gen.     │◀───│  LLM Summarization  │◀───────────────┘
│ (Jina Embeddings)   │    │  (Anthropic Claude) │
└─────────────────────┘    └─────────────────────┘
```

## 🚀 Quick Start

### Prerequisites

- Python 3.8+
- Node.js 18+ 
- .NET 6+
- Neo4j Database
- Anthropic API Key (optional, for LLM features)

### Installation

1. **Clone the repository**
```bash
git clone https://github.com/your-org/agentic-code-indexer.git
cd agentic-code-indexer
```

2. **Start Neo4j Database**
```bash
docker-compose up -d
```

3. **Install Python dependencies**
```bash
cd src/agentic_code_indexer
pip install -r requirements.txt
```

4. **Set up environment variables**
```bash
export ANTHROPIC_API_KEY="your-api-key-here"  # Optional
export NEO4J_PASSWORD="your-neo4j-password"
```

### Basic Usage

1. **Index your codebase**
```bash
# Index current directory with database initialization
python -m agentic_code_indexer index . --init-db

# Index specific directory
python -m agentic_code_indexer index /path/to/your/project

# Skip LLM features (faster, no API required)
python -m agentic_code_indexer index . --skip-llm
```

2. **Check indexing status**
```bash
python -m agentic_code_indexer status
```

3. **Generate summaries and embeddings**
```bash
python -m agentic_code_indexer summarize
```

4. **Search your codebase**
```bash
# Natural language search
python -m agentic_code_indexer search "authentication methods"
python -m agentic_code_indexer search "PaymentService class" --types Class
python -m agentic_code_indexer search "error handling" --context --code

# Explain how a query would be processed
python -m agentic_code_indexer explain "user authentication"

# Start the search API server
python -m agentic_code_indexer api --host 0.0.0.0 --port 8000
# Then visit http://localhost:8000/docs for interactive API documentation
```

## 📚 Component Overview

### Phase 1: Foundation (✅ Complete)

- **🗃️ Neo4j Database Setup**: Comprehensive schema with constraints and vector indexes
- **🐍 Python Chunker**: LibCST-based AST analysis with scope resolution
- **🔷 C# Chunker**: Microsoft.CodeAnalysis with semantic symbol resolution  
- **🟨 JavaScript/TypeScript Chunker**: TypeScript Compiler API + Acorn parser
- **📋 Common Data Format**: Pydantic models for cross-language compatibility

### Phase 2: Main Pipeline (✅ Complete)

- **📁 File Traversal**: Recursive directory scanning with change detection
- **🔄 Chunker Orchestration**: Coordinates all language-specific chunkers
- **📊 Graph Ingestion**: Efficient batched Neo4j operations with MERGE clauses
- **🧠 Hierarchical Summarization**: Bottom-up LLM processing (Parameters → Variables → Methods → Classes → Files)
- **🔍 Embedding Generation**: Local vector generation using Jina embeddings
- **⚙️ Transaction Management**: Error handling, retry mechanisms, and batch optimization

### Phase 3: Retrieval System (✅ Complete)

- **🔍 Vector Search Engine**: Semantic similarity search using Neo4j vector indexes
- **🕸️ Graph Traversal Engine**: GraphRAG-style context expansion with relationship following
- **🎯 Hybrid Search System**: Combines vector similarity, entity lookup, and graph context
- **🤖 Query Intent Parsing**: Intelligent analysis of natural language queries
- **📊 Call & Inheritance Hierarchy**: Analyze method calls and class inheritance patterns
- **🌐 REST API**: FastAPI-based search API with comprehensive endpoints
- **💻 Interactive CLI**: Rich terminal search interface with explanations

## 🛠️ Advanced Usage

### Custom Configuration

```bash
# Use different Neo4j instance
python -m agentic_code_indexer index . \
  --neo4j-uri bolt://your-server:7687 \
  --neo4j-user your-username \
  --neo4j-password your-password

# Adjust performance settings
python -m agentic_code_indexer index . \
  --max-concurrent 10 \
  --batch-size 2000

# Verbose logging
python -m agentic_code_indexer index . --verbose
```

### Recovery Operations

```bash
# Reset processing status (if interrupted)
python -m agentic_code_indexer reset --confirm

# Re-run just summarization
python -m agentic_code_indexer summarize --batch-size 50
```

## 📊 Database Schema

The system creates a rich graph model in Neo4j:

### Node Types
- **File**: Source code files with checksums and metadata
- **Class/Interface**: Type definitions with inheritance relationships  
- **Method/Function**: Callable code elements with parameters
- **Variable/Parameter**: Data elements with type information
- **Import**: Dependency declarations

### Relationships
- **CONTAINS**: Hierarchical containment (File → Class → Method)
- **DEFINES**: Definition relationships (Class → Method)
- **CALLS**: Function/method invocations
- **EXTENDS/IMPLEMENTS**: Inheritance relationships
- **IMPORTS**: Module dependencies

### Vector Indexes
- 768-dimensional embeddings on all major node types
- Cosine similarity for semantic search
- Optimized for `jina-embeddings-v2-base-code` model

## 🔍 Search Examples

### Natural Language Search

```bash
# Find authentication-related code
python -m agentic_code_indexer search "user authentication login"

# Search for specific classes
python -m agentic_code_indexer search "PaymentService" --types Class

# Find error handling patterns
python -m agentic_code_indexer search "exception handling try catch" --context

# Search with source code included
python -m agentic_code_indexer search "database connection" --code --verbose

# Explain search strategy
python -m agentic_code_indexer explain "API rate limiting middleware"
```

### REST API Examples

```bash
# Start the API server
python -m agentic_code_indexer api

# Search via HTTP
curl -X POST "http://localhost:8000/search" \
  -H "Content-Type: application/json" \
  -d '{"query": "authentication methods", "max_results": 5, "include_context": true}'

# Get call hierarchy for a method
curl -X POST "http://localhost:8000/hierarchy/call" \
  -H "Content-Type: application/json" \
  -d '{"node_id": "method_123", "direction": "both", "max_depth": 2}'

# Get inheritance hierarchy for a class
curl -X POST "http://localhost:8000/hierarchy/inheritance" \
  -H "Content-Type: application/json" \
  -d '{"node_id": "class_456"}'
```

### Example Cypher Queries

```cypher
// Find all classes that implement a specific interface
MATCH (c:Class)-[:IMPLEMENTS]->(i:Interface {name: "IUserRepository"})
RETURN c.name, c.generated_summary

// Semantic search for payment-related code
CALL db.index.vector.queryNodes('embedding_index', 10, $payment_embedding)
YIELD node, score
RETURN node.name, node.generated_summary, score

// Find complex methods (high cyclomatic complexity)
MATCH (m:Method)
WHERE m.raw_code CONTAINS "if" AND m.raw_code CONTAINS "for"
RETURN m.full_name, m.generated_summary
```

## 🧪 Testing

Each chunker includes comprehensive test coverage:

```bash
# Test Python chunker
cd src/python-chunker && python -m pytest

# Test C# chunker  
cd src/csharp-chunker/CSharpChunker && dotnet test

# Test Node.js chunker
cd src/nodejs-chunker && npm test
```

## 📈 Performance

- **Throughput**: ~50-100 files/second (depends on file size and complexity)
- **Concurrency**: Configurable concurrent processing (default: 5 workers)
- **Memory**: Efficient streaming with batched database operations
- **Incremental**: Only processes changed files using SHA-256 checksums

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Add tests for new functionality
4. Ensure all tests pass
5. Submit a pull request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- **Microsoft CodeAnalysis** for C# semantic analysis
- **LibCST** for Python concrete syntax trees
- **TypeScript Compiler API** for JavaScript/TypeScript analysis
- **Neo4j** for graph database capabilities
- **Anthropic Claude** for intelligent code summarization
- **Jina AI** for state-of-the-art code embeddings

## Cite this project

### Code citation
```
@software{agentic-code-indexer,
  author = {TeaBranch},
  title = {agentic-code-indexer: An intelligent code analysis and graph-based indexing system that creates a comprehensive, searchable representation of your codebase using Neo4j, LLMs, and semantic embeddings.},
  year = {2025},
  publisher = {GitHub},
  journal = {GitHub Repository},
  howpublished = {\url{https://github.com/teabranch/agentic-code-indexer}},
  commit = {use the commit hash you’re working with}
}
```

### Text citation

TeaBranch. (2025). agentic-code-indexer: An intelligent code analysis and graph-based indexing system that creates a comprehensive, searchable representation of your codebase using Neo4j, LLMs, and semantic embeddings. [Computer software]. GitHub. https://github.com/teabranch/agentic-code-indexer


---

**Ready to explore your codebase like never before?** 🚀

Get started with the Agentic Code Indexer and unlock the full potential of graph-based code analysis! 
