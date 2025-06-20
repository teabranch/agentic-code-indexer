import asyncio
import subprocess
import json
import tempfile
import os
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
import logging
from .file_traversal import FileChange
from .common_data_format import ChunkerOutput

logger = logging.getLogger(__name__)

@dataclass
class ChunkerConfig:
    """Configuration for a language-specific chunker."""
    language: str
    executable_path: str
    working_directory: str
    timeout: int = 300  # 5 minutes default timeout

class ChunkerOrchestrator:
    """
    Orchestrates all language-specific chunkers to process source files
    and extract structured data in the common JSON format.
    """
    
    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self.chunkers: Dict[str, ChunkerConfig] = {}
        self._setup_chunkers()
    
    def _setup_chunkers(self):
        """Initialize configurations for all available chunkers."""
        # Python chunker
        python_chunker_path = self.project_root / "src" / "python-chunker" / "main.py"
        if python_chunker_path.exists():
            self.chunkers["python"] = ChunkerConfig(
                language="python",
                executable_path=str(python_chunker_path),
                working_directory=str(python_chunker_path.parent),
                timeout=300
            )
            logger.info("Python chunker configured")
        
        # C# chunker
        csharp_chunker_path = self.project_root / "src" / "csharp-chunker" / "CSharpChunker"
        if csharp_chunker_path.exists():
            self.chunkers["csharp"] = ChunkerConfig(
                language="csharp",
                executable_path="dotnet run --",
                working_directory=str(csharp_chunker_path),
                timeout=300
            )
            logger.info("C# chunker configured")
        
        # Node.js chunker  
        nodejs_chunker_path = self.project_root / "src" / "nodejs-chunker" / "src" / "main.ts"
        if nodejs_chunker_path.exists():
            # Check if compiled JS exists, otherwise use ts-node
            compiled_js = self.project_root / "src" / "nodejs-chunker" / "dist" / "main.js"
            if compiled_js.exists():
                executable = f"node {compiled_js}"
            else:
                executable = f"npx ts-node {nodejs_chunker_path}"
                
            self.chunkers["javascript"] = ChunkerConfig(
                language="javascript",
                executable_path=executable,
                working_directory=str(nodejs_chunker_path.parent.parent),
                timeout=300
            )
            self.chunkers["typescript"] = self.chunkers["javascript"]  # Same chunker handles both
            logger.info("Node.js/TypeScript chunker configured")
    
    def get_chunker_for_file(self, file_path: str) -> Optional[ChunkerConfig]:
        """Get the appropriate chunker for a file based on its extension."""
        path = Path(file_path)
        extension = path.suffix.lower()
        
        # Map extensions to chunker languages
        extension_map = {
            '.py': 'python',
            '.cs': 'csharp',
            '.js': 'javascript',
            '.jsx': 'javascript', 
            '.mjs': 'javascript',
            '.cjs': 'javascript',
            '.ts': 'typescript',
            '.tsx': 'typescript'
        }
        
        language = extension_map.get(extension)
        if language and language in self.chunkers:
            return self.chunkers[language]
        
        logger.warning(f"No chunker available for file: {file_path}")
        return None
    
    async def process_file(self, file_change: FileChange) -> Optional[ChunkerOutput]:
        """
        Process a single file using the appropriate chunker.
        Returns ChunkerOutput or None if processing fails.
        """
        chunker_config = self.get_chunker_for_file(file_change.absolute_path)
        if not chunker_config:
            return None
        
        # Create temporary output file
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as temp_file:
            temp_output_path = temp_file.name
        
        try:
            # Build command based on chunker type
            if chunker_config.language == "python":
                cmd = [
                    "python", chunker_config.executable_path,
                    file_change.absolute_path,
                    "--output", temp_output_path,
                    "--project-root", str(self.project_root)
                ]
            elif chunker_config.language == "csharp":
                cmd = chunker_config.executable_path.split() + [
                    file_change.absolute_path,
                    "-o", temp_output_path,
                    "--project-root", str(self.project_root)
                ]
            else:  # javascript/typescript
                cmd = chunker_config.executable_path.split() + [
                    file_change.absolute_path,
                    "--output", temp_output_path,
                    "--project-root", str(self.project_root)
                ]
            
            logger.debug(f"Running chunker command: {' '.join(cmd)}")
            
            # Execute chunker
            process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=chunker_config.working_directory,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(), 
                    timeout=chunker_config.timeout
                )
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                logger.error(f"Chunker timeout for file: {file_change.path}")
                return None
            
            if process.returncode != 0:
                logger.error(f"Chunker failed for {file_change.path}: {stderr.decode()}")
                return None
            
            # Read and parse output
            if os.path.exists(temp_output_path):
                with open(temp_output_path, 'r', encoding='utf-8') as f:
                    output_data = json.load(f)
                
                # Convert to ChunkerOutput object
                chunker_output = ChunkerOutput.parse_obj(output_data)
                logger.info(f"Successfully processed {file_change.path}: {len(chunker_output.nodes)} nodes, {len(chunker_output.relationships)} relationships")
                return chunker_output
            else:
                logger.error(f"No output file generated for: {file_change.path}")
                return None
                
        except Exception as e:
            logger.error(f"Error processing file {file_change.path}: {e}")
            return None
        finally:
            # Clean up temp file
            if os.path.exists(temp_output_path):
                os.unlink(temp_output_path)
    
    async def process_files_batch(self, file_changes: List[FileChange], max_concurrent: int = 5) -> List[ChunkerOutput]:
        """
        Process multiple files concurrently with limited parallelism.
        Returns list of ChunkerOutput objects for successful processing.
        """
        semaphore = asyncio.Semaphore(max_concurrent)
        
        async def process_with_semaphore(file_change: FileChange) -> Optional[ChunkerOutput]:
            async with semaphore:
                return await self.process_file(file_change)
        
        logger.info(f"Processing {len(file_changes)} files with max {max_concurrent} concurrent workers")
        
        # Create tasks for all files
        tasks = [process_with_semaphore(fc) for fc in file_changes]
        
        # Wait for all tasks to complete
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Filter successful results
        successful_outputs = []
        failed_count = 0
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Exception processing {file_changes[i].path}: {result}")
                failed_count += 1
            elif result is not None:
                successful_outputs.append(result)
            else:
                failed_count += 1
        
        logger.info(f"Batch processing complete: {len(successful_outputs)} successful, {failed_count} failed")
        return successful_outputs
    
    def get_available_chunkers(self) -> List[str]:
        """Get list of available chunker languages."""
        return list(self.chunkers.keys())
    
    def validate_chunkers(self) -> Dict[str, bool]:
        """
        Validate that all configured chunkers are working properly.
        Returns dict mapping language to validation status.
        """
        validation_results = {}
        
        for language, config in self.chunkers.items():
            try:
                # Test with a simple command that should work
                if language == "python":
                    cmd = ["python", "--version"]
                elif language == "csharp":
                    cmd = ["dotnet", "--version"]
                else:  # javascript/typescript
                    cmd = ["node", "--version"]
                
                result = subprocess.run(
                    cmd, 
                    cwd=config.working_directory,
                    capture_output=True, 
                    timeout=10
                )
                validation_results[language] = result.returncode == 0
                
                if result.returncode == 0:
                    logger.info(f"{language} chunker validation passed")
                else:
                    logger.error(f"{language} chunker validation failed")
                    
            except Exception as e:
                logger.error(f"Error validating {language} chunker: {e}")
                validation_results[language] = False
        
        return validation_results

# Example usage
async def main():
    """Example usage of ChunkerOrchestrator."""
    orchestrator = ChunkerOrchestrator(".")
    
    # Validate chunkers
    validation = orchestrator.validate_chunkers()
    print("Chunker validation results:", validation)
    
    # Show available chunkers
    available = orchestrator.get_available_chunkers()
    print("Available chunkers:", available)

if __name__ == "__main__":
    asyncio.run(main()) 