#!/usr/bin/env python3
"""
Agentic Code Indexer - Main CLI Entry Point
Provides comprehensive code analysis and indexing capabilities.
"""

import asyncio
import os
from pathlib import Path
import typer
from rich.console import Console
from rich.panel import Panel
import logging

from .main_pipeline import MainPipeline
from .llm_integration import LLMEmbeddingIntegration
from .summarization_orchestrator import HierarchicalSummarizationOrchestrator
from .hybrid_search import HybridSearchEngine, HybridSearchConfig
from .search_api import run_api

console = Console()
app = typer.Typer(
    name="agentic-code-indexer",
    help="🤖 Agentic Code Indexer - Intelligent code analysis and graph-based indexing system",
    rich_markup_mode="rich"
)

@app.command("index")
def index_command(
    directory: str = typer.Argument(..., help="Directory to index"),
    project_root: str = typer.Option(".", "--root", help="Project root directory"),
    neo4j_uri: str = typer.Option("bolt://localhost:7687", "--neo4j-uri", help="Neo4j database URI"),
    neo4j_user: str = typer.Option("neo4j", "--neo4j-user", help="Neo4j username"),
    neo4j_password: str = typer.Option("password", "--neo4j-password", help="Neo4j password"),
    init_db: bool = typer.Option(False, "--init-db", help="Initialize database schema"),
    max_concurrent: int = typer.Option(5, "--max-concurrent", help="Maximum concurrent file processing"),
    batch_size: int = typer.Option(1000, "--batch-size", help="Database batch size"),
    skip_llm: bool = typer.Option(False, "--skip-llm", help="Skip LLM summarization and embedding"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose logging")
):
    """
    🚀 Run the complete code indexing pipeline.
    
    This command performs:
    1. File traversal and change detection
    2. Code chunking and analysis  
    3. Graph database ingestion
    4. LLM-powered summarization (optional)
    5. Embedding generation (optional)
    """
    
    # Setup logging
    log_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=log_level, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    async def run_pipeline():
        console.print(Panel.fit(
            "[bold blue]🤖 Agentic Code Indexer[/bold blue]\n"
            "Intelligent code analysis and graph-based indexing",
            border_style="blue"
        ))
        
        # Initialize main pipeline
        pipeline = MainPipeline(
            project_root=project_root,
            neo4j_uri=neo4j_uri,
            neo4j_user=neo4j_user,
            neo4j_password=neo4j_password,
            max_concurrent_files=max_concurrent,
            batch_size=batch_size
        )
        
        try:
            # Run core indexing pipeline
            success = await pipeline.run_full_pipeline(directory, init_db)
            
            if not success:
                console.print("[red]❌ Core indexing pipeline failed[/red]")
                raise typer.Exit(1)
            
            # Run LLM enrichment if not skipped
            if not skip_llm:
                console.print("\n[yellow]🧠 Starting LLM enrichment process...[/yellow]")
                
                # Check for required environment variables
                if not os.getenv("ANTHROPIC_API_KEY"):
                    console.print("[yellow]⚠️ ANTHROPIC_API_KEY not set, skipping LLM features[/yellow]")
                else:
                    await run_llm_enrichment(neo4j_uri, neo4j_user, neo4j_password)
            
            console.print("\n[bold green]✅ Indexing pipeline completed successfully![/bold green]")
            
        except Exception as e:
            console.print(f"[red]❌ Pipeline failed: {e}[/red]")
            raise typer.Exit(1)
        finally:
            pipeline.file_traversal.close()
            pipeline.graph_ingestion.close()
    
    asyncio.run(run_pipeline())

@app.command("summarize")
def summarize_command(
    neo4j_uri: str = typer.Option("bolt://localhost:7687", "--neo4j-uri", help="Neo4j database URI"),
    neo4j_user: str = typer.Option("neo4j", "--neo4j-user", help="Neo4j username"),
    neo4j_password: str = typer.Option("password", "--neo4j-password", help="Neo4j password"),
    batch_size: int = typer.Option(20, "--batch-size", help="Batch size for processing"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Enable verbose logging")
):
    """
    🧠 Generate hierarchical summaries using LLM.
    
    Processes code elements in bottom-up order:
    Parameters → Variables → Methods → Classes → Files
    """
    
    log_level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=log_level, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    
    async def run_summarization():
        console.print(Panel.fit(
            "[bold yellow]🧠 Hierarchical Code Summarization[/bold yellow]\n"
            "Generating intelligent summaries using LLM",
            border_style="yellow"
        ))
        
        # Check API key
        if not os.getenv("ANTHROPIC_API_KEY"):
            console.print("[red]❌ ANTHROPIC_API_KEY environment variable not set[/red]")
            raise typer.Exit(1)
        
        await run_llm_enrichment(neo4j_uri, neo4j_user, neo4j_password, batch_size)
    
    asyncio.run(run_summarization())

@app.command("status")
def status_command(
    neo4j_uri: str = typer.Option("bolt://localhost:7687", "--neo4j-uri", help="Neo4j database URI"),
    neo4j_user: str = typer.Option("neo4j", "--neo4j-user", help="Neo4j username"),
    neo4j_password: str = typer.Option("password", "--neo4j-password", help="Neo4j password")
):
    """
    📊 Show current database status and statistics.
    """
    
    from .graph_ingestion import GraphIngestion
    
    console.print(Panel.fit(
        "[bold cyan]📊 Database Status[/bold cyan]\n"
        "Current indexing statistics",
        border_style="cyan"
    ))
    
    ingestion = GraphIngestion(neo4j_uri, neo4j_user, neo4j_password)
    
    try:
        summary = ingestion.get_ingestion_summary()
        
        # Create a temporary pipeline for display
        temp_pipeline = MainPipeline(".")
        temp_pipeline.display_summary(summary)
        
    except Exception as e:
        console.print(f"[red]❌ Failed to get status: {e}[/red]")
        raise typer.Exit(1)
    finally:
        ingestion.close()

@app.command("reset")
def reset_command(
    neo4j_uri: str = typer.Option("bolt://localhost:7687", "--neo4j-uri", help="Neo4j database URI"),
    neo4j_user: str = typer.Option("neo4j", "--neo4j-user", help="Neo4j username"),
    neo4j_password: str = typer.Option("password", "--neo4j-password", help="Neo4j password"),
    confirm: bool = typer.Option(False, "--confirm", help="Confirm database reset")
):
    """
    🔄 Reset processing status markers.
    
    Useful for recovering from interrupted processing.
    """
    
    if not confirm:
        console.print("[yellow]⚠️ This will reset all processing status markers[/yellow]")
        if not typer.confirm("Are you sure you want to continue?"):
            raise typer.Abort()
    
    from .summarization_orchestrator import HierarchicalSummarizationOrchestrator
    
    orchestrator = HierarchicalSummarizationOrchestrator(neo4j_uri, neo4j_user, neo4j_password)
    
    try:
        orchestrator.reset_processing_status()
        console.print("[green]✅ Processing status reset successfully[/green]")
    except Exception as e:
        console.print(f"[red]❌ Failed to reset status: {e}[/red]")
        raise typer.Exit(1)
    finally:
        orchestrator.close()

@app.command("search")
def search_command(
    query: str = typer.Argument(..., help="Search query"),
    neo4j_uri: str = typer.Option("bolt://localhost:7687", "--neo4j-uri", help="Neo4j database URI"),
    neo4j_user: str = typer.Option("neo4j", "--neo4j-user", help="Neo4j username"),
    neo4j_password: str = typer.Option("password", "--neo4j-password", help="Neo4j password"),
    max_results: int = typer.Option(10, "--max-results", "-n", help="Maximum number of results"),
    include_context: bool = typer.Option(True, "--context/--no-context", help="Include graph context"),
    include_code: bool = typer.Option(False, "--code/--no-code", help="Include source code"),
    node_types: str = typer.Option(None, "--types", help="Comma-separated node types (Class,Method,Function)"),
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed results")
):
    """
    🔍 Search the indexed codebase using natural language.
    
    Performs hybrid search combining:
    • Semantic similarity using embeddings
    • Direct entity name matching
    • Graph context expansion
    
    Examples:
      search "authentication methods"
      search "PaymentService class" --types Class
      search "error handling" --context --code
    """
    
    async def run_search():
        from rich.table import Table
        from rich.text import Text
        
        console.print(Panel.fit(
            f"[bold magenta]🔍 Searching: {query}[/bold magenta]\n"
            "Hybrid semantic + entity search",
            border_style="magenta"
        ))
        
        # Initialize search engine
        search_engine = HybridSearchEngine(neo4j_uri, neo4j_user, neo4j_password)
        
        try:
            # Parse node types
            parsed_node_types = None
            if node_types:
                parsed_node_types = [t.strip() for t in node_types.split(',')]
            
            # Configure search
            config = HybridSearchConfig(
                max_total_results=max_results,
                enable_context_expansion=include_context,
                include_source_code=include_code
            )
            
            # Perform search
            results = await search_engine.search(query, config)
            
            if not results:
                console.print("[yellow]No results found[/yellow]")
                return
            
            # Display results
            table = Table(title=f"Search Results ({len(results)} found)")
            table.add_column("Rank", justify="right", style="cyan", no_wrap=True)
            table.add_column("Name", style="bold")
            table.add_column("Type", style="green")
            table.add_column("Score", justify="right", style="yellow")
            table.add_column("Match", style="blue")
            if verbose:
                table.add_column("Summary", style="dim", max_width=50)
            
            for i, result in enumerate(results, 1):
                name_text = result.search_result.name
                if result.search_result.full_name != result.search_result.name:
                    name_text = f"{result.search_result.name}\n[dim]{result.search_result.full_name}[/dim]"
                
                score_text = f"{result.hybrid_score:.3f}"
                if result.search_result.similarity_score != result.hybrid_score:
                    score_text += f"\n[dim]({result.search_result.similarity_score:.3f})[/dim]"
                
                row = [
                    str(i),
                    name_text,
                    result.search_result.node_type,
                    score_text,
                    result.match_type
                ]
                
                if verbose:
                    summary = result.search_result.summary[:100] + "..." if len(result.search_result.summary) > 100 else result.search_result.summary
                    row.append(summary)
                
                table.add_row(*row)
            
            console.print(table)
            
            # Show context information if available
            if include_context and results and results[0].context:
                context = results[0].context
                console.print(f"\n[bold]Context Information:[/bold]")
                console.print(f"  Related nodes: {len(context.related_nodes)}")
                console.print(f"  Relationships: {len(context.relationships)}")
                
                if context.traversal_summary:
                    console.print("  Node types found:")
                    for node_type, count in context.traversal_summary.get('node_types', {}).items():
                        console.print(f"    {node_type}: {count}")
            
            # Show source code if requested
            if include_code and verbose:
                for i, result in enumerate(results[:3], 1):  # Show code for top 3 results
                    if result.search_result.raw_code:
                        console.print(f"\n[bold]Code for Result {i}:[/bold]")
                        console.print(Panel(
                            result.search_result.raw_code,
                            title=result.search_result.name,
                            border_style="dim"
                        ))
                        
        except Exception as e:
            console.print(f"[red]❌ Search failed: {e}[/red]")
            raise typer.Exit(1)
        finally:
            search_engine.close()
    
    asyncio.run(run_search())

@app.command("explain")
def explain_command(
    query: str = typer.Argument(..., help="Query to explain"),
    neo4j_uri: str = typer.Option("bolt://localhost:7687", "--neo4j-uri", help="Neo4j database URI"),
    neo4j_user: str = typer.Option("neo4j", "--neo4j-user", help="Neo4j username"),
    neo4j_password: str = typer.Option("password", "--neo4j-password", help="Neo4j password")
):
    """
    💡 Explain how a search query would be processed.
    
    Shows the query parsing, search strategy, and approach
    that would be used for a given search query.
    """
    
    async def run_explain():
        console.print(Panel.fit(
            f"[bold blue]💡 Query Analysis: {query}[/bold blue]\n"
            "Understanding search strategy",
            border_style="blue"
        ))
        
        search_engine = HybridSearchEngine(neo4j_uri, neo4j_user, neo4j_password)
        
        try:
            explanation = await search_engine.explain_search(query)
            
            from rich.tree import Tree
            
            tree = Tree(f"[bold]Query: {query}[/bold]")
            
            # Add parsed intent
            intent_branch = tree.add("[yellow]Parsed Intent[/yellow]")
            parsed = explanation['parsed_intent']
            intent_branch.add(f"Query Type: [green]{parsed['query_type']}[/green]")
            intent_branch.add(f"Confidence: [blue]{parsed['confidence']:.2f}[/blue]")
            
            if parsed['entity_names']:
                entities = intent_branch.add("Entity Names:")
                for entity in parsed['entity_names']:
                    entities.add(f"• {entity}")
            
            if parsed['semantic_terms']:
                terms = intent_branch.add("Semantic Terms:")
                for term in parsed['semantic_terms']:
                    terms.add(f"• {term}")
            
            if parsed['node_types']:
                types = intent_branch.add("Node Types:")
                for node_type in parsed['node_types']:
                    types.add(f"• {node_type}")
            
            # Add search strategy
            strategy_branch = tree.add("[cyan]Search Strategy[/cyan]")
            for strategy in explanation['search_strategy']:
                strategy_branch.add(f"• {strategy}")
            
            # Add approach
            approach_branch = tree.add("[magenta]Approach[/magenta]")
            approach_branch.add(explanation['estimated_approach'])
            
            console.print(tree)
            
        except Exception as e:
            console.print(f"[red]❌ Explain failed: {e}[/red]")
            raise typer.Exit(1)
        finally:
            search_engine.close()
    
    asyncio.run(run_explain())

@app.command("api")
def api_command(
    host: str = typer.Option("0.0.0.0", "--host", help="Host to bind to"),
    port: int = typer.Option(8000, "--port", help="Port to bind to"),
    reload: bool = typer.Option(False, "--reload", help="Enable auto-reload for development"),
    log_level: str = typer.Option("info", "--log-level", help="Log level")
):
    """
    🌐 Start the search API server.
    
    Provides REST API endpoints for:
    • Hybrid code search
    • Call hierarchy analysis  
    • Inheritance hierarchy analysis
    • Node details lookup
    • Search statistics
    
    The API will be available at http://localhost:8000
    Documentation at http://localhost:8000/docs
    """
    
    console.print(Panel.fit(
        f"[bold green]🌐 Starting Search API Server[/bold green]\n"
        f"Host: {host}\n"
        f"Port: {port}\n"
        f"Docs: http://{host}:{port}/docs",
        border_style="green"
    ))
    
    # Set environment variables if not already set
    if not os.getenv("NEO4J_URI"):
        os.environ["NEO4J_URI"] = "bolt://localhost:7687"
    if not os.getenv("NEO4J_USER"):
        os.environ["NEO4J_USER"] = "neo4j"
    if not os.getenv("NEO4J_PASSWORD"):
        os.environ["NEO4J_PASSWORD"] = "password"
    
    run_api(host=host, port=port, reload=reload, log_level=log_level)

async def run_llm_enrichment(neo4j_uri: str, neo4j_user: str, neo4j_password: str, batch_size: int = 20):
    """Run the complete LLM enrichment process."""
    
    # Initialize components
    llm_integration = LLMEmbeddingIntegration(neo4j_uri, neo4j_user, neo4j_password)
    summarization_orchestrator = HierarchicalSummarizationOrchestrator(neo4j_uri, neo4j_user, neo4j_password)
    
    try:
        # Step 1: Hierarchical summarization
        console.print("[yellow]🔄 Running hierarchical summarization...[/yellow]")
        summary_stats = await summarization_orchestrator.run_hierarchical_summarization(
            llm_integration, batch_size
        )
        
        console.print("[green]✅ Summarization complete[/green]")
        for level, count in summary_stats.items():
            if count > 0:
                console.print(f"  {level}: {count} nodes")
        
        # Step 2: Embedding generation
        console.print("\n[yellow]🔄 Generating embeddings...[/yellow]")
        embedding_stats = await llm_integration.run_full_enrichment()
        
        console.print("[green]✅ Embedding generation complete[/green]")
        console.print(f"  Summaries: {embedding_stats['summaries_generated']}")
        console.print(f"  Embeddings: {embedding_stats['embeddings_generated']}")
        
    except Exception as e:
        console.print(f"[red]❌ LLM enrichment failed: {e}[/red]")
        raise
    finally:
        llm_integration.close()
        summarization_orchestrator.close()

@app.callback()
def main(
    ctx: typer.Context,
    version: bool = typer.Option(False, "--version", help="Show version information")
):
    """
    🤖 Agentic Code Indexer
    
    Intelligent code analysis and graph-based indexing system that creates
    a comprehensive, searchable representation of your codebase.
    
    Features:
    • Multi-language support (Python, C#, JavaScript/TypeScript)  
    • Graph-based code representation in Neo4j
    • LLM-powered code summarization
    • Semantic code search with embeddings
    • Incremental processing and change detection
    """
    
    if version:
        console.print("Agentic Code Indexer v1.0.0")
        raise typer.Exit()

if __name__ == "__main__":
    app() 