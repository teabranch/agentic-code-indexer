# Installation Guide

## Prerequisites

### 1. Python 3.7+

Install Python and required packages:

```bash
pip install openai neo4j python-dotenv numpy
```

### 2. Node.js 16+

For JavaScript/TypeScript analysis support:

```bash
# Install Node.js 16+ from https://nodejs.org/

# Install Node.js chunker dependencies
cd src/agentic_code_indexer/nodejs-chunker
npm install
```

### 3. Neo4j Database

You can use either a local or remote Neo4j instance:

#### Local Installation
- Download and install from [Neo4j Download Center](https://neo4j.com/download/)
- Start the Neo4j service
- Set up authentication (default username: `neo4j`)

#### Neo4j AuraDB (Cloud)
- Create a free account at [Neo4j Aura](https://neo4j.com/aura/)
- Create a database instance
- Note the connection URI and credentials

### 4. OpenAI API Key

- Sign up for an OpenAI account at [OpenAI Platform](https://platform.openai.com/)
- Generate an API key from the API keys section
- Ensure you have sufficient credits for embedding and completion requests

## Environment Setup

Create a `.env` file in the project root:

```env
# OpenAI Configuration
OPENAI_API_KEY=your_openai_api_key_here

# Neo4j Configuration
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=your_password_here

# For Neo4j AuraDB, use something like:
# NEO4J_URI=neo4j+s://your-instance.databases.neo4j.io
```

## Verification

### Test Neo4j Connection

```python
from neo4j import GraphDatabase

driver = GraphDatabase.driver("bolt://localhost:7687", auth=("neo4j", "your_password"))
with driver.session() as session:
    result = session.run("RETURN 'Connection successful' AS message")
    print(result.single()["message"])
driver.close()
```

### Test OpenAI API

```python
import openai
import os
from dotenv import load_dotenv

load_dotenv()
client = openai.OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

response = client.embeddings.create(
    model="text-embedding-ada-002",
    input="test"
)
print("OpenAI API connection successful")
```

### Test Node.js Chunker

```bash
cd src/agentic_code_indexer/nodejs-chunker
node main.js --help
```

## Docker Setup (Optional)

For a containerized setup, you can use Docker Compose:

```yaml
# docker-compose.yml
version: '3.8'
services:
  neo4j:
    image: neo4j:5.13
    environment:
      NEO4J_AUTH: neo4j/password
      NEO4J_PLUGINS: '["apoc"]'
    ports:
      - "7474:7474"
      - "7687:7687"
    volumes:
      - neo4j_data:/data

volumes:
  neo4j_data:
```

```bash
docker-compose up -d
```

## Troubleshooting Installation

### Common Issues

1. **Python Package Conflicts**: Use a virtual environment
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   # or
   venv\Scripts\activate     # Windows
   pip install -r requirements.txt
   ```

2. **Node.js Version**: Ensure you're using Node.js 16+
   ```bash
   node --version
   ```

3. **Neo4j Connection**: Check if Neo4j is running
   ```bash
   # Check if Neo4j is running (default port 7687)
   telnet localhost 7687
   ```

4. **OpenAI API Limits**: Monitor your usage and billing in the OpenAI dashboard

### Platform-specific Notes

#### Windows
- Use PowerShell or Command Prompt
- Ensure Python is added to PATH
- Neo4j may require running as administrator

#### macOS
- Consider using Homebrew for Neo4j installation:
  ```bash
  brew install neo4j
  brew services start neo4j
  ```

#### Linux
- Use your distribution's package manager for Neo4j
- Ensure proper permissions for the application directory 