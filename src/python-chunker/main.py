#!/usr/bin/env python3
"""
Python Code Chunker for Agentic Code Indexer
Uses LibCST for precise syntax tree parsing with comment preservation
and ast-scope for variable scope analysis.
"""

import os
import sys
import json
import hashlib
import argparse
from pathlib import Path
from typing import List, Dict, Any, Optional, Set
import logging

import libcst as cst
from libcst import metadata
import ast
from ast_scope import annotate

# Add parent directory to path to import common data format
sys.path.append(str(Path(__file__).parent.parent / "agentic_code_indexer"))
from common_data_format import (
    ChunkerOutput, FileNode, ClassNode, FunctionNode, MethodNode, 
    VariableNode, ParameterNode, ImportNode, Relationship,
    NodeType, RelationshipType, SourceLocation
)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class PythonChunker:
    """Main Python code chunker class."""
    
    def __init__(self, project_root: str):
        self.project_root = Path(project_root).resolve()
        self.nodes = []
        self.relationships = []
        self.processed_files = []
        self.node_counter = 0
        
    def generate_node_id(self, prefix: str = "node") -> str:
        """Generate unique node ID."""
        self.node_counter += 1
        return f"{prefix}_{self.node_counter}"
    
    def calculate_checksum(self, content: str) -> str:
        """Calculate SHA-256 checksum of content."""
        return hashlib.sha256(content.encode('utf-8')).hexdigest()
    
    def get_relative_path(self, file_path: Path) -> str:
        """Get path relative to project root."""
        try:
            return str(file_path.relative_to(self.project_root))
        except ValueError:
            return str(file_path)
    
    def extract_docstring(self, node: cst.CSTNode) -> Optional[str]:
        """Extract docstring from a function or class node."""
        if hasattr(node, 'body') and node.body.body:
            first_stmt = node.body.body[0]
            if isinstance(first_stmt, cst.SimpleStatementLine):
                for stmt in first_stmt.body:
                    if isinstance(stmt, cst.Expr) and isinstance(stmt.value, cst.SimpleString):
                        # Remove quotes and clean up the docstring
                        docstring = stmt.value.value
                        if docstring.startswith('"""') or docstring.startswith("'''"):
                            return docstring[3:-3].strip()
                        elif docstring.startswith('"') or docstring.startswith("'"):
                            return docstring[1:-1].strip()
                        return docstring.strip()
        return None
    
    def create_source_location(self, node: cst.CSTNode, source_code: str) -> Optional[SourceLocation]:
        """Create source location from CST node."""
        try:
            # LibCST doesn't directly provide line numbers, so we need to calculate them
            # This is a simplified approach - in production, you'd want more robust position tracking
            lines = source_code.split('\n')
            # For now, return None - proper implementation would require position metadata
            return None
        except Exception:
            return None


class PythonASTVisitor(cst.CSTVisitor):
    """Visitor class for traversing Python CST and extracting information."""
    
    METADATA_DEPENDENCIES = (metadata.PositionProvider,)
    
    def __init__(self, chunker: PythonChunker, file_path: Path, source_code: str):
        self.chunker = chunker
        self.file_path = file_path
        self.source_code = source_code
        self.current_class = None
        self.current_function = None
        self.scope_stack = []
        
        # Create file node
        self.file_node = self.create_file_node()
        chunker.nodes.append(self.file_node)
    
    def create_file_node(self) -> FileNode:
        """Create a file node for the current file."""
        file_stats = self.file_path.stat()
        return FileNode(
            id=self.chunker.generate_node_id("file"),
            name=self.file_path.name,
            full_name=self.chunker.get_relative_path(self.file_path),
            path=self.chunker.get_relative_path(self.file_path),
            absolute_path=str(self.file_path),
            extension=self.file_path.suffix,
            size=file_stats.st_size,
            checksum=self.chunker.calculate_checksum(self.source_code),
            content=self.source_code,
            language="python"
        )
    
    def visit_ClassDef(self, node: cst.ClassDef) -> None:
        """Visit class definition."""
        class_name = node.name.value
        full_name = f"{self.chunker.get_relative_path(self.file_path)}::{class_name}"
        
        # Extract base classes
        base_classes = []
        if node.bases:
            for base in node.bases:
                if isinstance(base.value, cst.Name):
                    base_classes.append(base.value.value)
                elif isinstance(base.value, cst.Attribute):
                    # Handle qualified names like module.ClassName
                    base_classes.append(self.chunker.get_source_code_for_node(base.value))
        
        # Create class node
        class_node = ClassNode(
            id=self.chunker.generate_node_id("class"),
            name=class_name,
            full_name=full_name,
            raw_code=self.source_code[node.metadata[metadata.PositionProvider].start.line-1:node.metadata[metadata.PositionProvider].end.line] if hasattr(node, 'metadata') else None,
            location=self.chunker.create_source_location(node, self.source_code),
            base_classes=base_classes,
            docstring=self.chunker.extract_docstring(node)
        )
        
        self.chunker.nodes.append(class_node)
        
        # Create relationship: File CONTAINS Class
        self.chunker.relationships.append(Relationship(
            source_id=self.file_node.id,
            target_id=class_node.id,
            type=RelationshipType.CONTAINS
        ))
        
        # Set current class context
        previous_class = self.current_class
        self.current_class = class_node
        
        # Continue traversal
        self.generic_visit(node)
        
        # Restore previous class context
        self.current_class = previous_class
    
    def visit_FunctionDef(self, node: cst.FunctionDef) -> None:
        """Visit function definition."""
        function_name = node.name.value
        
        # Determine if this is a method or standalone function
        is_method = self.current_class is not None
        
        if is_method:
            full_name = f"{self.current_class.full_name}::{function_name}"
            node_type = NodeType.METHOD
        else:
            full_name = f"{self.chunker.get_relative_path(self.file_path)}::{function_name}"
            node_type = NodeType.FUNCTION
        
        # Extract parameters
        parameters = []
        if node.params:
            for param in node.params.params:
                if isinstance(param.name, cst.Name):
                    parameters.append(param.name.value)
        
        # Extract decorators
        decorators = []
        if node.decorators:
            for decorator in node.decorators:
                if isinstance(decorator.decorator, cst.Name):
                    decorators.append(decorator.decorator.value)
        
        # Create function/method node
        if is_method:
            func_node = MethodNode(
                id=self.chunker.generate_node_id("method"),
                name=function_name,
                full_name=full_name,
                raw_code=self.source_code[node.metadata[metadata.PositionProvider].start.line-1:node.metadata[metadata.PositionProvider].end.line] if hasattr(node, 'metadata') else None,
                location=self.chunker.create_source_location(node, self.source_code),
                parameters=parameters,
                is_static="staticmethod" in decorators,
                docstring=self.chunker.extract_docstring(node),
                properties={"decorators": decorators}
            )
            
            # Create relationship: Class DEFINES Method
            self.chunker.relationships.append(Relationship(
                source_id=self.current_class.id,
                target_id=func_node.id,
                type=RelationshipType.DEFINES
            ))
        else:
            func_node = FunctionNode(
                id=self.chunker.generate_node_id("function"),
                name=function_name,
                full_name=full_name,
                raw_code=self.source_code[node.metadata[metadata.PositionProvider].start.line-1:node.metadata[metadata.PositionProvider].end.line] if hasattr(node, 'metadata') else None,
                location=self.chunker.create_source_location(node, self.source_code),
                parameters=parameters,
                is_async=isinstance(node, cst.AsyncFunctionDef),
                docstring=self.chunker.extract_docstring(node),
                properties={"decorators": decorators}
            )
            
            # Create relationship: File CONTAINS Function
            self.chunker.relationships.append(Relationship(
                source_id=self.file_node.id,
                target_id=func_node.id,
                type=RelationshipType.CONTAINS
            ))
        
        self.chunker.nodes.append(func_node)
        
        # Create parameter nodes
        if node.params:
            for param in node.params.params:
                if isinstance(param.name, cst.Name):
                    param_name = param.name.value
                    param_node = ParameterNode(
                        id=self.chunker.generate_node_id("param"),
                        name=param_name,
                        full_name=f"{full_name}::{param_name}",
                        type=str(param.annotation.annotation) if param.annotation else None,
                        default_value=str(param.default) if param.default else None
                    )
                    
                    self.chunker.nodes.append(param_node)
                    
                    # Create relationship: Function/Method DECLARES Parameter
                    self.chunker.relationships.append(Relationship(
                        source_id=func_node.id,
                        target_id=param_node.id,
                        type=RelationshipType.DECLARES
                    ))
        
        # Set current function context
        previous_function = self.current_function
        self.current_function = func_node
        
        # Continue traversal
        self.generic_visit(node)
        
        # Restore previous function context
        self.current_function = previous_function
    
    def visit_ImportFrom(self, node: cst.ImportFrom) -> None:
        """Visit from ... import ... statements."""
        module_name = ""
        if node.module:
            if isinstance(node.module, cst.Name):
                module_name = node.module.value
            elif isinstance(node.module, cst.Attribute):
                module_name = self.get_qualified_name(node.module)
        
        # Handle relative imports
        if node.relative:
            module_name = "." * len(node.relative) + module_name
        
        imported_names = []
        if node.names:
            if isinstance(node.names, cst.ImportStar):
                imported_names = ["*"]
            else:
                for name_item in node.names:
                    if isinstance(name_item.name, cst.Name):
                        imported_names.append(name_item.name.value)
        
        import_node = ImportNode(
            id=self.chunker.generate_node_id("import"),
            name=f"from {module_name} import {', '.join(imported_names)}",
            full_name=f"{self.chunker.get_relative_path(self.file_path)}::import::{module_name}",
            module=module_name,
            imported_names=imported_names,
            is_wildcard="*" in imported_names
        )
        
        self.chunker.nodes.append(import_node)
        
        # Create relationship: File IMPORTS Module
        self.chunker.relationships.append(Relationship(
            source_id=self.file_node.id,
            target_id=import_node.id,
            type=RelationshipType.IMPORTS
        ))
    
    def visit_Import(self, node: cst.Import) -> None:
        """Visit import statements."""
        for name_item in node.names:
            if isinstance(name_item.name, cst.Name):
                module_name = name_item.name.value
            elif isinstance(name_item.name, cst.Attribute):
                module_name = self.get_qualified_name(name_item.name)
            else:
                continue
            
            alias = None
            if name_item.asname:
                alias = name_item.asname.name.value
            
            import_node = ImportNode(
                id=self.chunker.generate_node_id("import"),
                name=f"import {module_name}" + (f" as {alias}" if alias else ""),
                full_name=f"{self.chunker.get_relative_path(self.file_path)}::import::{module_name}",
                module=module_name,
                alias=alias
            )
            
            self.chunker.nodes.append(import_node)
            
            # Create relationship: File IMPORTS Module
            self.chunker.relationships.append(Relationship(
                source_id=self.file_node.id,
                target_id=import_node.id,
                type=RelationshipType.IMPORTS
            ))
    
    def get_qualified_name(self, node: cst.Attribute) -> str:
        """Get qualified name from attribute access."""
        parts = []
        current = node
        
        while isinstance(current, cst.Attribute):
            parts.append(current.attr.value)
            current = current.value
        
        if isinstance(current, cst.Name):
            parts.append(current.value)
        
        return ".".join(reversed(parts))


def process_file(chunker: PythonChunker, file_path: Path) -> None:
    """Process a single Python file."""
    try:
        logger.info(f"Processing file: {file_path}")
        
        with open(file_path, 'r', encoding='utf-8') as f:
            source_code = f.read()
        
        # Parse with LibCST
        try:
            tree = cst.parse_expression(source_code) if source_code.strip() else cst.parse_module(source_code)
        except Exception:
            tree = cst.parse_module(source_code)
        
        # Create visitor and traverse
        visitor = PythonASTVisitor(chunker, file_path, source_code)
        
        # Use metadata wrapper for position information
        wrapper = metadata.MetadataWrapper(tree)
        wrapper.visit(visitor)
        
        chunker.processed_files.append(str(file_path))
        
    except Exception as e:
        logger.error(f"Error processing file {file_path}: {e}")


def find_python_files(directory: Path) -> List[Path]:
    """Find all Python files in a directory recursively."""
    python_files = []
    
    for file_path in directory.rglob("*.py"):
        if file_path.is_file():
            python_files.append(file_path)
    
    return python_files


def main():
    """Main entry point for the Python chunker."""
    parser = argparse.ArgumentParser(description="Python Code Chunker for Agentic Code Indexer")
    parser.add_argument("input_path", help="Path to Python file or directory to process")
    parser.add_argument("-o", "--output", help="Output JSON file path", default="python_chunker_output.json")
    parser.add_argument("--project-root", help="Project root directory", default=".")
    
    args = parser.parse_args()
    
    input_path = Path(args.input_path)
    project_root = Path(args.project_root)
    
    if not input_path.exists():
        logger.error(f"Input path does not exist: {input_path}")
        return 1
    
    # Initialize chunker
    chunker = PythonChunker(project_root)
    
    # Process files
    if input_path.is_file():
        if input_path.suffix == '.py':
            process_file(chunker, input_path)
        else:
            logger.error(f"Input file is not a Python file: {input_path}")
            return 1
    elif input_path.is_dir():
        python_files = find_python_files(input_path)
        logger.info(f"Found {len(python_files)} Python files")
        
        for file_path in python_files:
            process_file(chunker, file_path)
    else:
        logger.error(f"Input path is neither a file nor directory: {input_path}")
        return 1
    
    # Create output
    output = ChunkerOutput(
        language="python",
        processed_files=chunker.processed_files,
        nodes=chunker.nodes,
        relationships=chunker.relationships,
        metadata={
            "total_files": len(chunker.processed_files),
            "total_nodes": len(chunker.nodes),
            "total_relationships": len(chunker.relationships)
        }
    )
    
    # Write output
    with open(args.output, 'w', encoding='utf-8') as f:
        f.write(output.model_dump_json(indent=2))
    
    logger.info(f"Python chunker completed. Output written to: {args.output}")
    logger.info(f"Processed {len(chunker.processed_files)} files, extracted {len(chunker.nodes)} nodes, {len(chunker.relationships)} relationships")
    
    return 0


if __name__ == "__main__":
    sys.exit(main()) 