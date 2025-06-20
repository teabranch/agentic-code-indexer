import asyncio
from typing import List, Dict, Optional, Set, Tuple
from dataclasses import dataclass
from enum import Enum
import logging
from neo4j import GraphDatabase
from collections import defaultdict

logger = logging.getLogger(__name__)

class SummarizationLevel(Enum):
    """Hierarchical levels for summarization processing."""
    PARAMETER = 1
    VARIABLE = 2
    METHOD = 3
    FUNCTION = 4
    CLASS = 5
    INTERFACE = 6
    FILE = 7
    DIRECTORY = 8

@dataclass
class SummarizationNode:
    """Represents a node in the summarization hierarchy."""
    id: str
    name: str
    full_name: str
    node_type: str
    level: SummarizationLevel
    raw_code: Optional[str] = None
    summary: Optional[str] = None
    children_summaries: List[str] = None
    dependencies: List[str] = None
    
    def __post_init__(self):
        if self.children_summaries is None:
            self.children_summaries = []
        if self.dependencies is None:
            self.dependencies = []

class HierarchicalSummarizationOrchestrator:
    """
    Orchestrates hierarchical summarization of code elements in bottom-up fashion.
    Processes nodes in topological order considering containment relationships.
    """
    
    def __init__(self, neo4j_uri: str, neo4j_user: str, neo4j_password: str):
        self.driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
        
        # Define processing order by level
        self.level_order = [
            SummarizationLevel.PARAMETER,
            SummarizationLevel.VARIABLE,
            SummarizationLevel.METHOD,
            SummarizationLevel.FUNCTION,
            SummarizationLevel.CLASS,
            SummarizationLevel.INTERFACE,
            SummarizationLevel.FILE,
            SummarizationLevel.DIRECTORY
        ]
        
        # Map node types to summarization levels
        self.type_to_level = {
            "Parameter": SummarizationLevel.PARAMETER,
            "Variable": SummarizationLevel.VARIABLE,
            "Method": SummarizationLevel.METHOD,
            "Function": SummarizationLevel.FUNCTION,
            "Class": SummarizationLevel.CLASS,
            "Interface": SummarizationLevel.INTERFACE,
            "File": SummarizationLevel.FILE,
            "Directory": SummarizationLevel.DIRECTORY
        }
    
    def close(self):
        """Close Neo4j driver connection."""
        if self.driver:
            self.driver.close()
    
    def _get_nodes_by_level(self, level: SummarizationLevel) -> List[SummarizationNode]:
        """Get all nodes at a specific summarization level that need processing."""
        node_type = level.name.title()
        
        query = f"""
        MATCH (n:{node_type})
        WHERE (n.generated_summary IS NULL OR n.generated_summary = '')
        AND (n.summary_status IS NULL OR n.summary_status <> 'PROCESSING')
        RETURN n.id as id, n.name as name, n.full_name as full_name,
               labels(n)[0] as node_type, n.raw_code as raw_code
        ORDER BY n.full_name
        """
        
        nodes = []
        with self.driver.session() as session:
            result = session.run(query)
            for record in result:
                nodes.append(SummarizationNode(
                    id=record["id"],
                    name=record["name"],
                    full_name=record["full_name"],
                    node_type=record["node_type"],
                    level=level,
                    raw_code=record["raw_code"]
                ))
        
        return nodes
    
    def _get_children_summaries(self, node_id: str) -> List[str]:
        """Get summaries of all children nodes for context."""
        query = """
        MATCH (parent {id: $node_id})-[:CONTAINS|:DEFINES|:DECLARES]->(child)
        WHERE child.generated_summary IS NOT NULL 
        AND child.generated_summary <> ''
        RETURN child.name as name, child.generated_summary as summary
        ORDER BY child.name
        """
        
        summaries = []
        with self.driver.session() as session:
            result = session.run(query, node_id=node_id)
            for record in result:
                summaries.append(f"{record['name']}: {record['summary']}")
        
        return summaries
    
    def _get_related_summaries(self, node_id: str) -> List[str]:
        """Get summaries of related nodes (same level dependencies)."""
        query = """
        MATCH (n {id: $node_id})-[:CALLS|:USES|:REFERENCES]->(related)
        WHERE related.generated_summary IS NOT NULL 
        AND related.generated_summary <> ''
        RETURN related.name as name, related.generated_summary as summary
        LIMIT 5
        """
        
        summaries = []
        with self.driver.session() as session:
            result = session.run(query, node_id=node_id)
            for record in result:
                summaries.append(f"{record['name']}: {record['summary']}")
        
        return summaries
    
    def _mark_node_processing(self, node_id: str):
        """Mark a node as being processed to avoid duplicate work."""
        query = """
        MATCH (n {id: $node_id})
        SET n.summary_status = 'PROCESSING'
        """
        
        with self.driver.session() as session:
            session.run(query, node_id=node_id)
    
    def _mark_node_completed(self, node_id: str):
        """Mark a node as completed processing."""
        query = """
        MATCH (n {id: $node_id})
        SET n.summary_status = 'COMPLETED'
        """
        
        with self.driver.session() as session:
            session.run(query, node_id=node_id)
    
    def _check_dependencies_ready(self, node_id: str) -> bool:
        """Check if all child nodes have been summarized."""
        query = """
        MATCH (parent {id: $node_id})-[:CONTAINS|:DEFINES|:DECLARES]->(child)
        WHERE (child.generated_summary IS NULL OR child.generated_summary = '')
        AND labels(child)[0] IN ['Parameter', 'Variable', 'Method', 'Function', 'Class', 'Interface']
        RETURN count(child) as unsummarized_count
        """
        
        with self.driver.session() as session:
            result = session.run(query, node_id=node_id)
            record = result.single()
            return record["unsummarized_count"] == 0 if record else True
    
    def _enrich_node_with_context(self, node: SummarizationNode) -> SummarizationNode:
        """Enrich a node with context from its children and dependencies."""
        # Get children summaries for hierarchical context
        node.children_summaries = self._get_children_summaries(node.id)
        
        # Get related summaries for additional context
        node.dependencies = self._get_related_summaries(node.id)
        
        return node
    
    def _create_hierarchical_prompt(self, node: SummarizationNode) -> str:
        """Create a context-aware prompt for hierarchical summarization."""
        prompt_parts = [
            f"Analyze and summarize this {node.node_type.lower()}: {node.name}\n"
        ]
        
        if node.raw_code:
            prompt_parts.append(f"Code:\n{node.raw_code}\n")
        
        # Add children context if available
        if node.children_summaries:
            prompt_parts.append("Contains these components:")
            for child_summary in node.children_summaries[:10]:  # Limit context
                prompt_parts.append(f"- {child_summary}")
            prompt_parts.append("")
        
        # Add dependencies context if available
        if node.dependencies:
            prompt_parts.append("Uses/References:")
            for dep_summary in node.dependencies[:5]:  # Limit context
                prompt_parts.append(f"- {dep_summary}")
            prompt_parts.append("")
        
        # Add level-specific instructions
        if node.level == SummarizationLevel.PARAMETER:
            prompt_parts.append("Focus on: parameter type, purpose, constraints, default values")
        elif node.level == SummarizationLevel.VARIABLE:
            prompt_parts.append("Focus on: variable type, purpose, scope, usage pattern")
        elif node.level in [SummarizationLevel.METHOD, SummarizationLevel.FUNCTION]:
            prompt_parts.append("Focus on: purpose, parameters, return value, side effects, algorithm")
        elif node.level in [SummarizationLevel.CLASS, SummarizationLevel.INTERFACE]:
            prompt_parts.append("Focus on: responsibility, key methods, relationships, design patterns")
        elif node.level == SummarizationLevel.FILE:
            prompt_parts.append("Focus on: main purpose, key classes/functions, external dependencies")
        
        prompt_parts.append("Provide a concise technical summary (2-4 sentences):")
        
        return "\n".join(prompt_parts)
    
    async def get_nodes_ready_for_processing(self, level: SummarizationLevel, batch_size: int = 50) -> List[SummarizationNode]:
        """Get nodes at a level that are ready for processing (dependencies satisfied)."""
        nodes = self._get_nodes_by_level(level)
        ready_nodes = []
        
        for node in nodes:
            if self._check_dependencies_ready(node.id):
                # Mark as processing to avoid concurrent processing
                self._mark_node_processing(node.id)
                # Enrich with context
                enriched_node = self._enrich_node_with_context(node)
                ready_nodes.append(enriched_node)
                
                if len(ready_nodes) >= batch_size:
                    break
        
        return ready_nodes
    
    async def process_level(self, level: SummarizationLevel, llm_integration, batch_size: int = 20) -> int:
        """Process all nodes at a specific level."""
        logger.info(f"Processing summarization level: {level.name}")
        
        total_processed = 0
        
        while True:
            # Get nodes ready for processing
            ready_nodes = await self.get_nodes_ready_for_processing(level, batch_size)
            
            if not ready_nodes:
                break
            
            logger.info(f"Processing {len(ready_nodes)} {level.name.lower()} nodes")
            
            # Prepare data for LLM processing
            texts = []
            node_types = []
            contexts = []
            
            for node in ready_nodes:
                prompt = self._create_hierarchical_prompt(node)
                texts.append(prompt)
                node_types.append(node.node_type.lower())
                contexts.append(prompt)  # Use full prompt as context
            
            # Generate summaries using LLM integration
            try:
                summary_results = await llm_integration.llm_summarizer.generate_summaries_batch(
                    texts, node_types, contexts, max_concurrent=5
                )
                
                # Update nodes with summaries
                successful_updates = 0
                for node, summary_result in zip(ready_nodes, summary_results):
                    if await llm_integration.update_node_summary(node.id, summary_result.summary):
                        self._mark_node_completed(node.id)
                        successful_updates += 1
                    else:
                        # Reset processing status on failure
                        self._mark_node_completed(node.id)
                
                total_processed += successful_updates
                logger.info(f"Successfully processed {successful_updates}/{len(ready_nodes)} nodes")
                
            except Exception as e:
                logger.error(f"Error processing level {level.name}: {e}")
                # Reset processing status for failed nodes
                for node in ready_nodes:
                    self._mark_node_completed(node.id)
                break
        
        logger.info(f"Completed level {level.name}: {total_processed} nodes processed")
        return total_processed
    
    async def run_hierarchical_summarization(self, llm_integration, batch_size: int = 20) -> Dict[str, int]:
        """
        Run complete hierarchical summarization in bottom-up order.
        Processes each level only when its dependencies are satisfied.
        """
        logger.info("Starting hierarchical summarization process")
        
        stats = {}
        total_processed = 0
        
        # Process each level in order
        for level in self.level_order:
            processed_count = await self.process_level(level, llm_integration, batch_size)
            stats[level.name.lower()] = processed_count
            total_processed += processed_count
            
            # Small delay between levels
            await asyncio.sleep(1)
        
        stats["total_processed"] = total_processed
        logger.info(f"Hierarchical summarization complete: {total_processed} total nodes processed")
        
        return stats
    
    def get_summarization_progress(self) -> Dict[str, Dict[str, int]]:
        """Get current progress of summarization by level."""
        progress = {}
        
        for level in self.level_order:
            node_type = level.name.title()
            
            query = f"""
            MATCH (n:{node_type})
            RETURN 
                count(n) as total,
                count(CASE WHEN n.generated_summary IS NOT NULL AND n.generated_summary <> '' THEN 1 END) as completed,
                count(CASE WHEN n.summary_status = 'PROCESSING' THEN 1 END) as processing
            """
            
            with self.driver.session() as session:
                result = session.run(query)
                record = result.single()
                
                if record and record["total"] > 0:
                    progress[level.name.lower()] = {
                        "total": record["total"],
                        "completed": record["completed"],
                        "processing": record["processing"],
                        "remaining": record["total"] - record["completed"]
                    }
        
        return progress
    
    def reset_processing_status(self):
        """Reset all processing status markers (useful for recovery)."""
        query = """
        MATCH (n)
        WHERE n.summary_status = 'PROCESSING'
        REMOVE n.summary_status
        """
        
        with self.driver.session() as session:
            result = session.run(query)
            logger.info("Reset processing status for all nodes")

# Example usage
async def main():
    """Example usage of hierarchical summarization orchestrator."""
    orchestrator = HierarchicalSummarizationOrchestrator(
        neo4j_uri="bolt://localhost:7687",
        neo4j_user="neo4j",
        neo4j_password="password"
    )
    
    try:
        # Get current progress
        progress = orchestrator.get_summarization_progress()
        print("Summarization progress:", progress)
        
        # Reset any stuck processing status
        orchestrator.reset_processing_status()
        
    finally:
        orchestrator.close()

if __name__ == "__main__":
    asyncio.run(main()) 