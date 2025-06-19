import asyncio
from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass
from neo4j import GraphDatabase
import logging
from .common_data_format import ChunkerOutput, BaseNode, Relationship

logger = logging.getLogger(__name__)

@dataclass
class IngestionStats:
    """Statistics for a graph ingestion operation."""
    nodes_created: int = 0
    nodes_updated: int = 0
    relationships_created: int = 0
    relationships_updated: int = 0
    files_processed: int = 0
    errors: int = 0

class GraphIngestion:
    """
    Handles efficient ingestion of chunker output into Neo4j database
    using batched operations and idempotent writes.
    """
    
    def __init__(self, neo4j_uri: str, neo4j_user: str, neo4j_password: str, batch_size: int = 1000):
        self.driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
        self.batch_size = batch_size
        
    def close(self):
        """Close the Neo4j driver connection."""
        if self.driver:
            self.driver.close()
    
    def _prepare_node_for_cypher(self, node: BaseNode) -> Dict[str, Any]:
        """Convert a BaseNode to a dictionary suitable for Cypher queries."""
        node_dict = {
            "id": node.id,
            "label": node.label,
            "name": node.name,
            "full_name": node.full_name,
        }
        
        # Add optional fields if they exist
        if hasattr(node, 'raw_code') and node.raw_code:
            node_dict["raw_code"] = node.raw_code
        if hasattr(node, 'location') and node.location:
            node_dict["start_line"] = node.location.start_line
            node_dict["end_line"] = node.location.end_line
            if node.location.start_column is not None:
                node_dict["start_column"] = node.location.start_column
            if node.location.end_column is not None:
                node_dict["end_column"] = node.location.end_column
        
        # Add type-specific properties
        if hasattr(node, 'path'):  # File node
            node_dict.update({
                "path": node.path,
                "absolute_path": node.absolute_path,
                "extension": node.extension,
                "size": node.size,
                "checksum": node.checksum,
                "language": getattr(node, 'language', 'unknown')
            })
            
        elif hasattr(node, 'visibility'):  # Class/Interface/Method/Variable nodes
            node_dict["visibility"] = node.visibility
            
            if hasattr(node, 'is_abstract'):  # Class/Method nodes
                node_dict["is_abstract"] = node.is_abstract
            if hasattr(node, 'is_static'):
                node_dict["is_static"] = node.is_static
            if hasattr(node, 'return_type'):  # Method/Function nodes
                node_dict["return_type"] = node.return_type
            if hasattr(node, 'signature'):
                node_dict["signature"] = node.signature
            if hasattr(node, 'type'):  # Variable/Parameter nodes
                node_dict["type"] = node.type
            if hasattr(node, 'value'):
                node_dict["value"] = node.value
        
        # Add any additional properties
        if hasattr(node, 'properties') and node.properties:
            for key, value in node.properties.items():
                if key not in node_dict:  # Don't override existing fields
                    node_dict[key] = value
        
        return node_dict
    
    def _get_node_label(self, node: BaseNode) -> str:
        """Get the Neo4j label for a node based on its type."""
        label_map = {
            "File": "File",
            "Directory": "Directory", 
            "Class": "Class",
            "Interface": "Interface",
            "Method": "Method",
            "Function": "Function",
            "Variable": "Variable",
            "Parameter": "Parameter",
            "Import": "Import",
            "Export": "Export"
        }
        return label_map.get(node.label, "Node")
    
    async def ingest_chunker_output(self, chunker_output: ChunkerOutput) -> IngestionStats:
        """
        Ingest a single ChunkerOutput into Neo4j.
        Uses batched operations for performance.
        """
        stats = IngestionStats()
        
        try:
            # Process nodes in batches
            nodes_batches = [
                chunker_output.nodes[i:i + self.batch_size]
                for i in range(0, len(chunker_output.nodes), self.batch_size)
            ]
            
            for batch in nodes_batches:
                node_stats = await self._ingest_nodes_batch(batch)
                stats.nodes_created += node_stats.nodes_created
                stats.nodes_updated += node_stats.nodes_updated
                stats.errors += node_stats.errors
            
            # Process relationships in batches
            rel_batches = [
                chunker_output.relationships[i:i + self.batch_size]
                for i in range(0, len(chunker_output.relationships), self.batch_size)
            ]
            
            for batch in rel_batches:
                rel_stats = await self._ingest_relationships_batch(batch)
                stats.relationships_created += rel_stats.relationships_created
                stats.relationships_updated += rel_stats.relationships_updated
                stats.errors += rel_stats.errors
            
            stats.files_processed = len(chunker_output.processed_files)
            
            logger.info(f"Ingestion complete: {stats.nodes_created} nodes created, "
                       f"{stats.relationships_created} relationships created")
            
        except Exception as e:
            logger.error(f"Error during ingestion: {e}")
            stats.errors += 1
        
        return stats
    
    async def _ingest_nodes_batch(self, nodes: List[BaseNode]) -> IngestionStats:
        """Ingest a batch of nodes using UNWIND and MERGE operations."""
        stats = IngestionStats()
        
        if not nodes:
            return stats
        
        # Group nodes by label for efficient processing
        nodes_by_label = {}
        for node in nodes:
            label = self._get_node_label(node)
            if label not in nodes_by_label:
                nodes_by_label[label] = []
            nodes_by_label[label].append(self._prepare_node_for_cypher(node))
        
        # Process each label group
        for label, node_data in nodes_by_label.items():
            try:
                # Build dynamic MERGE query based on node properties
                query = f"""
                UNWIND $nodes as node_data
                MERGE (n:{label} {{id: node_data.id}})
                SET n += node_data
                RETURN COUNT(n) as count
                """
                
                with self.driver.session() as session:
                    result = session.run(query, nodes=node_data)
                    record = result.single()
                    if record:
                        stats.nodes_created += record["count"]
                        
                logger.debug(f"Processed {len(node_data)} {label} nodes")
                
            except Exception as e:
                logger.error(f"Error ingesting {label} nodes: {e}")
                stats.errors += len(node_data)
        
        return stats
    
    async def _ingest_relationships_batch(self, relationships: List[Relationship]) -> IngestionStats:
        """Ingest a batch of relationships using UNWIND and MERGE operations."""
        stats = IngestionStats()
        
        if not relationships:
            return stats
        
        # Prepare relationship data
        rel_data = []
        for rel in relationships:
            rel_dict = {
                "source_id": rel.source_id,
                "target_id": rel.target_id,
                "type": rel.type,
                "properties": rel.properties or {}
            }
            rel_data.append(rel_dict)
        
        try:
            # Use dynamic relationship creation based on type
            query = """
            UNWIND $relationships as rel_data
            MATCH (source {id: rel_data.source_id})
            MATCH (target {id: rel_data.target_id})
            CALL apoc.create.relationship(source, rel_data.type, rel_data.properties, target)
            YIELD rel
            RETURN COUNT(rel) as count
            """
            
            with self.driver.session() as session:
                result = session.run(query, relationships=rel_data)
                record = result.single()
                if record:
                    stats.relationships_created += record["count"]
                    
            logger.debug(f"Processed {len(rel_data)} relationships")
            
        except Exception as e:
            # Fallback to simpler approach if APOC is not available
            logger.warning(f"APOC not available, using fallback method: {e}")
            stats = await self._ingest_relationships_fallback(relationships)
        
        return stats
    
    async def _ingest_relationships_fallback(self, relationships: List[Relationship]) -> IngestionStats:
        """Fallback method for relationship ingestion without APOC."""
        stats = IngestionStats()
        
        # Group relationships by type for efficiency
        rels_by_type = {}
        for rel in relationships:
            rel_type = rel.type
            if rel_type not in rels_by_type:
                rels_by_type[rel_type] = []
            rels_by_type[rel_type].append({
                "source_id": rel.source_id,
                "target_id": rel.target_id,
                "properties": rel.properties or {}
            })
        
        # Process each relationship type
        for rel_type, rel_data in rels_by_type.items():
            try:
                query = f"""
                UNWIND $relationships as rel_data
                MATCH (source {{id: rel_data.source_id}})
                MATCH (target {{id: rel_data.target_id}})
                MERGE (source)-[r:{rel_type}]->(target)
                SET r += rel_data.properties
                RETURN COUNT(r) as count
                """
                
                with self.driver.session() as session:
                    result = session.run(query, relationships=rel_data)
                    record = result.single()
                    if record:
                        stats.relationships_created += record["count"]
                        
            except Exception as e:
                logger.error(f"Error creating {rel_type} relationships: {e}")
                stats.errors += len(rel_data)
        
        return stats
    
    async def delete_file_subgraph(self, file_path: str) -> int:
        """
        Delete a file node and all its associated nodes and relationships.
        Returns the number of nodes deleted.
        """
        try:
            query = """
            MATCH (f:File {path: $file_path})
            OPTIONAL MATCH (f)-[*]-(n)
            WITH f, collect(DISTINCT n) as related_nodes
            DETACH DELETE f
            FOREACH (node in related_nodes | DETACH DELETE node)
            RETURN count(f) + size(related_nodes) as deleted_count
            """
            
            with self.driver.session() as session:
                result = session.run(query, file_path=file_path)
                record = result.single()
                deleted_count = record["deleted_count"] if record else 0
                
            logger.info(f"Deleted file subgraph for {file_path}: {deleted_count} nodes")
            return deleted_count
            
        except Exception as e:
            logger.error(f"Error deleting file subgraph {file_path}: {e}")
            return 0
    
    async def ingest_multiple_outputs(self, chunker_outputs: List[ChunkerOutput]) -> IngestionStats:
        """
        Ingest multiple ChunkerOutputs efficiently.
        Combines data for optimal batching.
        """
        total_stats = IngestionStats()
        
        # Combine all nodes and relationships
        all_nodes = []
        all_relationships = []
        all_processed_files = []
        
        for output in chunker_outputs:
            all_nodes.extend(output.nodes)
            all_relationships.extend(output.relationships)
            all_processed_files.extend(output.processed_files)
        
        # Create a combined output for efficient processing
        combined_output = ChunkerOutput(
            language="multi",
            version="1.0.0",
            processed_files=all_processed_files,
            nodes=all_nodes,
            relationships=all_relationships,
            metadata={"total_outputs": len(chunker_outputs)}
        )
        
        logger.info(f"Ingesting combined data: {len(all_nodes)} nodes, "
                   f"{len(all_relationships)} relationships from {len(chunker_outputs)} outputs")
        
        stats = await self.ingest_chunker_output(combined_output)
        return stats
    
    def get_ingestion_summary(self) -> Dict[str, Any]:
        """Get summary statistics about the current database state."""
        summary = {}
        
        with self.driver.session() as session:
            try:
                # Node counts by type
                result = session.run("""
                MATCH (n)
                RETURN labels(n)[0] as label, count(n) as count
                ORDER BY count DESC
                """)
                
                node_counts = {record["label"]: record["count"] for record in result}
                summary["node_counts"] = node_counts
                
                # Relationship counts by type
                result = session.run("""
                MATCH ()-[r]->()
                RETURN type(r) as rel_type, count(r) as count
                ORDER BY count DESC
                """)
                
                rel_counts = {record["rel_type"]: record["count"] for record in result}
                summary["relationship_counts"] = rel_counts
                
                # File statistics
                result = session.run("""
                MATCH (f:File)
                RETURN count(f) as file_count,
                       collect(DISTINCT f.language) as languages,
                       sum(f.size) as total_size
                """)
                
                record = result.single()
                if record:
                    summary["files"] = {
                        "count": record["file_count"],
                        "languages": record["languages"],
                        "total_size": record["total_size"]
                    }
                
            except Exception as e:
                logger.error(f"Error getting ingestion summary: {e}")
        
        return summary

# Example usage
async def main():
    """Example usage of GraphIngestion."""
    ingestion = GraphIngestion(
        neo4j_uri="bolt://localhost:7687",
        neo4j_user="neo4j",
        neo4j_password="password"
    )
    
    try:
        # Get current state summary
        summary = ingestion.get_ingestion_summary()
        print("Database summary:", summary)
        
    finally:
        ingestion.close()

if __name__ == "__main__":
    asyncio.run(main()) 