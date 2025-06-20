import os
import hashlib
import asyncio
from pathlib import Path
from typing import List, Dict, Set, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import aiofiles
from neo4j import GraphDatabase
import logging

logger = logging.getLogger(__name__)

class FileStatus(Enum):
    NEW = "new"
    MODIFIED = "modified"
    UNCHANGED = "unchanged"
    DELETED = "deleted"

@dataclass
class FileChange:
    path: str
    absolute_path: str
    status: FileStatus
    old_checksum: Optional[str] = None
    new_checksum: Optional[str] = None
    size: int = 0
    extension: str = ""

class FileTraversal:
    """Handles recursive directory traversal and file change detection."""
    
    SUPPORTED_EXTENSIONS = {
        '.py': 'python',
        '.cs': 'csharp', 
        '.js': 'javascript',
        '.ts': 'typescript',
        '.jsx': 'javascript',
        '.tsx': 'typescript',
        '.mjs': 'javascript',
        '.cjs': 'javascript'
    }
    
    IGNORE_PATTERNS = {
        '__pycache__', '.git', '.svn', '.hg', 'node_modules', 'bin', 'obj',
        '.vs', '.vscode', 'build', 'dist', 'target', '.idea', '.pytest_cache'
    }
    
    def __init__(self, neo4j_uri: str, neo4j_user: str, neo4j_password: str):
        self.driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
        
    def close(self):
        if self.driver:
            self.driver.close()
            
    async def calculate_file_checksum(self, file_path: str) -> str:
        """Calculate SHA-256 checksum of a file."""
        hash_sha256 = hashlib.sha256()
        try:
            async with aiofiles.open(file_path, 'rb') as f:
                while chunk := await f.read(8192):
                    hash_sha256.update(chunk)
            return hash_sha256.hexdigest()
        except Exception as e:
            logger.error(f"Error calculating checksum for {file_path}: {e}")
            return ""
    
    def should_ignore_path(self, path: Path) -> bool:
        """Check if a path should be ignored."""
        for part in path.parts:
            if part in self.IGNORE_PATTERNS:
                return True
        return path.name.startswith('.') and path.name not in {'.gitignore', '.env'}
    
    def is_supported_file(self, file_path: Path) -> bool:
        """Check if a file is supported."""
        return file_path.suffix.lower() in self.SUPPORTED_EXTENSIONS
    
    async def scan_directory(self, directory_path: str) -> List[Path]:
        """Recursively scan directory for supported files."""
        directory = Path(directory_path)
        if not directory.exists():
            raise FileNotFoundError(f"Directory does not exist: {directory_path}")
            
        supported_files = []
        
        def _scan_recursive(current_path: Path):
            try:
                if self.should_ignore_path(current_path):
                    return
                    
                if current_path.is_file():
                    if self.is_supported_file(current_path):
                        supported_files.append(current_path)
                elif current_path.is_dir():
                    for child in current_path.iterdir():
                        _scan_recursive(child)
            except (PermissionError, OSError) as e:
                logger.warning(f"Cannot access {current_path}: {e}")
        
        _scan_recursive(directory)
        logger.info(f"Found {len(supported_files)} supported files")
        return supported_files
    
    def get_stored_checksums(self) -> Dict[str, str]:
        """Get stored file checksums from Neo4j."""
        checksums = {}
        with self.driver.session() as session:
            try:
                result = session.run("MATCH (f:File) RETURN f.path as path, f.checksum as checksum")
                for record in result:
                    if record["path"] and record["checksum"]:
                        checksums[record["path"]] = record["checksum"]
            except Exception as e:
                logger.error(f"Error retrieving checksums: {e}")
        return checksums
    
    async def detect_file_changes(self, directory_path: str, project_root: str) -> List[FileChange]:
        """Detect file changes by comparing with stored checksums."""
        project_root_path = Path(project_root)
        current_files = await self.scan_directory(directory_path)
        stored_checksums = self.get_stored_checksums()
        
        file_changes = []
        current_paths = set()
        
        # Process current files
        for file_path in current_files:
            try:
                relative_path = str(file_path.relative_to(project_root_path))
                current_paths.add(relative_path)
                
                file_stat = file_path.stat()
                new_checksum = await self.calculate_file_checksum(str(file_path))
                
                if relative_path not in stored_checksums:
                    status = FileStatus.NEW
                    old_checksum = None
                elif stored_checksums[relative_path] != new_checksum:
                    status = FileStatus.MODIFIED
                    old_checksum = stored_checksums[relative_path]
                else:
                    status = FileStatus.UNCHANGED
                    old_checksum = stored_checksums[relative_path]
                
                file_changes.append(FileChange(
                    path=relative_path,
                    absolute_path=str(file_path),
                    status=status,
                    old_checksum=old_checksum,
                    new_checksum=new_checksum,
                    size=file_stat.st_size,
                    extension=file_path.suffix
                ))
                
            except Exception as e:
                logger.error(f"Error processing {file_path}: {e}")
        
        # Find deleted files
        for stored_path in stored_checksums.keys():
            if stored_path not in current_paths:
                file_changes.append(FileChange(
                    path=stored_path,
                    absolute_path="",
                    status=FileStatus.DELETED,
                    old_checksum=stored_checksums[stored_path]
                ))
        
        return file_changes
    
    def get_files_to_process(self, file_changes: List[FileChange]) -> List[FileChange]:
        """Get files that need processing (new or modified)."""
        return [fc for fc in file_changes if fc.status in {FileStatus.NEW, FileStatus.MODIFIED}]

# Example usage and testing
async def main():
    """Example usage of FileTraversal system."""
    traversal = FileTraversal(
        neo4j_uri="bolt://localhost:7687",
        neo4j_user="neo4j", 
        neo4j_password="password"
    )
    
    try:
        # Detect changes in current directory
        file_changes = await traversal.detect_file_changes(".", ".")
        
        # Get files that need processing
        to_process = traversal.get_files_to_process(file_changes)
        
        print(f"Files to process: {len(to_process)}")
        for file_change in to_process[:5]:  # Show first 5
            print(f"  {file_change.status.value}: {file_change.path}")
            
    finally:
        traversal.close()

if __name__ == "__main__":
    asyncio.run(main()) 