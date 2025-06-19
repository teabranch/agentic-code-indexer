/**
 * TypeScript type definitions for the NodeJS Chunker
 * Mirrors the common data format defined in Python
 */

export enum NodeType {
    FILE = "File",
    DIRECTORY = "Directory", 
    CLASS = "Class",
    INTERFACE = "Interface",
    METHOD = "Method",
    FUNCTION = "Function",
    VARIABLE = "Variable",
    PARAMETER = "Parameter",
    IMPORT = "Import",
    EXPORT = "Export"
}

export enum RelationshipType {
    CONTAINS = "CONTAINS",
    DEFINES = "DEFINES",
    DECLARES = "DECLARES",
    HAS_MEMBER = "HAS_MEMBER",
    CALLS = "CALLS",
    INSTANTIATES = "INSTANTIATES",
    EXTENDS = "EXTENDS",
    IMPLEMENTS = "IMPLEMENTS",
    IMPORTS = "IMPORTS",
    EXPORTS = "EXPORTS",
    SCOPES = "SCOPES",
    USES = "USES",
    REFERENCES = "REFERENCES"
}

export interface SourceLocation {
    start_line: number;
    end_line: number;
    start_column?: number;
    end_column?: number;
}

export interface BaseNode {
    id: string;
    label: NodeType;
    name: string;
    full_name?: string;
    raw_code?: string;
    location?: SourceLocation;
    properties?: Record<string, any>;
}

export interface FileNode extends BaseNode {
    label: NodeType.FILE;
    path: string;
    absolute_path: string;
    extension: string;
    size: number;
    checksum: string;
    content?: string;
    language: string;
}

export interface DirectoryNode extends BaseNode {
    label: NodeType.DIRECTORY;
    path: string;
    absolute_path: string;
}

export interface ClassNode extends BaseNode {
    label: NodeType.CLASS;
    visibility?: string;
    is_abstract?: boolean;
    is_static?: boolean;
    base_classes?: string[];
    interfaces?: string[];
    docstring?: string;
}

export interface InterfaceNode extends BaseNode {
    label: NodeType.INTERFACE;
    visibility?: string;
    base_interfaces?: string[];
    docstring?: string;
}

export interface MethodNode extends BaseNode {
    label: NodeType.METHOD;
    visibility?: string;
    is_static?: boolean;
    is_abstract?: boolean;
    is_virtual?: boolean;
    return_type?: string;
    parameters?: string[];
    signature?: string;
    docstring?: string;
}

export interface FunctionNode extends BaseNode {
    label: NodeType.FUNCTION;
    return_type?: string;
    parameters?: string[];
    signature?: string;
    is_async?: boolean;
    is_generator?: boolean;
    docstring?: string;
}

export interface VariableNode extends BaseNode {
    label: NodeType.VARIABLE;
    type?: string;
    value?: string;
    is_constant?: boolean;
    visibility?: string;
    scope?: string;
}

export interface ParameterNode extends BaseNode {
    label: NodeType.PARAMETER;
    type?: string;
    default_value?: string;
    is_optional?: boolean;
    is_variadic?: boolean;
}

export interface ImportNode extends BaseNode {
    label: NodeType.IMPORT;
    module: string;
    alias?: string;
    imported_names?: string[];
    is_wildcard?: boolean;
}

export interface ExportNode extends BaseNode {
    label: NodeType.EXPORT;
    exported_names?: string[];
    is_default?: boolean;
}

export type AnyNode = FileNode | DirectoryNode | ClassNode | InterfaceNode | 
                     MethodNode | FunctionNode | VariableNode | ParameterNode |
                     ImportNode | ExportNode;

export interface Relationship {
    source_id: string;
    target_id: string;
    type: RelationshipType;
    properties?: Record<string, any>;
}

export interface ChunkerOutput {
    language: string;
    version?: string;
    processed_files?: string[];
    nodes: AnyNode[];
    relationships: Relationship[];
    metadata?: Record<string, any>;
}

export interface ModuleSystem {
    type: 'esm' | 'cjs' | 'mixed';
    hasPackageJson: boolean;
    packageJsonType?: string;
} 