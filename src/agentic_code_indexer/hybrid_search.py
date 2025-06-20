import asyncio
import re
from typing import List, Dict, Set, Any, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
import logging
from neo4j import GraphDatabase
from .vector_search import VectorSearchEngine, SearchResult, VectorSearchConfig
from .graph_traversal import GraphTraversalEngine, GraphContext, TraversalDirection

logger = logging.getLogger(__name__)

class QueryType(Enum):
    """Types of search queries."""
    SEMANTIC = "semantic"  # Natural language semantic search
    ENTITY = "entity"  # Direct entity lookup by name
    HYBRID = "hybrid"  # Combination of semantic and entity search
    CONTEXTUAL = "contextual"  # Semantic search with graph context expansion

@dataclass
class QueryIntent:
    """Represents the parsed intent of a search query."""
    query_type: QueryType
    semantic_terms: List[str] = field(default_factory=list)
    entity_names: List[str] = field(default_factory=list)
    node_types: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    programming_terms: List[str] = field(default_factory=list)
    expand_context: bool = True
    confidence: float = 0.0

@dataclass
class HybridSearchConfig:
    """Configuration for hybrid search operations."""
    max_vector_results: int = 20
    max_entity_results: int = 10
    max_total_results: int = 30
    min_similarity_threshold: float = 0.6
    enable_context_expansion: bool = True
    max_context_nodes: int = 50
    boost_exact_matches: float = 1.5
    boost_entity_matches: float = 1.3
    include_source_code: bool = False
    expand_call_hierarchy: bool = False
    expand_inheritance: bool = False

@dataclass
class HybridSearchResult:
    """Enhanced search result with hybrid scoring and context."""
    search_result: SearchResult
    match_type: str  # "vector", "entity", "hybrid"
    hybrid_score: float
    context: Optional[GraphContext] = None
    explanation: str = ""

class QueryParser:
    """Parses natural language queries to extract search intent."""
    
    def __init__(self):
        # Programming language keywords and common terms
        self.programming_terms = {
            'class', 'method', 'function', 'variable', 'interface', 'enum',
            'constructor', 'property', 'field', 'parameter', 'return',
            'public', 'private', 'protected', 'static', 'async', 'await',
            'import', 'export', 'extends', 'implements', 'inherit', 'override',
            'abstract', 'virtual', 'final', 'const', 'let', 'var',
            'api', 'service', 'controller', 'model', 'dto', 'entity',
            'repository', 'database', 'query', 'connection', 'client',
            'http', 'request', 'response', 'json', 'xml', 'rest',
            'authenticate', 'authorize', 'login', 'logout', 'session',
            'cache', 'redis', 'memory', 'storage', 'file', 'directory',
            'test', 'mock', 'stub', 'unit', 'integration', 'e2e',
            'exception', 'error', 'try', 'catch', 'throw', 'handle',
            'log', 'logger', 'debug', 'info', 'warn', 'error'
        }
        
        # Common entity name patterns
        self.entity_patterns = [
            r'\b[A-Z][a-zA-Z]*(?:Service|Controller|Repository|Manager|Handler|Factory|Builder|Helper|Util|Utils)\b',
            r'\b[A-Z][a-zA-Z]*(?:Entity|Model|DTO|Request|Response|Config|Configuration)\b',
            r'\b[A-Z][a-zA-Z]*(?:Exception|Error)\b',
            r'\b[a-z][a-zA-Z]*(?:Api|HTTP|Rest|GraphQL)\b',
            r'\b[A-Z][a-zA-Z0-9_]*\b'  # General PascalCase identifiers
        ]
        
        # Node type keywords
        self.node_type_mapping = {
            'class': ['Class'],
            'classes': ['Class'],
            'interface': ['Interface'],
            'interfaces': ['Interface'],
            'method': ['Method'],
            'methods': ['Method'],
            'function': ['Function'],
            'functions': ['Function'],
            'variable': ['Variable'],
            'variables': ['Variable'],
            'file': ['File'],
            'files': ['File'],
        }
    
    def parse_query(self, query: str) -> QueryIntent:
        """Parse a natural language query to extract search intent."""
        query_lower = query.lower()
        words = query.split()
        
        # Extract entity names (capitalized terms, class names, etc.)
        entity_names = []
        for pattern in self.entity_patterns:
            matches = re.findall(pattern, query)
            entity_names.extend(matches)
        
        # Extract programming terms
        programming_terms = []
        for word in words:
            if word.lower() in self.programming_terms:
                programming_terms.append(word.lower())
        
        # Extract node types
        node_types = []
        for word in words:
            if word.lower() in self.node_type_mapping:
                node_types.extend(self.node_type_mapping[word.lower()])
        
        # Extract semantic terms (non-entity, non-programming words)
        semantic_terms = []
        for word in words:
            word_clean = re.sub(r'[^\w]', '', word.lower())
            if (word_clean not in self.programming_terms and 
                word_clean not in self.node_type_mapping and
                len(word_clean) > 2):
                semantic_terms.append(word_clean)
        
        # Determine query type and confidence
        query_type, confidence = self._determine_query_type(
            entity_names, programming_terms, semantic_terms
        )
        
        # Determine if context expansion is needed
        expand_context = self._should_expand_context(query_lower, programming_terms)
        
        return QueryIntent(
            query_type=query_type,
            semantic_terms=semantic_terms,
            entity_names=entity_names,
            node_types=list(set(node_types)),
            keywords=programming_terms,
            programming_terms=programming_terms,
            expand_context=expand_context,
            confidence=confidence
        )
    
    def _determine_query_type(
        self, 
        entity_names: List[str], 
        programming_terms: List[str], 
        semantic_terms: List[str]
    ) -> Tuple[QueryType, float]:
        """Determine the primary query type and confidence."""
        has_entities = len(entity_names) > 0
        has_programming = len(programming_terms) > 0
        has_semantic = len(semantic_terms) > 0
        
        if has_entities and has_semantic:
            return QueryType.HYBRID, 0.8
        elif has_entities and has_programming:
            return QueryType.HYBRID, 0.7
        elif has_entities:
            return QueryType.ENTITY, 0.9
        elif has_programming and has_semantic:
            return QueryType.CONTEXTUAL, 0.7
        elif has_semantic:
            return QueryType.SEMANTIC, 0.6
        else:
            return QueryType.SEMANTIC, 0.4
    
    def _should_expand_context(self, query: str, programming_terms: List[str]) -> bool:
        """Determine if context expansion should be performed."""
        context_indicators = [
            'calls', 'called by', 'uses', 'used by', 'implements', 'extends',
            'inherits', 'derived', 'related', 'similar', 'dependencies',
            'hierarchy', 'structure', 'architecture', 'flow', 'interaction'
        ]
        
        return any(indicator in query for indicator in context_indicators)

class HybridSearchEngine:
    """
    Advanced search engine that combines vector search, entity lookup, 
    and graph traversal for comprehensive code search.
    """
    
    def __init__(self, neo4j_uri: str, neo4j_user: str, neo4j_password: str):
        self.driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
        self.vector_engine = VectorSearchEngine(neo4j_uri, neo4j_user, neo4j_password)
        self.graph_engine = GraphTraversalEngine(neo4j_uri, neo4j_user, neo4j_password)
        self.query_parser = QueryParser()
    
    def close(self):
        """Close all database connections."""
        if self.driver:
            self.driver.close()
        self.vector_engine.close()
        self.graph_engine.close()
    
    async def search(
        self, 
        query: str, 
        config: HybridSearchConfig = None
    ) -> List[HybridSearchResult]:
        """
        Perform hybrid search combining multiple search strategies.
        
        Args:
            query: Natural language search query
            config: Search configuration options
            
        Returns:
            List of hybrid search results with scoring and context
        """
        if config is None:
            config = HybridSearchConfig()
        
        # Parse query intent
        intent = self.query_parser.parse_query(query)
        logger.info(f"Query intent: {intent.query_type.value}, confidence: {intent.confidence:.2f}")
        
        # Perform different search strategies based on intent
        all_results = []
        
        if intent.query_type in [QueryType.SEMANTIC, QueryType.HYBRID, QueryType.CONTEXTUAL]:
            # Vector-based semantic search
            vector_results = await self._semantic_search(query, intent, config)
            all_results.extend(vector_results)
        
        if intent.query_type in [QueryType.ENTITY, QueryType.HYBRID]:
            # Direct entity lookup
            entity_results = await self._entity_search(intent, config)
            all_results.extend(entity_results)
        
        if intent.query_type == QueryType.CONTEXTUAL or intent.expand_context:
            # Expand context for existing results
            all_results = await self._expand_context(all_results, config)
        
        # Deduplicate and score results
        final_results = self._merge_and_score_results(all_results, intent, config)
        
        # Sort by hybrid score and limit results
        final_results.sort(key=lambda x: x.hybrid_score, reverse=True)
        return final_results[:config.max_total_results]
    
    async def _semantic_search(
        self, 
        query: str, 
        intent: QueryIntent, 
        config: HybridSearchConfig
    ) -> List[HybridSearchResult]:
        """Perform semantic vector search."""
        vector_config = VectorSearchConfig(
            max_results=config.max_vector_results,
            min_similarity_threshold=config.min_similarity_threshold,
            boost_exact_matches=True,
            include_raw_code=config.include_source_code
        )
        
        # Use specific node types if identified
        node_types = intent.node_types if intent.node_types else None
        
        vector_results = await self.vector_engine.search_by_text(
            query, vector_config, node_types
        )
        
        hybrid_results = []
        for result in vector_results:
            hybrid_result = HybridSearchResult(
                search_result=result,
                match_type="vector",
                hybrid_score=result.similarity_score,
                explanation=f"Semantic similarity: {result.similarity_score:.3f}"
            )
            hybrid_results.append(hybrid_result)
        
        return hybrid_results
    
    async def _entity_search(
        self, 
        intent: QueryIntent, 
        config: HybridSearchConfig
    ) -> List[HybridSearchResult]:
        """Perform direct entity name lookup."""
        entity_results = []
        
        for entity_name in intent.entity_names:
            results = await self._search_by_name(entity_name, config)
            
            for result in results:
                hybrid_result = HybridSearchResult(
                    search_result=result,
                    match_type="entity",
                    hybrid_score=result.similarity_score * config.boost_entity_matches,
                    explanation=f"Entity name match: {entity_name}"
                )
                entity_results.append(hybrid_result)
        
        return entity_results
    
    async def _search_by_name(
        self, 
        name: str, 
        config: HybridSearchConfig
    ) -> List[SearchResult]:
        """Search for entities by exact or partial name match."""
        query = """
        MATCH (n)
        WHERE n.name CONTAINS $name OR n.full_name CONTAINS $name
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
            n.type as type_info,
            CASE 
                WHEN n.name = $name THEN 1.0
                WHEN n.full_name = $name THEN 0.9
                WHEN n.name CONTAINS $name THEN 0.8
                ELSE 0.7
            END as match_score
        ORDER BY match_score DESC, n.name
        LIMIT $limit
        """
        
        results = []
        with self.driver.session() as session:
            result = session.run(
                query, 
                name=name, 
                limit=config.max_entity_results
            )
            
            for record in result:
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
                
                search_result = SearchResult(
                    node_id=record["id"],
                    name=record["name"],
                    full_name=record["full_name"],
                    node_type=record["node_type"],
                    summary=record["summary"] or "",
                    raw_code=record["raw_code"] if config.include_source_code else None,
                    similarity_score=record["match_score"],
                    location=location,
                    metadata=metadata
                )
                results.append(search_result)
        
        return results
    
    async def _expand_context(
        self, 
        results: List[HybridSearchResult], 
        config: HybridSearchConfig
    ) -> List[HybridSearchResult]:
        """Expand context for search results using graph traversal."""
        if not config.enable_context_expansion or not results:
            return results
        
        # Select top results for context expansion
        top_results = results[:10]
        search_results = [r.search_result for r in top_results]
        
        # Expand context using graph traversal
        context = await self.graph_engine.expand_context(
            search_results,
            max_related_nodes=config.max_context_nodes,
            include_source_code=config.include_source_code
        )
        
        # Add context to results
        for i, hybrid_result in enumerate(top_results):
            hybrid_result.context = context
            hybrid_result.explanation += f" | Context: {len(context.related_nodes)} related nodes"
        
        # Add specific hierarchical context if requested
        if config.expand_call_hierarchy or config.expand_inheritance:
            for hybrid_result in top_results:
                await self._add_hierarchical_context(hybrid_result, config)
        
        return results
    
    async def _add_hierarchical_context(
        self, 
        result: HybridSearchResult, 
        config: HybridSearchConfig
    ):
        """Add call hierarchy and inheritance context to a result."""
        node_type = result.search_result.node_type
        
        if config.expand_call_hierarchy and node_type in ["Method", "Function"]:
            call_hierarchy = await self.graph_engine.get_call_hierarchy(
                result.search_result.node_id,
                direction=TraversalDirection.BOTH,
                max_depth=2
            )
            
            if result.context:
                result.context.traversal_summary["call_hierarchy"] = {
                    "callers": len(call_hierarchy["callers"]),
                    "callees": len(call_hierarchy["callees"])
                }
        
        if config.expand_inheritance and node_type in ["Class", "Interface"]:
            inheritance = await self.graph_engine.get_inheritance_hierarchy(
                result.search_result.node_id
            )
            
            if result.context:
                result.context.traversal_summary["inheritance"] = {
                    "ancestors": len(inheritance["ancestors"]),
                    "descendants": len(inheritance["descendants"])
                }
    
    def _merge_and_score_results(
        self, 
        all_results: List[HybridSearchResult], 
        intent: QueryIntent, 
        config: HybridSearchConfig
    ) -> List[HybridSearchResult]:
        """Merge duplicate results and compute hybrid scores."""
        # Deduplicate by node_id
        seen_nodes = set()
        unique_results = []
        
        for result in all_results:
            node_id = result.search_result.node_id
            if node_id not in seen_nodes:
                seen_nodes.add(node_id)
                unique_results.append(result)
            else:
                # Find existing result and merge scores
                for existing in unique_results:
                    if existing.search_result.node_id == node_id:
                        # Take the higher score and combine match types
                        if result.hybrid_score > existing.hybrid_score:
                            existing.hybrid_score = result.hybrid_score
                        existing.match_type = f"{existing.match_type}+{result.match_type}"
                        break
        
        # Apply hybrid scoring
        for result in unique_results:
            result.hybrid_score = self._calculate_hybrid_score(result, intent, config)
        
        return unique_results
    
    def _calculate_hybrid_score(
        self, 
        result: HybridSearchResult, 
        intent: QueryIntent, 
        config: HybridSearchConfig
    ) -> float:
        """Calculate hybrid score combining multiple factors."""
        base_score = result.hybrid_score
        
        # Boost exact matches
        if self._is_exact_match(result.search_result, intent):
            base_score *= config.boost_exact_matches
        
        # Boost based on query intent confidence
        base_score *= intent.confidence
        
        # Boost based on node type preferences
        if intent.node_types and result.search_result.node_type in intent.node_types:
            base_score *= 1.2
        
        # Boost based on match type diversity
        if "+" in result.match_type:  # Multiple match types
            base_score *= 1.1
        
        # Context relevance boost
        if result.context and len(result.context.related_nodes) > 0:
            context_boost = min(0.1, len(result.context.related_nodes) * 0.002)
            base_score += context_boost
        
        return min(base_score, 2.0)  # Cap at 2.0
    
    def _is_exact_match(self, search_result: SearchResult, intent: QueryIntent) -> bool:
        """Check if the result is an exact match for the query intent."""
        name_lower = search_result.name.lower()
        
        # Check entity name matches
        for entity in intent.entity_names:
            if entity.lower() == name_lower:
                return True
        
        # Check keyword matches
        for keyword in intent.keywords:
            if keyword in name_lower:
                return True
        
        return False
    
    async def explain_search(self, query: str) -> Dict[str, Any]:
        """Explain how a search query would be processed."""
        intent = self.query_parser.parse_query(query)
        
        explanation = {
            "original_query": query,
            "parsed_intent": {
                "query_type": intent.query_type.value,
                "confidence": intent.confidence,
                "semantic_terms": intent.semantic_terms,
                "entity_names": intent.entity_names,
                "node_types": intent.node_types,
                "programming_terms": intent.programming_terms,
                "expand_context": intent.expand_context
            },
            "search_strategy": self._get_search_strategy_explanation(intent),
            "estimated_approach": self._get_approach_explanation(intent)
        }
        
        return explanation
    
    def _get_search_strategy_explanation(self, intent: QueryIntent) -> List[str]:
        """Get explanation of search strategies that will be used."""
        strategies = []
        
        if intent.query_type in [QueryType.SEMANTIC, QueryType.HYBRID, QueryType.CONTEXTUAL]:
            strategies.append("Vector semantic search using embeddings")
        
        if intent.query_type in [QueryType.ENTITY, QueryType.HYBRID]:
            strategies.append("Direct entity name lookup")
        
        if intent.expand_context:
            strategies.append("Graph context expansion")
        
        return strategies
    
    def _get_approach_explanation(self, intent: QueryIntent) -> str:
        """Get high-level explanation of the search approach."""
        if intent.query_type == QueryType.SEMANTIC:
            return "Pure semantic search - finding code with similar meaning"
        elif intent.query_type == QueryType.ENTITY:
            return "Entity lookup - finding specific named code elements"
        elif intent.query_type == QueryType.HYBRID:
            return "Hybrid approach - combining semantic search with entity lookup"
        elif intent.query_type == QueryType.CONTEXTUAL:
            return "Contextual search - semantic search with relationship traversal"
        else:
            return "Default semantic search approach"

# Example usage
async def main():
    """Example usage of HybridSearchEngine."""
    search_engine = HybridSearchEngine(
        neo4j_uri="bolt://localhost:7687",
        neo4j_user="neo4j",
        neo4j_password="password"
    )
    
    try:
        # Example queries
        queries = [
            "PaymentService class that handles stripe payments",
            "authentication methods",
            "UserController login function",
            "database connection configuration",
            "error handling in api endpoints"
        ]
        
        for query in queries:
            print(f"\n=== Query: {query} ===")
            
            # Explain the search approach
            explanation = await search_engine.explain_search(query)
            print(f"Strategy: {explanation['search_strategy']}")
            print(f"Approach: {explanation['estimated_approach']}")
            
            # Perform the search
            config = HybridSearchConfig(
                max_total_results=5,
                enable_context_expansion=True,
                include_source_code=False
            )
            
            results = await search_engine.search(query, config)
            
            print(f"\nFound {len(results)} results:")
            for i, result in enumerate(results, 1):
                print(f"{i}. {result.search_result.name} ({result.search_result.node_type})")
                print(f"   Score: {result.hybrid_score:.3f} | Type: {result.match_type}")
                print(f"   {result.explanation}")
                if result.context:
                    print(f"   Context: {result.context.traversal_summary}")
                print()
        
    finally:
        search_engine.close()

if __name__ == "__main__":
    asyncio.run(main()) 