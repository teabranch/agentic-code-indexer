using System.Collections.Generic;
using Newtonsoft.Json;

namespace CSharpChunker.Models
{
    public enum NodeType
    {
        File,
        Directory,
        Class,
        Interface,
        Method,
        Function,
        Variable,
        Parameter,
        Import,
        Export
    }

    public enum RelationshipType
    {
        CONTAINS,
        DEFINES,
        DECLARES,
        HAS_MEMBER,
        CALLS,
        INSTANTIATES,
        EXTENDS,
        IMPLEMENTS,
        IMPORTS,
        EXPORTS,
        SCOPES,
        USES,
        REFERENCES
    }

    public class SourceLocation
    {
        [JsonProperty("start_line")]
        public int StartLine { get; set; }

        [JsonProperty("end_line")]
        public int EndLine { get; set; }

        [JsonProperty("start_column")]
        public int? StartColumn { get; set; }

        [JsonProperty("end_column")]
        public int? EndColumn { get; set; }
    }

    public abstract class BaseNode
    {
        [JsonProperty("id")]
        public string Id { get; set; }

        [JsonProperty("label")]
        public NodeType Label { get; set; }

        [JsonProperty("name")]
        public string Name { get; set; }

        [JsonProperty("full_name")]
        public string FullName { get; set; }

        [JsonProperty("raw_code")]
        public string RawCode { get; set; }

        [JsonProperty("location")]
        public SourceLocation Location { get; set; }

        [JsonProperty("properties")]
        public Dictionary<string, object> Properties { get; set; } = new Dictionary<string, object>();
    }

    public class FileNode : BaseNode
    {
        [JsonProperty("path")]
        public string Path { get; set; }

        [JsonProperty("absolute_path")]
        public string AbsolutePath { get; set; }

        [JsonProperty("extension")]
        public string Extension { get; set; }

        [JsonProperty("size")]
        public long Size { get; set; }

        [JsonProperty("checksum")]
        public string Checksum { get; set; }

        [JsonProperty("content")]
        public string Content { get; set; }

        [JsonProperty("language")]
        public string Language { get; set; }

        public FileNode()
        {
            Label = NodeType.File;
            Language = "csharp";
        }
    }

    public class DirectoryNode : BaseNode
    {
        [JsonProperty("path")]
        public string Path { get; set; }

        [JsonProperty("absolute_path")]
        public string AbsolutePath { get; set; }

        public DirectoryNode()
        {
            Label = NodeType.Directory;
        }
    }

    public class ClassNode : BaseNode
    {
        [JsonProperty("visibility")]
        public string Visibility { get; set; }

        [JsonProperty("is_abstract")]
        public bool IsAbstract { get; set; }

        [JsonProperty("is_static")]
        public bool IsStatic { get; set; }

        [JsonProperty("is_sealed")]
        public bool IsSealed { get; set; }

        [JsonProperty("base_classes")]
        public List<string> BaseClasses { get; set; } = new List<string>();

        [JsonProperty("interfaces")]
        public List<string> Interfaces { get; set; } = new List<string>();

        [JsonProperty("docstring")]
        public string Docstring { get; set; }

        public ClassNode()
        {
            Label = NodeType.Class;
        }
    }

    public class InterfaceNode : BaseNode
    {
        [JsonProperty("visibility")]
        public string Visibility { get; set; }

        [JsonProperty("base_interfaces")]
        public List<string> BaseInterfaces { get; set; } = new List<string>();

        [JsonProperty("docstring")]
        public string Docstring { get; set; }

        public InterfaceNode()
        {
            Label = NodeType.Interface;
        }
    }

    public class MethodNode : BaseNode
    {
        [JsonProperty("visibility")]
        public string Visibility { get; set; }

        [JsonProperty("is_static")]
        public bool IsStatic { get; set; }

        [JsonProperty("is_abstract")]
        public bool IsAbstract { get; set; }

        [JsonProperty("is_virtual")]
        public bool IsVirtual { get; set; }

        [JsonProperty("is_override")]
        public bool IsOverride { get; set; }

        [JsonProperty("is_async")]
        public bool IsAsync { get; set; }

        [JsonProperty("return_type")]
        public string ReturnType { get; set; }

        [JsonProperty("parameters")]
        public List<string> Parameters { get; set; } = new List<string>();

        [JsonProperty("signature")]
        public string Signature { get; set; }

        [JsonProperty("docstring")]
        public string Docstring { get; set; }

        public MethodNode()
        {
            Label = NodeType.Method;
        }
    }

    public class FunctionNode : BaseNode
    {
        [JsonProperty("return_type")]
        public string ReturnType { get; set; }

        [JsonProperty("parameters")]
        public List<string> Parameters { get; set; } = new List<string>();

        [JsonProperty("signature")]
        public string Signature { get; set; }

        [JsonProperty("is_async")]
        public bool IsAsync { get; set; }

        [JsonProperty("docstring")]
        public string Docstring { get; set; }

        public FunctionNode()
        {
            Label = NodeType.Function;
        }
    }

    public class VariableNode : BaseNode
    {
        [JsonProperty("type")]
        public string Type { get; set; }

        [JsonProperty("value")]
        public string Value { get; set; }

        [JsonProperty("is_constant")]
        public bool IsConstant { get; set; }

        [JsonProperty("is_readonly")]
        public bool IsReadonly { get; set; }

        [JsonProperty("visibility")]
        public string Visibility { get; set; }

        [JsonProperty("scope")]
        public string Scope { get; set; }

        public VariableNode()
        {
            Label = NodeType.Variable;
        }
    }

    public class ParameterNode : BaseNode
    {
        [JsonProperty("type")]
        public string Type { get; set; }

        [JsonProperty("default_value")]
        public string DefaultValue { get; set; }

        [JsonProperty("is_optional")]
        public bool IsOptional { get; set; }

        [JsonProperty("is_params")]
        public bool IsParams { get; set; }

        [JsonProperty("modifier")]
        public string Modifier { get; set; } // ref, out, in

        public ParameterNode()
        {
            Label = NodeType.Parameter;
        }
    }

    public class ImportNode : BaseNode
    {
        [JsonProperty("module")]
        public string Module { get; set; }

        [JsonProperty("alias")]
        public string Alias { get; set; }

        [JsonProperty("imported_names")]
        public List<string> ImportedNames { get; set; } = new List<string>();

        [JsonProperty("is_wildcard")]
        public bool IsWildcard { get; set; }

        public ImportNode()
        {
            Label = NodeType.Import;
        }
    }

    public class Relationship
    {
        [JsonProperty("source_id")]
        public string SourceId { get; set; }

        [JsonProperty("target_id")]
        public string TargetId { get; set; }

        [JsonProperty("type")]
        public RelationshipType Type { get; set; }

        [JsonProperty("properties")]
        public Dictionary<string, object> Properties { get; set; } = new Dictionary<string, object>();
    }

    public class ChunkerOutput
    {
        [JsonProperty("language")]
        public string Language { get; set; } = "csharp";

        [JsonProperty("version")]
        public string Version { get; set; } = "1.0.0";

        [JsonProperty("processed_files")]
        public List<string> ProcessedFiles { get; set; } = new List<string>();

        [JsonProperty("nodes")]
        public List<BaseNode> Nodes { get; set; } = new List<BaseNode>();

        [JsonProperty("relationships")]
        public List<Relationship> Relationships { get; set; } = new List<Relationship>();

        [JsonProperty("metadata")]
        public Dictionary<string, object> Metadata { get; set; } = new Dictionary<string, object>();
    }
} 