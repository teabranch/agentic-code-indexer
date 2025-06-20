import asyncio
import os
from pathlib import Path
from typing import Dict, List, Optional
import logging
from datetime import datetime
import typer
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn
from rich.table import Table
from rich.panel import Panel
import json

from .file_traversal import FileTraversal, FileStatus
from .chunker_orchestrator import ChunkerOrchestrator
from .graph_ingestion import GraphIngestion, IngestionStats
from .neo4j_setup import Neo4jSetup

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

console = Console()
app = typer.Typer(help="Agentic Code Indexer - Main Pipeline")

class MainPipeline:
    """
    Main orchestrator for the Agentic Code Indexing Pipeline.
    Coordinates file traversal, chunking, and graph ingestion.
    """
    
    def __init__(
        self,
        project_root: str,
        neo4j_uri: str = "bolt://localhost:7687",
        neo4j_user: str = "neo4j",
        neo4j_password: str = "password",
        max_concurrent_files: int = 5,
        batch_size: int = 1000
    ):
        self.project_root = Path(project_root).resolve()
        self.neo4j_uri = neo4j_uri
        self.neo4j_user = neo4j_user
        self.neo4j_password = neo4j_password
        self.max_concurrent_files = max_concurrent_files
        self.batch_size = batch_size
        
        # Initialize components
        self.file_traversal = FileTraversal(neo4j_uri, neo4j_user, neo4j_password)
        self.chunker_orchestrator = ChunkerOrchestrator(str(self.project_root))
        self.graph_ingestion = GraphIngestion(neo4j_uri, neo4j_user, neo4j_password, batch_size)
        
    async def initialize_database(self) -> bool:
        """Initialize Neo4j database with schema and indexes."""
        try:
            console.print("[yellow]Initializing Neo4j database...[/yellow]")
            
            neo4j_setup = Neo4jSetup(self.neo4j_uri, self.neo4j_user, self.neo4j_password)
            await neo4j_setup.setup_database()
            neo4j_setup.close()
            
            console.print("[green]✓ Database initialized successfully[/green]")
            return True
            
        except Exception as e:
            console.print(f"[red]✗ Database initialization failed: {e}[/red]")
            logger.error(f"Database initialization error: {e}")
            return False
    
    def validate_environment(self) -> bool:
        """Validate that all required components are available."""
        console.print("[yellow]Validating environment...[/yellow]")
        
        # Check project root exists
        if not self.project_root.exists():
            console.print(f"[red]✗ Project root does not exist: {self.project_root}[/red]")
            return False
        
        # Validate chunkers
        validation_results = self.chunker_orchestrator.validate_chunkers()
        
        table = Table(title="Chunker Validation")
        table.add_column("Language", style="cyan")
        table.add_column("Status", style="bold")
        
        all_valid = True
        for language, is_valid in validation_results.items():
            status = "[green]✓ Available[/green]" if is_valid else "[red]✗ Failed[/red]"
            table.add_row(language, status)
            if not is_valid:
                all_valid = False
        
        console.print(table)
        
        if not all_valid:
            console.print("[yellow]Warning: Some chunkers failed validation[/yellow]")
        
        return True  # Continue even if some chunkers fail
    
    async def scan_and_detect_changes(self, directory: str) -> List:
        """Scan directory and detect file changes."""
        console.print(f"[yellow]Scanning directory: {directory}[/yellow]")
        
        try:
            file_changes = await self.file_traversal.detect_file_changes(
                directory, str(self.project_root)
            )
            
            # Summarize changes
            change_summary = {}
            for status in FileStatus:
                count = sum(1 for fc in file_changes if fc.status == status)
                change_summary[status.value] = count
            
            table = Table(title="File Change Summary")
            table.add_column("Status", style="cyan")
            table.add_column("Count", style="bold")
            
            for status, count in change_summary.items():
                color = {
                    "new": "green",
                    "modified": "yellow", 
                    "deleted": "red",
                    "unchanged": "blue"
                }.get(status, "white")
                
                table.add_row(status.title(), f"[{color}]{count}[/{color}]")
            
            console.print(table)
            
            return file_changes
            
        except Exception as e:
            console.print(f"[red]Error scanning directory: {e}[/red]")
            logger.error(f"Directory scan error: {e}")
            return []
    
    async def process_files(self, file_changes: List) -> List:
        """Process files through chunkers."""
        files_to_process = self.file_traversal.get_files_to_process(file_changes)
        
        if not files_to_process:
            console.print("[blue]No files need processing[/blue]")
            return []
        
        console.print(f"[yellow]Processing {len(files_to_process)} files...[/yellow]")
        
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TimeElapsedColumn(),
            console=console
        ) as progress:
            
            task = progress.add_task("Processing files...", total=len(files_to_process))
            
            # Process files in batches
            chunker_outputs = await self.chunker_orchestrator.process_files_batch(
                files_to_process, self.max_concurrent_files
            )
            
            progress.update(task, completed=len(files_to_process))
        
        console.print(f"[green]✓ Processed {len(chunker_outputs)} files successfully[/green]")
        return chunker_outputs
    
    async def ingest_to_database(self, chunker_outputs: List) -> IngestionStats:
        """Ingest chunker outputs to Neo4j database."""
        if not chunker_outputs:
            console.print("[blue]No data to ingest[/blue]")
            return IngestionStats()
        
        console.print(f"[yellow]Ingesting data from {len(chunker_outputs)} files...[/yellow]")
        
        try:
            stats = await self.graph_ingestion.ingest_multiple_outputs(chunker_outputs)
            
            # Display ingestion results
            table = Table(title="Ingestion Results")
            table.add_column("Metric", style="cyan")
            table.add_column("Count", style="bold green")
            
            table.add_row("Nodes Created", str(stats.nodes_created))
            table.add_row("Relationships Created", str(stats.relationships_created))
            table.add_row("Files Processed", str(stats.files_processed))
            if stats.errors > 0:
                table.add_row("Errors", f"[red]{stats.errors}[/red]")
            
            console.print(table)
            
            return stats
            
        except Exception as e:
            console.print(f"[red]Error during ingestion: {e}[/red]")
            logger.error(f"Ingestion error: {e}")
            return IngestionStats(errors=1)
    
    async def cleanup_deleted_files(self, file_changes: List) -> int:
        """Clean up deleted files from database."""
        deleted_files = [fc for fc in file_changes if fc.status == FileStatus.DELETED]
        
        if not deleted_files:
            return 0
        
        console.print(f"[yellow]Cleaning up {len(deleted_files)} deleted files...[/yellow]")
        
        total_deleted = 0
        for file_change in deleted_files:
            deleted_count = await self.graph_ingestion.delete_file_subgraph(file_change.path)
            total_deleted += deleted_count
        
        console.print(f"[green]✓ Cleaned up {total_deleted} nodes from deleted files[/green]")
        return total_deleted
    
    def get_database_summary(self) -> Dict:
        """Get current database state summary."""
        return self.graph_ingestion.get_ingestion_summary()
    
    def display_summary(self, summary: Dict):
        """Display database summary in a nice format."""
        console.print("\n[bold cyan]Database Summary[/bold cyan]")
        
        # Node counts
        if "node_counts" in summary:
            node_table = Table(title="Node Counts by Type")
            node_table.add_column("Type", style="cyan")
            node_table.add_column("Count", style="bold")
            
            for node_type, count in summary["node_counts"].items():
                node_table.add_row(node_type, str(count))
            
            console.print(node_table)
        
        # Relationship counts
        if "relationship_counts" in summary:
            rel_table = Table(title="Relationship Counts by Type")
            rel_table.add_column("Type", style="cyan")
            rel_table.add_column("Count", style="bold")
            
            for rel_type, count in summary["relationship_counts"].items():
                rel_table.add_row(rel_type, str(count))
            
            console.print(rel_table)
        
        # File statistics
        if "files" in summary:
            files_info = summary["files"]
            file_panel = Panel(
                f"Files: {files_info.get('count', 0)}\n"
                f"Languages: {', '.join(files_info.get('languages', []))}\n"
                f"Total Size: {files_info.get('total_size', 0):,} bytes",
                title="File Statistics",
                border_style="green"
            )
            console.print(file_panel)
    
    async def run_full_pipeline(self, directory: str, init_db: bool = False) -> bool:
        """Run the complete indexing pipeline."""
        start_time = datetime.now()
        
        console.print(Panel(
            f"[bold cyan]Agentic Code Indexer[/bold cyan]\n"
            f"Project: {self.project_root}\n"
            f"Directory: {directory}\n"
            f"Started: {start_time.strftime('%Y-%m-%d %H:%M:%S')}",
            border_style="blue"
        ))
        
        try:
            # Step 1: Validate environment
            if not self.validate_environment():
                return False
            
            # Step 2: Initialize database if requested
            if init_db:
                if not await self.initialize_database():
                    return False
            
            # Step 3: Scan and detect changes
            file_changes = await self.scan_and_detect_changes(directory)
            if not file_changes:
                console.print("[yellow]No files found to process[/yellow]")
                return True
            
            # Step 4: Clean up deleted files
            await self.cleanup_deleted_files(file_changes)
            
            # Step 5: Process files through chunkers
            chunker_outputs = await self.process_files(file_changes)
            
            # Step 6: Ingest to database
            ingestion_stats = await self.ingest_to_database(chunker_outputs)
            
            # Step 7: Display final summary
            summary = self.get_database_summary()
            self.display_summary(summary)
            
            # Final status
            end_time = datetime.now()
            duration = end_time - start_time
            
            console.print(Panel(
                f"[bold green]Pipeline Completed Successfully[/bold green]\n"
                f"Duration: {duration}\n"
                f"Files Processed: {ingestion_stats.files_processed}\n"
                f"Nodes Created: {ingestion_stats.nodes_created}\n"
                f"Relationships Created: {ingestion_stats.relationships_created}",
                border_style="green"
            ))
            
            return True
            
        except Exception as e:
            console.print(f"[red]Pipeline failed: {e}[/red]")
            logger.error(f"Pipeline error: {e}")
            return False
        
        finally:
            # Cleanup connections
            self.file_traversal.close()
            self.graph_ingestion.close()

@app.command()
def run(
    directory: str = typer.Argument(..., help="Directory to process"),
    project_root: str = typer.Option(".", help="Project root directory"),
    neo4j_uri: str = typer.Option("bolt://localhost:7687", help="Neo4j URI"),
    neo4j_user: str = typer.Option("neo4j", help="Neo4j username"),
    neo4j_password: str = typer.Option("password", help="Neo4j password"),
    init_db: bool = typer.Option(False, "--init-db", help="Initialize database schema"),
    max_concurrent: int = typer.Option(5, help="Maximum concurrent file processing"),
    batch_size: int = typer.Option(1000, help="Database batch size")
):
    """Run the main indexing pipeline."""
    pipeline = MainPipeline(
        project_root=project_root,
        neo4j_uri=neo4j_uri,
        neo4j_user=neo4j_user,
        neo4j_password=neo4j_password,
        max_concurrent_files=max_concurrent,
        batch_size=batch_size
    )
    
    success = asyncio.run(pipeline.run_full_pipeline(directory, init_db))
    if not success:
        raise typer.Exit(1)

@app.command()
def status(
    neo4j_uri: str = typer.Option("bolt://localhost:7687", help="Neo4j URI"),
    neo4j_user: str = typer.Option("neo4j", help="Neo4j username"), 
    neo4j_password: str = typer.Option("password", help="Neo4j password")
):
    """Show current database status."""
    ingestion = GraphIngestion(neo4j_uri, neo4j_user, neo4j_password)
    
    try:
        summary = ingestion.get_ingestion_summary()
        
        # Create a simple pipeline instance for display method
        pipeline = MainPipeline(".")
        pipeline.display_summary(summary)
        
    finally:
        ingestion.close()

if __name__ == "__main__":
    app() 