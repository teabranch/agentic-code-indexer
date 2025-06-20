#!/usr/bin/env python3
"""
Common Intermediate Data Format for Agentic Code Indexer
Defines Pydantic models for the structured data format that all language chunkers output.
"""

from typing import List, Optional, Dict, Any, Union
from pydantic import BaseModel, Field
from enum import Enum


class NodeType(str, Enum):
    """Enumeration of supported node types in the code graph."""
    FILE = "File"
    DIRECTORY = "Directory"
    CLASS = "Class"
    INTERFACE = "Interface"
    METHOD = "Method"
    FUNCTION = "Function"
    VARIABLE = "Variable"
    PARAMETER = "Parameter"
    IMPORT = "Import"
    EXPORT = "Export"


class RelationshipType(str, Enum):
    """Enumeration of supported relationship types in the code graph."""
    CONTAINS = "CONTAINS"
    DEFINES = "DEFINES"
    DECLARES = "DECLARES"
    HAS_MEMBER = "HAS_MEMBER"
    CALLS = "CALLS"
    INSTANTIATES = "INSTANTIATES"
    EXTENDS = "EXTENDS"
    IMPLEMENTS = "IMPLEMENTS"
    IMPORTS = "IMPORTS"
    EXPORTS = "EXPORTS"
    SCOPES = "SCOPES"
    USES = "USES"
    REFERENCES = "REFERENCES"


class SourceLocation(BaseModel):
    """Represents a source code location with line and column information."""
    start_line: int = Field(..., description="Starting line number (1-indexed)")
    end_line: int = Field(..., description="Ending line number (1-indexed)")
    start_column: Optional[int] = Field(None, description="Starting column number (0-indexed)")
    end_column: Optional[int] = Field(None, description="Ending column number (0-indexed)")


class CodeNode(BaseModel):
    """Base model for all code nodes in the graph."""
    id: str = Field(..., description="Unique identifier for the node")
    label: NodeType = Field(..., description="Type/label of the node")
    name: str = Field(..., description="Name of the code element")
    full_name: Optional[str] = Field(None, description="Fully qualified name")
    raw_code: Optional[str] = Field(None, description="Raw source code content")
    location: Optional[SourceLocation] = Field(None, description="Source location information")
    properties: Dict[str, Any] = Field(default_factory=dict, description="Additional node properties")


class FileNode(CodeNode):
    """Represents a source code file."""
    label: NodeType = Field(default=NodeType.FILE, description="Node type")
    path: str = Field(..., description="File path relative to project root")
    absolute_path: str = Field(..., description="Absolute file path")
    extension: str = Field(..., description="File extension (e.g., .py, .cs, .js)")
    size: int = Field(..., description="File size in bytes")
    checksum: str = Field(..., description="SHA-256 checksum of file content")
    content: Optional[str] = Field(None, description="Full file content")
    language: str = Field(..., description="Programming language (python, csharp, javascript, typescript)")


class DirectoryNode(CodeNode):
    """Represents a directory in the codebase."""
    label: NodeType = Field(default=NodeType.DIRECTORY, description="Node type")
    path: str = Field(..., description="Directory path relative to project root")
    absolute_path: str = Field(..., description="Absolute directory path")


class ClassNode(CodeNode):
    """Represents a class definition."""
    label: NodeType = Field(default=NodeType.CLASS, description="Node type")
    visibility: Optional[str] = Field(None, description="Visibility modifier (public, private, protected)")
    is_abstract: bool = Field(default=False, description="Whether the class is abstract")
    is_static: bool = Field(default=False, description="Whether the class is static")
    base_classes: List[str] = Field(default_factory=list, description="List of base class names")
    interfaces: List[str] = Field(default_factory=list, description="List of implemented interface names")
    docstring: Optional[str] = Field(None, description="Class documentation/docstring")


class InterfaceNode(CodeNode):
    """Represents an interface definition."""
    label: NodeType = Field(default=NodeType.INTERFACE, description="Node type")
    visibility: Optional[str] = Field(None, description="Visibility modifier")
    base_interfaces: List[str] = Field(default_factory=list, description="List of base interface names")
    docstring: Optional[str] = Field(None, description="Interface documentation/docstring")


class MethodNode(CodeNode):
    """Represents a method within a class."""
    label: NodeType = Field(default=NodeType.METHOD, description="Node type")
    visibility: Optional[str] = Field(None, description="Visibility modifier")
    is_static: bool = Field(default=False, description="Whether the method is static")
    is_abstract: bool = Field(default=False, description="Whether the method is abstract")
    is_virtual: bool = Field(default=False, description="Whether the method is virtual")
    return_type: Optional[str] = Field(None, description="Return type of the method")
    parameters: List[str] = Field(default_factory=list, description="List of parameter names")
    signature: Optional[str] = Field(None, description="Full method signature")
    docstring: Optional[str] = Field(None, description="Method documentation/docstring")


class FunctionNode(CodeNode):
    """Represents a standalone function."""
    label: NodeType = Field(default=NodeType.FUNCTION, description="Node type")
    return_type: Optional[str] = Field(None, description="Return type of the function")
    parameters: List[str] = Field(default_factory=list, description="List of parameter names")
    signature: Optional[str] = Field(None, description="Full function signature")
    is_async: bool = Field(default=False, description="Whether the function is async")
    is_generator: bool = Field(default=False, description="Whether the function is a generator")
    docstring: Optional[str] = Field(None, description="Function documentation/docstring")


class VariableNode(CodeNode):
    """Represents a variable declaration."""
    label: NodeType = Field(default=NodeType.VARIABLE, description="Node type")
    type: Optional[str] = Field(None, description="Variable type")
    value: Optional[str] = Field(None, description="Initial value (as string)")
    is_constant: bool = Field(default=False, description="Whether the variable is constant")
    visibility: Optional[str] = Field(None, description="Visibility modifier")
    scope: Optional[str] = Field(None, description="Variable scope (local, instance, class, global)")


class ParameterNode(CodeNode):
    """Represents a function/method parameter."""
    label: NodeType = Field(default=NodeType.PARAMETER, description="Node type")
    type: Optional[str] = Field(None, description="Parameter type")
    default_value: Optional[str] = Field(None, description="Default value (as string)")
    is_optional: bool = Field(default=False, description="Whether the parameter is optional")
    is_variadic: bool = Field(default=False, description="Whether the parameter is variadic (*args, **kwargs)")


class ImportNode(CodeNode):
    """Represents an import statement."""
    label: NodeType = Field(default=NodeType.IMPORT, description="Node type")
    module: str = Field(..., description="Module being imported")
    alias: Optional[str] = Field(None, description="Import alias")
    imported_names: List[str] = Field(default_factory=list, description="Specific names imported")
    is_wildcard: bool = Field(default=False, description="Whether it's a wildcard import")


class ExportNode(CodeNode):
    """Represents an export statement (JavaScript/TypeScript)."""
    label: NodeType = Field(default=NodeType.EXPORT, description="Node type")
    exported_names: List[str] = Field(default_factory=list, description="Names being exported")
    is_default: bool = Field(default=False, description="Whether it's a default export")


class Relationship(BaseModel):
    """Represents a relationship between two nodes in the code graph."""
    source_id: str = Field(..., description="ID of the source node")
    target_id: str = Field(..., description="ID of the target node")
    type: RelationshipType = Field(..., description="Type of relationship")
    properties: Dict[str, Any] = Field(default_factory=dict, description="Additional relationship properties")


class ChunkerOutput(BaseModel):
    """Root model representing the output from a language-specific chunker."""
    language: str = Field(..., description="Programming language (python, csharp, javascript, typescript)")
    version: str = Field(default="1.0.0", description="Schema version")
    processed_files: List[str] = Field(default_factory=list, description="List of processed file paths")
    nodes: List[Union[
        FileNode, DirectoryNode, ClassNode, InterfaceNode, 
        MethodNode, FunctionNode, VariableNode, ParameterNode,
        ImportNode, ExportNode
    ]] = Field(default_factory=list, description="List of extracted nodes")
    relationships: List[Relationship] = Field(default_factory=list, description="List of relationships between nodes")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")


# Type aliases for convenience
AnyNode = Union[
    FileNode, DirectoryNode, ClassNode, InterfaceNode,
    MethodNode, FunctionNode, VariableNode, ParameterNode,
    ImportNode, ExportNode
] 