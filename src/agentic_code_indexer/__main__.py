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