import asyncio
from typing import List, Dict, Set, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import logging
from neo4j import GraphDatabase
from .vector_search import SearchResult

logger = logging.getLogger(__name__)

class TraversalDirection(Enum):
    """Direction for relationship traversal."""
    OUTGOING = "outgoing"
    INCOMING = "incoming"
    BOTH = "both"

@dataclass
class TraversalRule:
    """Defines how to traverse relationships from a node type."""
    from_node_type: str
    relationship_type: str
    to_node_type: Optional[str] = None
    direction: TraversalDirection = TraversalDirection.OUTGOING
    max_depth: int = 1
    include_properties: List[str] = None

@dataclass
class GraphNode:
    """Represents a node in the graph traversal result."""
    node_id: str
    name: str
    full_name: str
    node_type: str
    summary: str
    raw_code: Optional[str] = None
    metadata: Dict[str, Any] = None
    depth: int = 0
    relationship_path: List[str] = None

@dataclass
class GraphContext:
    """Contains the expanded context around search results."""
    central_nodes: List[SearchResult]
    related_nodes: List[GraphNode]
    relationships: List[Dict[str, Any]]
    traversal_summary: Dict[str, Any]

class GraphTraversalEngine:
    """
    Implements Graph Retrieval-Augmented Generation (GraphRAG) by traversing 
    relationships to gather context around search results.
    """
    
    def __init__(self, neo4j_uri: str, neo4j_user: str, neo4j_password: str):
        self.driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
        self._init_traversal_rules()
    
    def _init_traversal_rules(self):
        """Initialize default traversal rules for different node types."""
        self.traversal_rules = {
            # File-level traversal
            "File": [
                TraversalRule("File", "CONTAINS", "Class"),
                TraversalRule("File", "CONTAINS", "Function"),
                TraversalRule("File", "CONTAINS", "Interface"),
                TraversalRule("File", "IMPORTS", direction=TraversalDirection.OUTGOING),
                TraversalRule("File", "IMPORTS", direction=TraversalDirection.INCOMING),
            ],
            
            # Class-level traversal  
            "Class": [
                TraversalRule("Class", "CONTAINS", direction=TraversalDirection.INCOMING),  # File that contains this class
                TraversalRule("Class", "DEFINES", "Method"),
                TraversalRule("Class", "DEFINES", "Variable"),
                TraversalRule("Class", "EXTENDS", "Class"),
                TraversalRule("Class", "IMPLEMENTS", "Interface"),
                TraversalRule("Class", "EXTENDS", direction=TraversalDirection.INCOMING),  # Classes that extend this
                TraversalRule("Class", "IMPLEMENTS", direction=TraversalDirection.INCOMING),  # Classes that implement this
                TraversalRule("Class", "INSTANTIATES", direction=TraversalDirection.INCOMING),  # Methods that create instances
            ],
            
            # Interface-level traversal
            "Interface": [
                TraversalRule("Interface", "CONTAINS", direction=TraversalDirection.INCOMING),
                TraversalRule("Interface", "DEFINES", "Method"),
                TraversalRule("Interface", "EXTENDS", "Interface"),
                TraversalRule("Interface", "IMPLEMENTS", direction=TraversalDirection.INCOMING),
                TraversalRule("Interface", "EXTENDS", direction=TraversalDirection.INCOMING),
            ],
            
            # Method/Function-level traversal
            "Method": [
                TraversalRule("Method", "DEFINES", direction=TraversalDirection.INCOMING),  # Class that defines this method
                TraversalRule("Method", "DECLARES", "Parameter"), 
                TraversalRule("Method", "DECLARES", "Variable"),
                TraversalRule("Method", "CALLS", "Method"),
                TraversalRule("Method", "CALLS", "Function"),
                TraversalRule("Method", "INSTANTIATES", "Class"),
                TraversalRule("Method", "CALLS", direction=TraversalDirection.INCOMING),  # Methods that call this
            ],
            
            "Function": [
                TraversalRule("Function", "CONTAINS", direction=TraversalDirection.INCOMING),  # File that contains this function
                TraversalRule("Function", "DECLARES", "Parameter"),
                TraversalRule("Function", "DECLARES", "Variable"), 
                TraversalRule("Function", "CALLS", "Function"),
                TraversalRule("Function", "CALLS", "Method"),
                TraversalRule("Function", "INSTANTIATES", "Class"),
                TraversalRule("Function", "CALLS", direction=TraversalDirection.INCOMING),
            ],
            
            # Variable-level traversal
            "Variable": [
                TraversalRule("Variable", "DECLARES", direction=TraversalDirection.INCOMING),  # Method/function that declares
                TraversalRule("Variable", "SCOPES", direction=TraversalDirection.BOTH),  # Scope relationships
            ],
            
            "Parameter": [
                TraversalRule("Parameter", "DECLARES", direction=TraversalDirection.INCOMING),
                TraversalRule("Parameter", "SCOPES", direction=TraversalDirection.BOTH),
            ]
        }
    
    def close(self):
        """Close database connection."""
        if self.driver:
            self.driver.close()
    
    async def expand_context(
        self, 
        search_results: List[SearchResult],
        max_related_nodes: int = 50,
        include_source_code: bool = False,
        custom_rules: Optional[Dict[str, List[TraversalRule]]] = None
    ) -> GraphContext:
        """
        Expand context around search results by traversing relationships.
        
        Args:
            search_results: Initial search results to expand from
            max_related_nodes: Maximum number of related nodes to include
            include_source_code: Whether to include raw code in results
            custom_rules: Custom traversal rules (overrides defaults)
            
        Returns:
            GraphContext with expanded information
        """
        if not search_results:
            return GraphContext([], [], [], {})
        
        # Use custom rules if provided
        rules = custom_rules if custom_rules else self.traversal_rules
        
        # Collect all related nodes and relationships
        all_related_nodes = []
        all_relationships = []
        processed_node_ids = set()
        
        # Process each search result
        for result in search_results:
            if result.node_id in processed_node_ids:
                continue
                
            related_nodes, relationships = await self._traverse_from_node(
                result.node_id, 
                result.node_type,
                rules,
                max_related_nodes - len(all_related_nodes),
                include_source_code,
                processed_node_ids
            )
            
            all_related_nodes.extend(related_nodes)
            all_relationships.extend(relationships)
            processed_node_ids.add(result.node_id)
            
            # Stop if we've hit the limit
            if len(all_related_nodes) >= max_related_nodes:
                break
        
        # Create traversal summary
        traversal_summary = self._create_traversal_summary(
            search_results, all_related_nodes, all_relationships
        )
        
        return GraphContext(
            central_nodes=search_results,
            related_nodes=all_related_nodes[:max_related_nodes],
            relationships=all_relationships,
            traversal_summary=traversal_summary
        )
    
    async def _traverse_from_node(
        self, 
        node_id: str, 
        node_type: str,
        rules: Dict[str, List[TraversalRule]],
        max_nodes: int,
        include_source_code: bool,
        processed_ids: Set[str]
    ) -> Tuple[List[GraphNode], List[Dict[str, Any]]]:
        """Traverse relationships from a single node."""
        
        if node_type not in rules:
            logger.warning(f"No traversal rules defined for node type: {node_type}")
            return [], []
        
        related_nodes = []
        relationships = []
        
        for rule in rules[node_type]:
            if len(related_nodes) >= max_nodes:
                break
                
            nodes, rels = await self._apply_traversal_rule(
                node_id, rule, max_nodes - len(related_nodes), 
                include_source_code, processed_ids
            )
            
            related_nodes.extend(nodes)
            relationships.extend(rels)
        
        return related_nodes, relationships
    
    async def _apply_traversal_rule(
        self,
        start_node_id: str,
        rule: TraversalRule,
        max_nodes: int,
        include_source_code: bool,
        processed_ids: Set[str]
    ) -> Tuple[List[GraphNode], List[Dict[str, Any]]]:
        """Apply a single traversal rule to get related nodes."""
        
        # Build the traversal query based on rule
        direction_clause = self._get_direction_clause(rule)
        type_filter = f":{rule.to_node_type}" if rule.to_node_type else ""
        
        # Build query with optional depth limit
        if rule.max_depth == 1:
            path_pattern = f"(start)-{direction_clause}[r:{rule.relationship_type}]->(related{type_filter})"
        else:
            path_pattern = f"(start)-{direction_clause}[r:{rule.relationship_type}*1..{rule.max_depth}]->(related{type_filter})"
        
        query = f"""
        MATCH (start {{id: $start_id}})
        MATCH {path_pattern}
        WHERE related.id <> $start_id
        RETURN 
            related.id as id,
            related.name as name,
            related.full_name as full_name,
            labels(related)[0] as node_type,
            related.generated_summary as summary,
            {'related.raw_code as raw_code,' if include_source_code else ''}
            related.start_line as start_line,
            related.end_line as end_line,
            related.path as path,
            related.visibility as visibility,
            related.type as type_info,
            r as relationship,
            length(r) as depth
        ORDER BY depth, related.name
        LIMIT $limit
        """
        
        nodes = []
        relationships = []
        
        with self.driver.session() as session:
            try:
                result = session.run(
                    query,
                    start_id=start_node_id,
                    limit=max_nodes
                )
                
                for record in result:
                    node_id = record["id"]
                    if node_id in processed_ids:
                        continue
                    
                    # Create metadata
                    metadata = {}
                    if record["path"]:
                        metadata["path"] = record["path"]
                    if record["visibility"]:
                        metadata["visibility"] = record["visibility"]
                    if record["type_info"]:
                        metadata["type"] = record["type_info"]
                    
                    # Create graph node
                    graph_node = GraphNode(
                        node_id=node_id,
                        name=record["name"],
                        full_name=record["full_name"],
                        node_type=record["node_type"],
                        summary=record["summary"] or "",
                        raw_code=record.get("raw_code") if include_source_code else None,
                        metadata=metadata,
                        depth=record["depth"],
                        relationship_path=[rule.relationship_type]
                    )
                    
                    nodes.append(graph_node)
                    processed_ids.add(node_id)
                    
                    # Store relationship info
                    rel_info = {
                        "from_node": start_node_id,
                        "to_node": node_id,
                        "relationship_type": rule.relationship_type,
                        "direction": rule.direction.value,
                        "depth": record["depth"]
                    }
                    relationships.append(rel_info)
                    
            except Exception as e:
                logger.error(f"Error applying traversal rule {rule.relationship_type}: {e}")
        
        return nodes, relationships
    
    def _get_direction_clause(self, rule: TraversalRule) -> str:
        """Get the Neo4j direction clause for a traversal rule."""
        if rule.direction == TraversalDirection.OUTGOING:
            return ""
        elif rule.direction == TraversalDirection.INCOMING:
            return "<"
        else:  # BOTH
            return ""
    
    def _create_traversal_summary(
        self, 
        central_nodes: List[SearchResult],
        related_nodes: List[GraphNode], 
        relationships: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Create a summary of the traversal results."""
        
        # Count nodes by type
        node_type_counts = {}
        for node in related_nodes:
            node_type_counts[node.node_type] = node_type_counts.get(node.node_type, 0) + 1
        
        # Count relationships by type
        rel_type_counts = {}
        for rel in relationships:
            rel_type = rel["relationship_type"]
            rel_type_counts[rel_type] = rel_type_counts.get(rel_type, 0) + 1
        
        # Calculate depth distribution
        depth_counts = {}
        for node in related_nodes:
            depth = node.depth
            depth_counts[depth] = depth_counts.get(depth, 0) + 1
        
        return {
            "central_node_count": len(central_nodes),
            "related_node_count": len(related_nodes),
            "relationship_count": len(relationships),
            "node_types": node_type_counts,
            "relationship_types": rel_type_counts,
            "depth_distribution": depth_counts,
            "max_depth": max(depth_counts.keys()) if depth_counts else 0
        }
    
    async def get_call_hierarchy(
        self, 
        method_id: str, 
        direction: TraversalDirection = TraversalDirection.BOTH,
        max_depth: int = 3
    ) -> Dict[str, List[GraphNode]]:
        """
        Get the call hierarchy for a method (callers and callees).
        
        Args:
            method_id: ID of the method to analyze
            direction: Direction to traverse (callers, callees, or both)
            max_depth: Maximum depth to traverse
            
        Returns:
            Dictionary with 'callers' and 'callees' lists
        """
        result = {"callers": [], "callees": []}
        
        if direction in [TraversalDirection.INCOMING, TraversalDirection.BOTH]:
            # Find methods that call this method
            callers = await self._get_callers(method_id, max_depth)
            result["callers"] = callers
        
        if direction in [TraversalDirection.OUTGOING, TraversalDirection.BOTH]:
            # Find methods called by this method
            callees = await self._get_callees(method_id, max_depth)
            result["callees"] = callees
        
        return result
    
    async def _get_callers(self, method_id: str, max_depth: int) -> List[GraphNode]:
        """Get methods that call the specified method."""
        query = f"""
        MATCH (target {{id: $method_id}})
        MATCH (caller)-[:CALLS*1..{max_depth}]->(target)
        WHERE caller.id <> target.id
        RETURN DISTINCT
            caller.id as id,
            caller.name as name,
            caller.full_name as full_name,
            labels(caller)[0] as node_type,
            caller.generated_summary as summary,
            caller.path as path
        ORDER BY caller.name
        LIMIT 20
        """
        
        callers = []
        with self.driver.session() as session:
            result = session.run(query, method_id=method_id)
            
            for record in result:
                caller = GraphNode(
                    node_id=record["id"],
                    name=record["name"],
                    full_name=record["full_name"],
                    node_type=record["node_type"],
                    summary=record["summary"] or "",
                    metadata={"path": record["path"]} if record["path"] else None
                )
                callers.append(caller)
        
        return callers
    
    async def _get_callees(self, method_id: str, max_depth: int) -> List[GraphNode]:
        """Get methods called by the specified method."""
        query = f"""
        MATCH (source {{id: $method_id}})
        MATCH (source)-[:CALLS*1..{max_depth}]->(callee)
        WHERE callee.id <> source.id
        RETURN DISTINCT
            callee.id as id,
            callee.name as name,
            callee.full_name as full_name,
            labels(callee)[0] as node_type,
            callee.generated_summary as summary,
            callee.path as path
        ORDER BY callee.name
        LIMIT 20
        """
        
        callees = []
        with self.driver.session() as session:
            result = session.run(query, method_id=method_id)
            
            for record in result:
                callee = GraphNode(
                    node_id=record["id"],
                    name=record["name"],
                    full_name=record["full_name"],
                    node_type=record["node_type"],
                    summary=record["summary"] or "",
                    metadata={"path": record["path"]} if record["path"] else None
                )
                callees.append(callee)
        
        return callees
    
    async def get_inheritance_hierarchy(self, class_id: str) -> Dict[str, List[GraphNode]]:
        """
        Get the inheritance hierarchy for a class (ancestors and descendants).
        
        Args:
            class_id: ID of the class to analyze
            
        Returns:
            Dictionary with 'ancestors' and 'descendants' lists
        """
        ancestors = await self._get_ancestors(class_id)
        descendants = await self._get_descendants(class_id)
        
        return {
            "ancestors": ancestors,
            "descendants": descendants
        }
    
    async def _get_ancestors(self, class_id: str) -> List[GraphNode]:
        """Get parent classes and interfaces."""
        query = """
        MATCH (child {id: $class_id})
        MATCH (child)-[:EXTENDS|IMPLEMENTS*1..5]->(ancestor)
        WHERE ancestor.id <> child.id
        RETURN DISTINCT
            ancestor.id as id,
            ancestor.name as name,
            ancestor.full_name as full_name,
            labels(ancestor)[0] as node_type,
            ancestor.generated_summary as summary,
            ancestor.path as path
        ORDER BY ancestor.name
        """
        
        ancestors = []
        with self.driver.session() as session:
            result = session.run(query, class_id=class_id)
            
            for record in result:
                ancestor = GraphNode(
                    node_id=record["id"],
                    name=record["name"],
                    full_name=record["full_name"],
                    node_type=record["node_type"],
                    summary=record["summary"] or "",
                    metadata={"path": record["path"]} if record["path"] else None
                )
                ancestors.append(ancestor)
        
        return ancestors
    
    async def _get_descendants(self, class_id: str) -> List[GraphNode]:
        """Get child classes that extend or implement this class."""
        query = """
        MATCH (parent {id: $class_id})
        MATCH (descendant)-[:EXTENDS|IMPLEMENTS*1..5]->(parent)
        WHERE descendant.id <> parent.id
        RETURN DISTINCT
            descendant.id as id,
            descendant.name as name,
            descendant.full_name as full_name,
            labels(descendant)[0] as node_type,
            descendant.generated_summary as summary,
            descendant.path as path
        ORDER BY descendant.name
        """
        
        descendants = []
        with self.driver.session() as session:
            result = session.run(query, class_id=class_id)
            
            for record in result:
                descendant = GraphNode(
                    node_id=record["id"],
                    name=record["name"],
                    full_name=record["full_name"],
                    node_type=record["node_type"],
                    summary=record["summary"] or "",
                    metadata={"path": record["path"]} if record["path"] else None
                )
                descendants.append(descendant)
        
        return descendants

# Example usage
async def main():
    """Example usage of GraphTraversalEngine."""
    traversal_engine = GraphTraversalEngine(
        neo4j_uri="bolt://localhost:7687",
        neo4j_user="neo4j",
        neo4j_password="password"
    )
    
    try:
        # Example: Get call hierarchy for a method
        call_hierarchy = await traversal_engine.get_call_hierarchy(
            "method_123", 
            direction=TraversalDirection.BOTH,
            max_depth=2
        )
        
        print("Call Hierarchy:")
        print(f"Callers: {len(call_hierarchy['callers'])}")
        print(f"Callees: {len(call_hierarchy['callees'])}")
        
        # Example: Get inheritance hierarchy for a class
        inheritance = await traversal_engine.get_inheritance_hierarchy("class_456")
        print(f"\nInheritance Hierarchy:")
        print(f"Ancestors: {len(inheritance['ancestors'])}")
        print(f"Descendants: {len(inheritance['descendants'])}")
        
    finally:
        traversal_engine.close()

if __name__ == "__main__":
    asyncio.run(main()) 