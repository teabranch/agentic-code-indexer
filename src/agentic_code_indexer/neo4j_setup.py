#!/usr/bin/env python3
"""
Neo4j Database Setup Script for Agentic Code Indexer
Creates schema, constraints, and vector indexes for the code indexing system.
"""

import os
from neo4j import GraphDatabase
from typing import Optional
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class Neo4jSetup:
    def __init__(self, uri: str = "bolt://localhost:7687", 
                 username: str = "neo4j", 
                 password: Optional[str] = None):
        """
        Initialize Neo4j connection for setup operations.
        
        Args:
            uri: Neo4j connection URI
            username: Neo4j username
            password: Neo4j password (if None, will try to get from env var NEO4J_PASSWORD)
        """
        if password is None:
            password = os.getenv("NEO4J_PASSWORD", "password")
        
        self.driver = GraphDatabase.driver(uri, auth=(username, password))
        logger.info(f"Connected to Neo4j at {uri}")

    def close(self):
        """Close the Neo4j driver connection."""
        if self.driver:
            self.driver.close()
            logger.info("Neo4j connection closed")

    def create_constraints(self):
        """Create uniqueness constraints for crucial node properties."""
        constraints = [
            "CREATE CONSTRAINT file_path_unique IF NOT EXISTS FOR (f:File) REQUIRE f.path IS UNIQUE",
            "CREATE CONSTRAINT class_full_name_unique IF NOT EXISTS FOR (c:Class) REQUIRE c.full_name IS UNIQUE", 
            "CREATE CONSTRAINT method_full_name_unique IF NOT EXISTS FOR (m:Method) REQUIRE m.full_name IS UNIQUE",
            "CREATE CONSTRAINT function_full_name_unique IF NOT EXISTS FOR (f:Function) REQUIRE f.full_name IS UNIQUE",
            "CREATE CONSTRAINT variable_full_name_unique IF NOT EXISTS FOR (v:Variable) REQUIRE v.full_name IS UNIQUE",
            "CREATE CONSTRAINT interface_full_name_unique IF NOT EXISTS FOR (i:Interface) REQUIRE i.full_name IS UNIQUE",
            "CREATE CONSTRAINT parameter_full_name_unique IF NOT EXISTS FOR (p:Parameter) REQUIRE p.full_name IS UNIQUE"
        ]
        
        with self.driver.session() as session:
            for constraint in constraints:
                try:
                    session.run(constraint)
                    logger.info(f"Created constraint: {constraint}")
                except Exception as e:
                    logger.warning(f"Constraint creation failed or already exists: {constraint} - {e}")

    def create_vector_indexes(self):
        """Create vector indexes on embedding properties for all searchable node types."""
        # Vector dimension is 768 for jina-embeddings-v2-base-code
        vector_indexes = [
            {
                "name": "file_embedding_index",
                "label": "File",
                "query": "CREATE VECTOR INDEX file_embedding_index IF NOT EXISTS FOR (n:File) ON (n.embedding) OPTIONS { indexConfig: { `vector.dimensions`: 768, `vector.similarity_function`: 'cosine' } }"
            },
            {
                "name": "class_embedding_index", 
                "label": "Class",
                "query": "CREATE VECTOR INDEX class_embedding_index IF NOT EXISTS FOR (n:Class) ON (n.embedding) OPTIONS { indexConfig: { `vector.dimensions`: 768, `vector.similarity_function`: 'cosine' } }"
            },
            {
                "name": "method_embedding_index",
                "label": "Method", 
                "query": "CREATE VECTOR INDEX method_embedding_index IF NOT EXISTS FOR (n:Method) ON (n.embedding) OPTIONS { indexConfig: { `vector.dimensions`: 768, `vector.similarity_function`: 'cosine' } }"
            },
            {
                "name": "function_embedding_index",
                "label": "Function",
                "query": "CREATE VECTOR INDEX function_embedding_index IF NOT EXISTS FOR (n:Function) ON (n.embedding) OPTIONS { indexConfig: { `vector.dimensions`: 768, `vector.similarity_function`: 'cosine' } }"
            },
            {
                "name": "variable_embedding_index",
                "label": "Variable", 
                "query": "CREATE VECTOR INDEX variable_embedding_index IF NOT EXISTS FOR (n:Variable) ON (n.embedding) OPTIONS { indexConfig: { `vector.dimensions`: 768, `vector.similarity_function`: 'cosine' } }"
            },
            {
                "name": "interface_embedding_index",
                "label": "Interface",
                "query": "CREATE VECTOR INDEX interface_embedding_index IF NOT EXISTS FOR (n:Interface) ON (n.embedding) OPTIONS { indexConfig: { `vector.dimensions`: 768, `vector.similarity_function`: 'cosine' } }"
            }
        ]
        
        with self.driver.session() as session:
            for index_config in vector_indexes:
                try:
                    session.run(index_config["query"])
                    logger.info(f"Created vector index: {index_config['name']} for {index_config['label']} nodes")
                except Exception as e:
                    logger.warning(f"Vector index creation failed or already exists: {index_config['name']} - {e}")

    def create_additional_indexes(self):
        """Create additional indexes for performance optimization."""
        additional_indexes = [
            "CREATE INDEX file_checksum_index IF NOT EXISTS FOR (f:File) ON (f.checksum)",
            "CREATE INDEX file_extension_index IF NOT EXISTS FOR (f:File) ON (f.extension)",
            "CREATE INDEX node_name_index IF NOT EXISTS FOR (n:Class) ON (n.name)",
            "CREATE INDEX node_name_index IF NOT EXISTS FOR (n:Method) ON (n.name)",
            "CREATE INDEX node_name_index IF NOT EXISTS FOR (n:Function) ON (n.name)",
            "CREATE INDEX node_name_index IF NOT EXISTS FOR (n:Variable) ON (n.name)",
            "CREATE TEXT INDEX file_content_text_index IF NOT EXISTS FOR (f:File) ON (f.content)",
            "CREATE TEXT INDEX summary_text_index IF NOT EXISTS FOR (n) ON (n.generated_summary)"
        ]
        
        with self.driver.session() as session:
            for index_query in additional_indexes:
                try:
                    session.run(index_query)
                    logger.info(f"Created index: {index_query}")
                except Exception as e:
                    logger.warning(f"Index creation failed or already exists: {index_query} - {e}")

    def setup_complete_schema(self):
        """Run complete schema setup including constraints, vector indexes, and additional indexes."""
        logger.info("Starting Neo4j schema setup...")
        
        self.create_constraints()
        self.create_vector_indexes()
        self.create_additional_indexes()
        
        logger.info("Neo4j schema setup completed successfully!")

    def verify_setup(self):
        """Verify that constraints and indexes were created successfully."""
        with self.driver.session() as session:
            # Check constraints
            constraints_result = session.run("SHOW CONSTRAINTS")
            constraints = [record["name"] for record in constraints_result]
            logger.info(f"Created constraints: {constraints}")
            
            # Check indexes
            indexes_result = session.run("SHOW INDEXES")
            indexes = [record["name"] for record in indexes_result]
            logger.info(f"Created indexes: {indexes}")


def main():
    """Main function to setup Neo4j schema."""
    # Get connection details from environment variables or use defaults
    neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    neo4j_username = os.getenv("NEO4J_USERNAME", "neo4j")
    neo4j_password = os.getenv("NEO4J_PASSWORD", "password")
    
    setup = Neo4jSetup(neo4j_uri, neo4j_username, neo4j_password)
    
    try:
        setup.setup_complete_schema()
        setup.verify_setup()
    finally:
        setup.close()


if __name__ == "__main__":
    main() 