import asyncio
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import logging
import numpy as np
from neo4j import GraphDatabase
from .llm_integration import EmbeddingGenerator

logger = logging.getLogger(__name__)

@dataclass
class SearchResult:
    """Represents a single search result with score and metadata."""
    node_id: str
    name: str
    full_name: str
    node_type: str
    summary: str
    raw_code: Optional[str]
    similarity_score: float
    location: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None

@dataclass
class VectorSearchConfig:
    """Configuration for vector search operations."""
    max_results: int = 20
    min_similarity_threshold: float = 0.6
    boost_exact_matches: bool = True
    boost_factor: float = 1.2
    include_raw_code: bool = False

class VectorSearchEngine:
    """
    Handles semantic vector search operations using Neo4j vector indexes
    and embedding similarity calculations.
    """
    
    def __init__(self, neo4j_uri: str, neo4j_user: str, neo4j_password: str):
        self.driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
        self.embedding_generator = EmbeddingGenerator()
        
        # Available vector indexes by node type
        self.vector_indexes = {
            "File": "file_embedding_index",
            "Class": "class_embedding_index", 
            "Interface": "interface_embedding_index",
            "Method": "method_embedding_index",
            "Function": "function_embedding_index",
            "Variable": "variable_embedding_index"
        }
    
    def close(self):
        """Close database connection."""
        if self.driver:
            self.driver.close()
    
    async def search_by_text(
        self, 
        query_text: str, 
        config: VectorSearchConfig = None,
        node_types: Optional[List[str]] = None
    ) -> List[SearchResult]:
        """
        Search for code elements using natural language query.
        
        Args:
            query_text: Natural language search query
            config: Search configuration options
            node_types: Specific node types to search (default: all)
            
        Returns:
            List of SearchResult objects ranked by similarity
        """
        if config is None:
            config = VectorSearchConfig()
        
        if node_types is None:
            node_types = list(self.vector_indexes.keys())
        
        # Generate embedding for the query
        query_embedding_result = await self.embedding_generator.generate_embedding(query_text)
        query_embedding = query_embedding_result.embedding
        
        if not query_embedding:
            logger.error(f"Failed to generate embedding for query: {query_text}")
            return []
        
        # Search across specified node types
        all_results = []
        
        for node_type in node_types:
            if node_type not in self.vector_indexes:
                logger.warning(f"No vector index available for node type: {node_type}")
                continue
                
            results = await self._search_node_type(
                node_type, query_embedding, query_text, config
            )
            all_results.extend(results)
        
        # Sort by similarity score and apply global limit
        all_results.sort(key=lambda x: x.similarity_score, reverse=True)
        return all_results[:config.max_results]
    
    async def _search_node_type(
        self, 
        node_type: str, 
        query_embedding: List[float], 
        query_text: str,
        config: VectorSearchConfig
    ) -> List[SearchResult]:
        """Search within a specific node type using vector similarity."""
        
        index_name = self.vector_indexes[node_type]
        
        # Check if vector index exists
        if not await self._index_exists(index_name):
            logger.warning(f"Vector index {index_name} does not exist")
            return []
        
        query = f"""
        CALL db.index.vector.queryNodes($index_name, $k, $query_embedding)
        YIELD node, score
        WHERE score >= $min_threshold
        RETURN 
            node.id as id,
            node.name as name,
            node.full_name as full_name,
            labels(node)[0] as node_type,
            node.generated_summary as summary,
            node.raw_code as raw_code,
            node.start_line as start_line,
            node.end_line as end_line,
            score as similarity_score
        ORDER BY score DESC
        LIMIT $limit
        """
        
        results = []
        
        with self.driver.session() as session:
            try:
                result = session.run(
                    query,
                    index_name=index_name,
                    k=config.max_results,
                    query_embedding=query_embedding,
                    min_threshold=config.min_similarity_threshold,
                    limit=config.max_results
                )
                
                for record in result:
                    # Apply exact match boosting
                    similarity_score = record["similarity_score"]
                    if config.boost_exact_matches and self._is_exact_match(
                        query_text, record["name"], record["summary"]
                    ):
                        similarity_score *= config.boost_factor
                    
                    # Create location info if available
                    location = None
                    if record["start_line"] and record["end_line"]:
                        location = {
                            "start_line": record["start_line"],
                            "end_line": record["end_line"]
                        }
                    
                    search_result = SearchResult(
                        node_id=record["id"],
                        name=record["name"],
                        full_name=record["full_name"],
                        node_type=record["node_type"],
                        summary=record["summary"] or "",
                        raw_code=record["raw_code"] if config.include_raw_code else None,
                        similarity_score=similarity_score,
                        location=location,
                        metadata={"original_score": record["similarity_score"]}
                    )
                    
                    results.append(search_result)
                    
            except Exception as e:
                logger.error(f"Error searching {node_type} with vector index: {e}")
        
        return results
    
    async def _index_exists(self, index_name: str) -> bool:
        """Check if a vector index exists."""
        query = "SHOW INDEXES YIELD name WHERE name = $index_name RETURN count(*) as count"
        
        with self.driver.session() as session:
            try:
                result = session.run(query, index_name=index_name)
                record = result.single()
                return record["count"] > 0 if record else False
            except Exception as e:
                logger.error(f"Error checking index existence: {e}")
                return False
    
    def _is_exact_match(self, query: str, name: str, summary: str) -> bool:
        """Check if query contains exact matches with node name or key terms."""
        query_lower = query.lower()
        name_lower = name.lower()
        
        # Exact name match
        if name_lower in query_lower or query_lower in name_lower:
            return True
        
        # Check for exact matches in summary
        if summary:
            summary_lower = summary.lower()
            # Look for query terms in summary
            query_words = query_lower.split()
            for word in query_words:
                if len(word) > 3 and word in summary_lower:
                    return True
        
        return False
    
    async def search_similar_to_node(
        self, 
        node_id: str, 
        config: VectorSearchConfig = None,
        exclude_self: bool = True
    ) -> List[SearchResult]:
        """
        Find nodes similar to a given node using its embedding.
        
        Args:
            node_id: ID of the reference node
            config: Search configuration
            exclude_self: Whether to exclude the reference node from results
            
        Returns:
            List of similar nodes
        """
        if config is None:
            config = VectorSearchConfig()
        
        # Get the reference node's embedding
        query = """
        MATCH (n {id: $node_id})
        RETURN n.embedding as embedding, labels(n)[0] as node_type
        """
        
        reference_embedding = None
        reference_type = None
        
        with self.driver.session() as session:
            result = session.run(query, node_id=node_id)
            record = result.single()
            
            if not record or not record["embedding"]:
                logger.error(f"No embedding found for node: {node_id}")
                return []
            
            reference_embedding = record["embedding"]
            reference_type = record["node_type"]
        
        # Search for similar nodes of the same type
        similar_results = await self._search_node_type(
            reference_type, reference_embedding, "", config
        )
        
        # Exclude the reference node if requested
        if exclude_self:
            similar_results = [r for r in similar_results if r.node_id != node_id]
        
        return similar_results
    
    async def search_by_embedding(
        self, 
        embedding: List[float], 
        node_types: Optional[List[str]] = None,
        config: VectorSearchConfig = None
    ) -> List[SearchResult]:
        """
        Search using a pre-computed embedding vector.
        
        Args:
            embedding: Vector embedding to search with
            node_types: Specific node types to search
            config: Search configuration
            
        Returns:
            List of similar nodes
        """
        if config is None:
            config = VectorSearchConfig()
        
        if node_types is None:
            node_types = list(self.vector_indexes.keys())
        
        all_results = []
        
        for node_type in node_types:
            if node_type not in self.vector_indexes:
                continue
                
            results = await self._search_node_type(
                node_type, embedding, "", config
            )
            all_results.extend(results)
        
        # Sort and limit globally
        all_results.sort(key=lambda x: x.similarity_score, reverse=True)
        return all_results[:config.max_results]
    
    async def get_node_details(self, node_id: str) -> Optional[SearchResult]:
        """Get detailed information about a specific node."""
        query = """
        MATCH (n {id: $node_id})
        RETURN 
            n.id as id,
            n.name as name,
            n.full_name as full_name,
            labels(n)[0] as node_type,
            n.generated_summary as summary,
            n.raw_code as raw_code,
            n.start_line as start_line,
            n.end_line as end_line,
            n.path as path,
            n.visibility as visibility,
            n.type as type_info
        """
        
        with self.driver.session() as session:
            result = session.run(query, node_id=node_id)
            record = result.single()
            
            if not record:
                return None
            
            location = None
            if record["start_line"] and record["end_line"]:
                location = {
                    "start_line": record["start_line"],
                    "end_line": record["end_line"]
                }
            
            metadata = {}
            if record["path"]:
                metadata["path"] = record["path"]
            if record["visibility"]:
                metadata["visibility"] = record["visibility"]
            if record["type_info"]:
                metadata["type"] = record["type_info"]
            
            return SearchResult(
                node_id=record["id"],
                name=record["name"],
                full_name=record["full_name"],
                node_type=record["node_type"],
                summary=record["summary"] or "",
                raw_code=record["raw_code"],
                similarity_score=1.0,  # Perfect match for direct lookup
                location=location,
                metadata=metadata
            )
    
    def get_search_statistics(self) -> Dict[str, Any]:
        """Get statistics about available embeddings and search capabilities."""
        stats = {}
        
        with self.driver.session() as session:
            for node_type, index_name in self.vector_indexes.items():
                # Count nodes with embeddings
                query = f"""
                MATCH (n:{node_type})
                WHERE n.embedding IS NOT NULL AND size(n.embedding) > 0
                RETURN count(n) as count
                """
                
                result = session.run(query)
                record = result.single()
                count = record["count"] if record else 0
                
                stats[node_type] = {
                    "nodes_with_embeddings": count,
                    "index_name": index_name
                }
        
        return stats

# Example usage and testing
async def main():
    """Example usage of VectorSearchEngine."""
    search_engine = VectorSearchEngine(
        neo4j_uri="bolt://localhost:7687",
        neo4j_user="neo4j",
        neo4j_password="password"
    )
    
    try:
        # Search for payment-related code
        results = await search_engine.search_by_text(
            "payment processing stripe api",
            config=VectorSearchConfig(max_results=10, include_raw_code=True)
        )
        
        print(f"Found {len(results)} results:")
        for result in results:
            print(f"- {result.name} ({result.node_type}): {result.similarity_score:.3f}")
            print(f"  {result.summary}")
            print()
        
        # Get search statistics
        stats = search_engine.get_search_statistics()
        print("Search statistics:", stats)
        
    finally:
        search_engine.close()

if __name__ == "__main__":
    asyncio.run(main()) 