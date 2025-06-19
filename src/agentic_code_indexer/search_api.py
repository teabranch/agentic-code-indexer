import asyncio
import os
from typing import List, Dict, Any, Optional
from datetime import datetime
import logging
from contextlib import asynccontextmanager

# FastAPI imports
from fastapi import FastAPI, HTTPException, Query, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import uvicorn

# Internal imports
from .hybrid_search import HybridSearchEngine, HybridSearchConfig, HybridSearchResult
from .vector_search import VectorSearchConfig
from .graph_traversal import TraversalDirection

logger = logging.getLogger(__name__)

# Pydantic models for API requests/responses
class SearchRequest(BaseModel):
    """Request model for search operations."""
    query: str = Field(..., description="Search query text")
    max_results: int = Field(20, ge=1, le=100, description="Maximum number of results")
    min_similarity: float = Field(0.6, ge=0.0, le=1.0, description="Minimum similarity threshold")
    node_types: Optional[List[str]] = Field(None, description="Specific node types to search")
    include_context: bool = Field(True, description="Include graph context expansion")
    include_source_code: bool = Field(False, description="Include raw source code in results")
    expand_call_hierarchy: bool = Field(False, description="Expand call hierarchy for methods")
    expand_inheritance: bool = Field(False, description="Expand inheritance hierarchy for classes")

class LocationInfo(BaseModel):
    """Location information for a code element."""
    start_line: Optional[int] = None
    end_line: Optional[int] = None

class SearchResultResponse(BaseModel):
    """Response model for search results."""
    node_id: str
    name: str
    full_name: str
    node_type: str
    summary: str
    similarity_score: float
    hybrid_score: float
    match_type: str
    explanation: str
    location: Optional[LocationInfo] = None
    metadata: Optional[Dict[str, Any]] = None
    raw_code: Optional[str] = None

class ContextNodeResponse(BaseModel):
    """Response model for context nodes."""
    node_id: str
    name: str
    full_name: str
    node_type: str
    summary: str
    depth: int
    relationship_path: Optional[List[str]] = None

class SearchContextResponse(BaseModel):
    """Response model for search context."""
    related_nodes: List[ContextNodeResponse]
    relationships: List[Dict[str, Any]]
    traversal_summary: Dict[str, Any]

class SearchResponse(BaseModel):
    """Complete search response."""
    query: str
    total_results: int
    search_time_ms: float
    results: List[SearchResultResponse]
    context: Optional[SearchContextResponse] = None
    query_explanation: Optional[Dict[str, Any]] = None

class StatsResponse(BaseModel):
    """Search engine statistics response."""
    total_nodes_by_type: Dict[str, int]
    nodes_with_embeddings: Dict[str, int]
    available_indexes: List[str]
    database_info: Dict[str, Any]

class HierarchyRequest(BaseModel):
    """Request for hierarchy information."""
    node_id: str = Field(..., description="ID of the node to analyze")
    direction: str = Field("both", description="Direction: 'incoming', 'outgoing', or 'both'")
    max_depth: int = Field(3, ge=1, le=10, description="Maximum traversal depth")

class HierarchyResponse(BaseModel):
    """Response for hierarchy queries."""
    node_id: str
    hierarchy_type: str  # "call" or "inheritance"
    callers: Optional[List[ContextNodeResponse]] = None
    callees: Optional[List[ContextNodeResponse]] = None
    ancestors: Optional[List[ContextNodeResponse]] = None
    descendants: Optional[List[ContextNodeResponse]] = None

# Global search engine instance
search_engine: Optional[HybridSearchEngine] = None

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan - setup and cleanup."""
    global search_engine
    
    # Startup
    neo4j_uri = os.getenv("NEO4J_URI", "bolt://localhost:7687")
    neo4j_user = os.getenv("NEO4J_USER", "neo4j") 
    neo4j_password = os.getenv("NEO4J_PASSWORD", "password")
    
    try:
        search_engine = HybridSearchEngine(neo4j_uri, neo4j_user, neo4j_password)
        logger.info("Search engine initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize search engine: {e}")
        raise
    
    yield
    
    # Shutdown
    if search_engine:
        search_engine.close()
        logger.info("Search engine closed")

# Create FastAPI app
app = FastAPI(
    title="Agentic Code Indexer Search API",
    description="Advanced code search with semantic similarity, entity lookup, and graph traversal",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def get_search_engine() -> HybridSearchEngine:
    """Dependency to get the search engine instance."""
    if search_engine is None:
        raise HTTPException(status_code=503, detail="Search engine not available")
    return search_engine

@app.post("/search", response_model=SearchResponse)
async def search_code(
    request: SearchRequest,
    engine: HybridSearchEngine = Depends(get_search_engine)
) -> SearchResponse:
    """
    Perform hybrid code search with semantic similarity and graph context.
    
    This endpoint combines:
    - Vector-based semantic search using embeddings
    - Direct entity name lookup
    - Graph relationship traversal for context
    - Hybrid scoring and ranking
    """
    start_time = datetime.now()
    
    try:
        # Create search configuration
        config = HybridSearchConfig(
            max_total_results=request.max_results,
            min_similarity_threshold=request.min_similarity,
            enable_context_expansion=request.include_context,
            include_source_code=request.include_source_code,
            expand_call_hierarchy=request.expand_call_hierarchy,
            expand_inheritance=request.expand_inheritance
        )
        
        # Perform search
        results = await engine.search(request.query, config)
        
        # Get query explanation
        explanation = await engine.explain_search(request.query)
        
        # Convert results to response format
        result_responses = []
        context_response = None
        
        for result in results:
            location = None
            if result.search_result.location:
                location = LocationInfo(**result.search_result.location)
            
            result_response = SearchResultResponse(
                node_id=result.search_result.node_id,
                name=result.search_result.name,
                full_name=result.search_result.full_name,
                node_type=result.search_result.node_type,
                summary=result.search_result.summary,
                similarity_score=result.search_result.similarity_score,
                hybrid_score=result.hybrid_score,
                match_type=result.match_type,
                explanation=result.explanation,
                location=location,
                metadata=result.search_result.metadata,
                raw_code=result.search_result.raw_code
            )
            result_responses.append(result_response)
            
            # Use context from first result (they share the same context)
            if result.context and context_response is None:
                context_nodes = [
                    ContextNodeResponse(
                        node_id=node.node_id,
                        name=node.name,
                        full_name=node.full_name,
                        node_type=node.node_type,
                        summary=node.summary,
                        depth=node.depth,
                        relationship_path=node.relationship_path
                    )
                    for node in result.context.related_nodes
                ]
                
                context_response = SearchContextResponse(
                    related_nodes=context_nodes,
                    relationships=result.context.relationships,
                    traversal_summary=result.context.traversal_summary
                )
        
        # Calculate search time
        end_time = datetime.now()
        search_time_ms = (end_time - start_time).total_seconds() * 1000
        
        return SearchResponse(
            query=request.query,
            total_results=len(result_responses),
            search_time_ms=search_time_ms,
            results=result_responses,
            context=context_response,
            query_explanation=explanation
        )
        
    except Exception as e:
        logger.error(f"Search error: {e}")
        raise HTTPException(status_code=500, detail=f"Search failed: {str(e)}")

@app.get("/search", response_model=SearchResponse)
async def search_code_get(
    q: str = Query(..., description="Search query"),
    max_results: int = Query(20, ge=1, le=100, description="Maximum results"),
    min_similarity: float = Query(0.6, ge=0.0, le=1.0, description="Minimum similarity"),
    node_types: Optional[str] = Query(None, description="Comma-separated node types"),
    include_context: bool = Query(True, description="Include context expansion"),
    engine: HybridSearchEngine = Depends(get_search_engine)
) -> SearchResponse:
    """
    GET endpoint for simple search queries.
    """
    # Parse node types
    parsed_node_types = None
    if node_types:
        parsed_node_types = [t.strip() for t in node_types.split(',')]
    
    # Create request object
    request = SearchRequest(
        query=q,
        max_results=max_results,
        min_similarity=min_similarity,
        node_types=parsed_node_types,
        include_context=include_context
    )
    
    return await search_code(request, engine)

@app.post("/hierarchy/call", response_model=HierarchyResponse)
async def get_call_hierarchy(
    request: HierarchyRequest,
    engine: HybridSearchEngine = Depends(get_search_engine)
) -> HierarchyResponse:
    """
    Get call hierarchy for a method or function.
    """
    try:
        direction = TraversalDirection.BOTH
        if request.direction.lower() == "incoming":
            direction = TraversalDirection.INCOMING
        elif request.direction.lower() == "outgoing":
            direction = TraversalDirection.OUTGOING
        
        hierarchy = await engine.graph_engine.get_call_hierarchy(
            request.node_id,
            direction=direction,
            max_depth=request.max_depth
        )
        
        callers = [
            ContextNodeResponse(
                node_id=node.node_id,
                name=node.name,
                full_name=node.full_name,
                node_type=node.node_type,
                summary=node.summary,
                depth=0
            )
            for node in hierarchy.get("callers", [])
        ]
        
        callees = [
            ContextNodeResponse(
                node_id=node.node_id,
                name=node.name,
                full_name=node.full_name,
                node_type=node.node_type,
                summary=node.summary,
                depth=0
            )
            for node in hierarchy.get("callees", [])
        ]
        
        return HierarchyResponse(
            node_id=request.node_id,
            hierarchy_type="call",
            callers=callers,
            callees=callees
        )
        
    except Exception as e:
        logger.error(f"Call hierarchy error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get call hierarchy: {str(e)}")

@app.post("/hierarchy/inheritance", response_model=HierarchyResponse)
async def get_inheritance_hierarchy(
    request: HierarchyRequest,
    engine: HybridSearchEngine = Depends(get_search_engine)
) -> HierarchyResponse:
    """
    Get inheritance hierarchy for a class or interface.
    """
    try:
        hierarchy = await engine.graph_engine.get_inheritance_hierarchy(request.node_id)
        
        ancestors = [
            ContextNodeResponse(
                node_id=node.node_id,
                name=node.name,
                full_name=node.full_name,
                node_type=node.node_type,
                summary=node.summary,
                depth=0
            )
            for node in hierarchy.get("ancestors", [])
        ]
        
        descendants = [
            ContextNodeResponse(
                node_id=node.node_id,
                name=node.name,
                full_name=node.full_name,
                node_type=node.node_type,
                summary=node.summary,
                depth=0
            )
            for node in hierarchy.get("descendants", [])
        ]
        
        return HierarchyResponse(
            node_id=request.node_id,
            hierarchy_type="inheritance", 
            ancestors=ancestors,
            descendants=descendants
        )
        
    except Exception as e:
        logger.error(f"Inheritance hierarchy error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get inheritance hierarchy: {str(e)}")

@app.get("/node/{node_id}")
async def get_node_details(
    node_id: str,
    engine: HybridSearchEngine = Depends(get_search_engine)
):
    """
    Get detailed information about a specific node.
    """
    try:
        result = await engine.vector_engine.get_node_details(node_id)
        
        if not result:
            raise HTTPException(status_code=404, detail="Node not found")
        
        location = None
        if result.location:
            location = LocationInfo(**result.location)
        
        return SearchResultResponse(
            node_id=result.node_id,
            name=result.name,
            full_name=result.full_name,
            node_type=result.node_type,
            summary=result.summary,
            similarity_score=result.similarity_score,
            hybrid_score=result.similarity_score,
            match_type="direct",
            explanation="Direct node lookup",
            location=location,
            metadata=result.metadata,
            raw_code=result.raw_code
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Node details error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get node details: {str(e)}")

@app.get("/stats", response_model=StatsResponse)
async def get_search_stats(
    engine: HybridSearchEngine = Depends(get_search_engine)
) -> StatsResponse:
    """
    Get search engine statistics and capabilities.
    """
    try:
        # Get vector search statistics
        vector_stats = engine.vector_engine.get_search_statistics()
        
        # Get total node counts
        total_nodes = {}
        nodes_with_embeddings = {}
        available_indexes = []
        
        for node_type, stats in vector_stats.items():
            nodes_with_embeddings[node_type] = stats["nodes_with_embeddings"]
            available_indexes.append(stats["index_name"])
        
        # Get database info
        with engine.driver.session() as session:
            # Total nodes by type
            node_count_query = """
            MATCH (n)
            RETURN labels(n)[0] as node_type, count(n) as count
            ORDER BY count DESC
            """
            result = session.run(node_count_query)
            for record in result:
                if record["node_type"]:
                    total_nodes[record["node_type"]] = record["count"]
            
            # Database version and info
            db_info_query = "CALL dbms.components() YIELD name, versions RETURN name, versions"
            db_result = session.run(db_info_query)
            db_info = {}
            for record in db_result:
                db_info[record["name"]] = record["versions"]
        
        return StatsResponse(
            total_nodes_by_type=total_nodes,
            nodes_with_embeddings=nodes_with_embeddings,
            available_indexes=available_indexes,
            database_info=db_info
        )
        
    except Exception as e:
        logger.error(f"Stats error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get statistics: {str(e)}")

@app.get("/explain")
async def explain_query(
    q: str = Query(..., description="Query to explain"),
    engine: HybridSearchEngine = Depends(get_search_engine)
):
    """
    Explain how a search query would be processed.
    """
    try:
        explanation = await engine.explain_search(q)
        return explanation
    except Exception as e:
        logger.error(f"Explain error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to explain query: {str(e)}")

@app.get("/health")
async def health_check():
    """
    Health check endpoint.
    """
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}

@app.get("/")
async def root():
    """
    Root endpoint with API information.
    """
    return {
        "name": "Agentic Code Indexer Search API",
        "version": "1.0.0",
        "description": "Advanced code search with semantic similarity and graph traversal",
        "endpoints": {
            "search": "/search (GET/POST) - Hybrid code search",
            "call_hierarchy": "/hierarchy/call (POST) - Get method call hierarchy", 
            "inheritance_hierarchy": "/hierarchy/inheritance (POST) - Get class inheritance hierarchy",
            "node_details": "/node/{node_id} (GET) - Get node details",
            "stats": "/stats (GET) - Search engine statistics",
            "explain": "/explain (GET) - Explain query processing",
            "health": "/health (GET) - Health check"
        },
        "documentation": "/docs"
    }

def run_api(
    host: str = "0.0.0.0",
    port: int = 8000,
    reload: bool = False,
    log_level: str = "info"
):
    """
    Run the search API server.
    """
    uvicorn.run(
        "agentic_code_indexer.search_api:app",
        host=host,
        port=port,
        reload=reload,
        log_level=log_level
    )

if __name__ == "__main__":
    run_api(reload=True) 