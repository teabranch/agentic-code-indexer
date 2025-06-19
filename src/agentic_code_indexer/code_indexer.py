#!/usr/bin/env python3
"""
Agentic Code Indexer - Main Entry Point
Indexes code repositories with LLM descriptions and embeddings for semantic search
"""

import os
import sys
import json
import argparse
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
import logging

# Setup logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Add the chunker modules to the path
sys.path.append(str(Path(__file__).parent / 'python-chunker'))
sys.path.append(str(Path(__file__).parent / 'nodejs-chunker'))

from dotenv import load_dotenv
import openai
from neo4j import GraphDatabase
import numpy as np

# Load environment variables
load_dotenv()

class CodeIndexer:
    def __init__(self):
        self.neo4j_driver = None
        self.openai_client = None
        self.setup_connections()
    
    def setup_connections(self):
        """Setup Neo4j and OpenAI connections"""
        # Neo4j connection
        neo4j_uri = os.getenv('NEO4J_URI', 'bolt://localhost:7687')
        neo4j_user = os.getenv('NEO4J_USER', 'neo4j')
        neo4j_password = os.getenv('NEO4J_PASSWORD', 'password')
        
        try:
            self.neo4j_driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
            logger.info(f"Connected to Neo4j at {neo4j_uri}")
        except Exception as e:
            logger.error(f"Failed to connect to Neo4j: {e}")
            raise
        
        # OpenAI connection
        openai_api_key = os.getenv('OPENAI_API_KEY')
        if not openai_api_key:
            logger.error("OPENAI_API_KEY not found in environment variables")
            raise ValueError("OPENAI_API_KEY is required")
        
        self.openai_client = openai.OpenAI(api_key=openai_api_key)
        logger.info("Connected to OpenAI")
    
    def detect_project_type(self, folder_path: str) -> str:
        """Detect if the folder is a Node.js, Python, or other project"""
        folder_path = Path(folder_path)
        
        # Check for Node.js indicators
        if (folder_path / 'package.json').exists():
            return 'nodejs'
        
        # Check for Python indicators
        python_indicators = [
            'requirements.txt', 'setup.py', 'pyproject.toml', 
            'Pipfile', 'environment.yml', 'conda.yml'
        ]
        
        for indicator in python_indicators:
            if (folder_path / indicator).exists():
                return 'python'
        
        # Check for Python files in the directory
        python_files = list(folder_path.glob('**/*.py'))
        if python_files:
            return 'python'
        
        # Check for JavaScript/TypeScript files
        js_files = list(folder_path.glob('**/*.js')) + list(folder_path.glob('**/*.ts'))
        if js_files:
            return 'nodejs'
        
        return 'other'
    
    def chunk_code(self, folder_path: str, project_type: str) -> Dict[str, Any]:
        """Chunk code using the appropriate chunker"""
        logger.info(f"Chunking {project_type} code in {folder_path}")
        
        if project_type == 'python':
            return self._chunk_python_code(folder_path)
        elif project_type == 'nodejs':
            return self._chunk_nodejs_code(folder_path)
        else:
            logger.warning(f"Unsupported project type: {project_type}")
            return {'nodes': [], 'relationships': []}
    
    def _chunk_python_code(self, folder_path: str) -> Dict[str, Any]:
        """Chunk Python code using the existing Python chunker"""
        try:
            # Import Python chunker modules
            from scanner import scan_python_service
            from constants import DEFAULT_CONFIG
            
            config = {
                **DEFAULT_CONFIG,
                'capture_content': True,
                'include_classes': True,
                'include_methods': True,
                'include_functions': True,
                'include_files': True,
                'include_folders': True
            }
            
            graph = scan_python_service(folder_path, config)
            logger.info(f"Python chunking complete: {len(graph['nodes'])} nodes, {len(graph['relationships'])} relationships")
            return graph
            
        except Exception as e:
            logger.error(f"Error chunking Python code: {e}")
            return {'nodes': [], 'relationships': []}
    
    def _chunk_nodejs_code(self, folder_path: str) -> Dict[str, Any]:
        """Chunk Node.js code using the existing Node.js chunker"""
        try:
            # Use subprocess to run the Node.js chunker
            chunker_path = Path(__file__).parent / 'nodejs-chunker'
            
            # Create a temporary output file
            with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_file:
                temp_output = temp_file.name
            
            # Run the Node.js chunker
            cmd = [
                'node', 
                str(chunker_path / 'main.js'), 
                folder_path,
                '--capture-content=true'
            ]
            
            logger.info(f"Running Node.js chunker: {' '.join(cmd)}")
            result = subprocess.run(cmd, capture_output=True, text=True, cwd=str(chunker_path))
            
            if result.returncode != 0:
                logger.error(f"Node.js chunker failed: {result.stderr}")
                return {'nodes': [], 'relationships': []}
            
            # Read the generated graph data
            graph_file = chunker_path / 'graph-data.json'
            if graph_file.exists():
                with open(graph_file, 'r', encoding='utf-8') as f:
                    graph = json.load(f)
                logger.info(f"Node.js chunking complete: {len(graph['nodes'])} nodes, {len(graph['relationships'])} relationships")
                return graph
            else:
                logger.error("Graph data file not found after Node.js chunking")
                return {'nodes': [], 'relationships': []}
                
        except Exception as e:
            logger.error(f"Error chunking Node.js code: {e}")
            return {'nodes': [], 'relationships': []}
    
    def load_to_neo4j(self, graph: Dict[str, Any]):
        """Load graph data to Neo4j"""
        logger.info("Loading graph to Neo4j")
        
        with self.neo4j_driver.session() as session:
            # Clear existing data (optional)
            session.run("MATCH (n) DETACH DELETE n")
            
            # Create constraints
            constraints = [
                "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Folder) REQUIRE n.id IS UNIQUE",
                "CREATE CONSTRAINT IF NOT EXISTS FOR (n:File) REQUIRE n.id IS UNIQUE",
                "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Class) REQUIRE n.id IS UNIQUE",
                "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Method) REQUIRE n.id IS UNIQUE",
                "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Function) REQUIRE n.id IS UNIQUE",
                "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Variable) REQUIRE n.id IS UNIQUE",
                "CREATE CONSTRAINT IF NOT EXISTS FOR (n:Import) REQUIRE n.id IS UNIQUE",
                "CREATE CONSTRAINT IF NOT EXISTS FOR (n:ExternalLibrary) REQUIRE n.id IS UNIQUE",
                "CREATE INDEX IF NOT EXISTS FOR (n:Folder) ON (n.name)",
                "CREATE INDEX IF NOT EXISTS FOR (n:File) ON (n.name)"
            ]
            
            for constraint in constraints:
                session.run(constraint)
            
            # Load nodes
            for node in graph['nodes']:
                props = dict(node)
                node_id = props.pop('id')
                node_type = props.pop('type')
                
                query = f"MERGE (n:{node_type} {{id: $id}}) SET n += $props"
                session.run(query, id=node_id, props=props)
            
            # Load relationships
            for rel in graph['relationships']:
                query = """
                MATCH (a {id: $source}), (b {id: $target})
                MERGE (a)-[r:%s]->(b)
                SET r.id = $rel_id
                """ % rel['type']
                
                session.run(query, 
                          source=rel['source'], 
                          target=rel['target'], 
                          rel_id=rel['id'])
            
            logger.info(f"Loaded {len(graph['nodes'])} nodes and {len(graph['relationships'])} relationships to Neo4j")
    
    def generate_descriptions(self):
        """Add LLM-generated descriptions to nodes"""
        logger.info("Generating LLM descriptions for nodes")
        
        with self.neo4j_driver.session() as session:
            # Get nodes that need descriptions (classes, methods, functions, files)
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
            
            for node_data in nodes_to_process:
                try:
                    description = self._generate_node_description(node_data)
                    
                    # Update node with description
                    update_query = "MATCH (n {id: $id}) SET n.description = $description"
                    session.run(update_query, id=node_data['id'], description=description)
                    
                    logger.info(f"Generated description for {node_data['type']} {node_data['name']}")
                    
                except Exception as e:
                    logger.error(f"Error generating description for {node_data['id']}: {e}")
    
    def _generate_node_description(self, node_data: Dict[str, Any]) -> str:
        """Generate a description for a single node using OpenAI"""
        node_type = node_data.get('type', 'Unknown')
        node_name = node_data.get('name', 'Unknown')
        code_scope = node_data.get('code_scope', '')
        content = node_data.get('content', '')
        
        # Prepare the code content
        code_content = code_scope or content or ''
        if len(code_content) > 2000:
            code_content = code_content[:2000] + "..."
        
        prompt = f"""
        Analyze the following {node_type.lower()} named "{node_name}" and provide a concise description of its purpose and functionality.
        
        Code:
        {code_content}
        
        Please provide a brief, clear description (1-2 sentences) that explains what this {node_type.lower()} does.
        """
        
        try:
            response = self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a code analysis assistant. Provide concise, accurate descriptions of code elements."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=200,
                temperature=0.3
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"Error calling OpenAI API: {e}")
            return f"A {node_type.lower()} named {node_name}"
    
    def generate_embeddings(self):
        """Generate embeddings for nodes"""
        logger.info("Generating embeddings for nodes")
        
        with self.neo4j_driver.session() as session:
            # Get nodes that need embeddings
            query = """
            MATCH (n)
            WHERE (n:Class OR n:Method OR n:Function OR n:File)
            AND NOT EXISTS(n.embedding)
            RETURN n.id as id, n.name as name, n.description as description,
                   n.code_scope as code_scope, n.content as content
            LIMIT 100
            """
            
            results = session.run(query)
            nodes_to_process = [record.data() for record in results]
            
            for node_data in nodes_to_process:
                try:
                    embedding = self._generate_node_embedding(node_data)
                    
                    # Update node with embedding
                    update_query = "MATCH (n {id: $id}) SET n.embedding = $embedding"
                    session.run(update_query, id=node_data['id'], embedding=embedding)
                    
                    logger.info(f"Generated embedding for {node_data['name']}")
                    
                except Exception as e:
                    logger.error(f"Error generating embedding for {node_data['id']}: {e}")
    
    def _generate_node_embedding(self, node_data: Dict[str, Any]) -> List[float]:
        """Generate an embedding for a single node using OpenAI"""
        node_name = node_data.get('name', '')
        description = node_data.get('description', '')
        code_scope = node_data.get('code_scope', '')
        content = node_data.get('content', '')
        
        # Combine text for embedding
        text_parts = [node_name, description, code_scope, content]
        text_to_embed = ' '.join(part for part in text_parts if part)
        
        # Truncate if too long
        if len(text_to_embed) > 8000:
            text_to_embed = text_to_embed[:8000]
        
        try:
            response = self.openai_client.embeddings.create(
                model="text-embedding-ada-002",
                input=text_to_embed
            )
            
            return response.data[0].embedding
            
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            return []
    
    def query_code(self, query: str, max_results: int = 10) -> List[Dict[str, Any]]:
        """Query the indexed code using semantic search"""
        logger.info(f"Querying code with: {query}")
        
        # Generate embedding for the query
        try:
            query_response = self.openai_client.embeddings.create(
                model="text-embedding-ada-002",
                input=query
            )
            query_embedding = query_response.data[0].embedding
        except Exception as e:
            logger.error(f"Error generating query embedding: {e}")
            return []
        
        # Search for similar nodes
        with self.neo4j_driver.session() as session:
            # Find nodes with embeddings and calculate similarity
            search_query = """
            MATCH (n)
            WHERE EXISTS(n.embedding)
            RETURN n.id as id, n.name as name, n.type as type, 
                   n.description as description, n.embedding as embedding,
                   n.code_scope as code_scope, n.content as content
            """
            
            results = session.run(search_query)
            nodes = [record.data() for record in results]
            
            # Calculate cosine similarity
            similarities = []
            for node in nodes:
                if node['embedding']:
                    similarity = self._cosine_similarity(query_embedding, node['embedding'])
                    similarities.append((similarity, node))
            
            # Sort by similarity and get top results
            similarities.sort(key=lambda x: x[0], reverse=True)
            top_results = similarities[:max_results]
            
            # Get expanded context for each result
            expanded_results = []
            for similarity, node in top_results:
                context = self._get_node_context(session, node['id'], depth=3)
                expanded_results.append({
                    'node': node,
                    'similarity': similarity,
                    'context': context
                })
            
            return expanded_results
    
    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        """Calculate cosine similarity between two vectors"""
        a = np.array(a)
        b = np.array(b)
        return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b))
    
    def _get_node_context(self, session, node_id: str, depth: int = 3) -> Dict[str, Any]:
        """Get context around a node (up to depth levels)"""
        context_query = f"""
        MATCH (start {{id: $node_id}})
        CALL apoc.path.subgraphNodes(start, {{
            relationshipFilter: '<|>',
            minLevel: 0,
            maxLevel: {depth}
        }}) YIELD node
        RETURN node.id as id, node.name as name, node.type as type,
               node.description as description, node.code_scope as code_scope
        """
        
        try:
            results = session.run(context_query, node_id=node_id)
            return [record.data() for record in results]
        except Exception:
            # Fallback if APOC is not available
            fallback_query = """
            MATCH (n {id: $node_id})
            OPTIONAL MATCH (n)-[*1..3]-(related)
            RETURN COLLECT(DISTINCT {
                id: related.id,
                name: related.name,
                type: related.type,
                description: related.description
            }) as context
            """
            result = session.run(fallback_query, node_id=node_id)
            return result.single()['context'] if result.single() else []
    
    def index_folder(self, folder_path: str):
        """Index a folder completely"""
        logger.info(f"Starting indexing of folder: {folder_path}")
        
        # Step 1: Detect project type
        project_type = self.detect_project_type(folder_path)
        logger.info(f"Detected project type: {project_type}")
        
        if project_type == 'other':
            logger.warning("Unsupported project type. Skipping indexing.")
            return
        
        # Step 2: Chunk the code
        graph = self.chunk_code(folder_path, project_type)
        
        if not graph['nodes']:
            logger.warning("No nodes found in the code. Skipping indexing.")
            return
        
        # Step 3: Load to Neo4j
        self.load_to_neo4j(graph)
        
        # Step 4: Generate descriptions
        self.generate_descriptions()
        
        # Step 5: Generate embeddings
        self.generate_embeddings()
        
        logger.info("Indexing completed successfully!")
    
    def close(self):
        """Close connections"""
        if self.neo4j_driver:
            self.neo4j_driver.close()

def main():
    parser = argparse.ArgumentParser(description='Agentic Code Indexer')
    parser.add_argument('command', choices=['index', 'query'], help='Command to execute')
    parser.add_argument('--folder', type=str, help='Folder path to index')
    parser.add_argument('--query', type=str, help='Query string for semantic search')
    parser.add_argument('--max-results', type=int, default=10, help='Maximum number of results')
    
    args = parser.parse_args()
    
    indexer = CodeIndexer()
    
    try:
        if args.command == 'index':
            if not args.folder:
                logger.error("--folder is required for index command")
                return
            
            indexer.index_folder(args.folder)
            
        elif args.command == 'query':
            if not args.query:
                logger.error("--query is required for query command")
                return
            
            results = indexer.query_code(args.query, args.max_results)
            
            if not results:
                print("No results found.")
                return
            
            print(f"\nFound {len(results)} results for query: '{args.query}'\n")
            
            for i, result in enumerate(results, 1):
                node = result['node']
                similarity = result['similarity']
                context = result['context']
                
                print(f"Result {i} (Similarity: {similarity:.4f})")
                print(f"  Type: {node['type']}")
                print(f"  Name: {node['name']}")
                print(f"  Description: {node.get('description', 'N/A')}")
                
                if context:
                    print(f"  Related Context ({len(context)} items):")
                    for ctx_node in context[:5]:  # Show first 5 context items
                        print(f"    - {ctx_node['type']}: {ctx_node['name']}")
                
                print()
                
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    except Exception as e:
        logger.error(f"Error: {e}")
    finally:
        indexer.close()

if __name__ == '__main__':
    main() 