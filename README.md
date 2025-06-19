# Agentic Code Indexer

A powerful library and CLI tool for indexing code repositories using Large Language Models (LLMs) and embeddings to enable intelligent semantic search and code analysis.

## 🚀 Quick Start

```bash
# 1. Install dependencies
pip install openai neo4j python-dotenv numpy

# 2. Set up environment
cp .env.example .env  # Add your OpenAI API key and Neo4j credentials

# 3. Index your code
python src/agentic_code_indexer/code_indexer.py index --folder ./your-project

# 4. Search semantically
python src/agentic_code_indexer/code_indexer.py query --query "authentication functions"
```

## ✨ Features

- **🔍 Multi-Language Support**: Python and Node.js/JavaScript analysis
- **🧠 AI-Powered**: LLM descriptions and semantic embeddings
- **🗄️ Graph Database**: Rich relationships stored in Neo4j
- **🔎 Semantic Search**: Natural language code queries
- **⚡ Context-Aware**: Returns related code elements with search results

## 📋 Overview

Agentic Code Indexer analyzes codebases and creates rich, searchable indexes that combine traditional code structure analysis with AI-powered semantic understanding. It automatically detects project types, extracts code structure, generates natural language descriptions, and creates embeddings for semantic search.

### Architecture

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
            │  + OpenAI Descriptions          │
            │  + Semantic Embeddings          │
            └─────────────────────────────────┘
```

## 📚 Documentation

| Document | Description |
|----------|-------------|
| **[Installation Guide](docs/installation.md)** | Complete setup instructions with prerequisites |
| **[Usage Guide](docs/usage.md)** | CLI and programmatic usage examples |
| **[Architecture](docs/architecture.md)** | Technical details and system design |
| **[Neo4j Integration](docs/neo4j-integration.md)** | Database schema and query patterns |
| **[API Reference](docs/api-reference.md)** | Complete API documentation |
| **[Troubleshooting](docs/troubleshooting.md)** | Common issues and solutions |
| **[Contributing](docs/contributing.md)** | Development guidelines and contribution process |

## 🛠️ Prerequisites

- **Python 3.7+** with packages: `openai`, `neo4j`, `python-dotenv`, `numpy`
- **Node.js 16+** for JavaScript/TypeScript analysis
- **Neo4j Database** (local or AuraDB cloud)
- **OpenAI API Key** for LLM features

## 🏗️ Project Structure

```
agentic-code-indexer/
├── src/agentic_code_indexer/
│   ├── code_indexer.py          # Main orchestrator
│   ├── nodejs-chunker/          # JavaScript/TypeScript analysis
│   │   ├── main.js             # Entry point
│   │   ├── js-scanner.js       # AST analysis
│   │   └── ...                 # Supporting modules
│   └── python-chunker/         # Python analysis
│       ├── main.py             # Entry point
│       ├── ast_analyzer.py     # AST analysis
│       └── ...                 # Supporting modules
├── docs/                       # Detailed documentation
└── README.md                   # This file
```

## 🎯 Supported Languages

### Python
- **AST Analysis**: Classes, methods, functions, variables, imports
- **Dependency Tracking**: External libraries from requirements.txt
- **Advanced Features**: Inheritance relationships, decorators, docstrings

### Node.js/JavaScript
- **Modern JS**: ES6+, TypeScript, JSX support
- **Comprehensive**: Functions, classes, modules, imports/exports
- **Framework Support**: React components, Express routes

## 🔍 Query Examples

```python
from src.agentic_code_indexer.code_indexer import CodeIndexer

indexer = CodeIndexer()

# Natural language queries
results = indexer.query_code("user authentication functions")
results = indexer.query_code("database connection setup")
results = indexer.query_code("error handling middleware")

# Results include similarity scores and context
for result in results:
    print(f"{result['node']['name']}: {result['similarity']:.3f}")
    print(f"Context: {len(result['context'])} related elements")
```

## 🗄️ Database Schema

The indexer creates a rich Neo4j graph with these node types:

- **Folder/File**: Project structure
- **Class/Method/Function**: Code elements
- **Variable/Import**: Dependencies and data
- **ExternalLibrary**: Third-party packages

Connected by relationships:
- **CONTAINS**: Hierarchical structure
- **IMPORTS/CALLS**: Dependencies and usage
- **EXTENDS**: Inheritance chains

## 🚦 Getting Started

1. **📖 Read the [Installation Guide](docs/installation.md)** for detailed setup
2. **👀 Check the [Usage Guide](docs/usage.md)** for examples
3. **🔧 Review [Troubleshooting](docs/troubleshooting.md)** if you encounter issues
4. **🤝 See [Contributing](docs/contributing.md)** to help improve the project

## 📈 Performance

- **Indexing**: ~1000 Python nodes/minute, ~800 Node.js nodes/minute
- **Search**: Sub-second queries for databases with <10k nodes
- **Memory**: ~1GB for 10k nodes with embeddings
- **API Costs**: Optimized batching for OpenAI API efficiency

## 🔒 Security & Privacy

- **Local Processing**: Code analysis happens locally
- **Configurable**: Choose what content to capture and store
- **API Keys**: Secure environment variable management
- **Private Data**: Option to exclude sensitive files

## 🛣️ Roadmap

- [ ] **Additional Languages**: Java, C#, Go support
- [ ] **Web Interface**: Browser-based code exploration
- [ ] **IDE Integration**: VS Code and other editor plugins
- [ ] **Incremental Indexing**: Update only changed files
- [ ] **Advanced Analytics**: Code quality metrics and insights
- [ ] **Cloud Deployment**: Scalable cloud-based indexing

## 📄 License

[Add your license information here]

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guide](docs/contributing.md) for:

- Development setup
- Code style guidelines
- Testing requirements
- Pull request process

## 📞 Support

- **🐛 Bug Reports**: [GitHub Issues](https://github.com/your-repo/issues)
- **💡 Feature Requests**: [GitHub Discussions](https://github.com/your-repo/discussions)
- **📚 Documentation**: Check the [docs/](docs/) folder
- **❓ Questions**: Create an issue with the "question" label

## 🙏 Acknowledgments

Built with:
- **OpenAI** for language models and embeddings
- **Neo4j** for graph database capabilities
- **Python AST** and **Babel** for code parsing
- The open source community for inspiration and feedback

---

**Ready to make your codebase searchable?** Start with the [Installation Guide](docs/installation.md)!
