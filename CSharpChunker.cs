using System;
using System.Collections.Generic;
using System.IO;
using System.Linq;
using System.Security.Cryptography;
using System.Text;
using System.Threading.Tasks;
using Microsoft.CodeAnalysis;
using Microsoft.CodeAnalysis.CSharp;
using Microsoft.CodeAnalysis.CSharp.Syntax;
using Microsoft.CodeAnalysis.MSBuild;
using CSharpChunker.Models;

namespace CSharpChunker
{
    public class CSharpCodeChunker
    {
        private readonly string _projectRoot;
        private readonly List<BaseNode> _nodes;
        private readonly List<Relationship> _relationships;
        private readonly List<string> _processedFiles;
        private int _nodeCounter;

        public CSharpCodeChunker(string projectRoot)
        {
            _projectRoot = Path.GetFullPath(projectRoot);
            _nodes = new List<BaseNode>();
            _relationships = new List<Relationship>();
            _processedFiles = new List<string>();
            _nodeCounter = 0;
        }

        private string GenerateNodeId(string prefix = "node")
        {
            _nodeCounter++;
            return $"{prefix}_{_nodeCounter}";
        }

        private string CalculateChecksum(string content)
        {
            using (var sha256 = SHA256.Create())
            {
                var hash = sha256.ComputeHash(Encoding.UTF8.GetBytes(content));
                return BitConverter.ToString(hash).Replace("-", "").ToLowerInvariant();
            }
        }

        private string GetRelativePath(string filePath)
        {
            try
            {
                return Path.GetRelativePath(_projectRoot, filePath);
            }
            catch
            {
                return filePath;
            }
        }

        private SourceLocation CreateSourceLocation(SyntaxNode node, SyntaxTree syntaxTree)
        {
            if (node == null || syntaxTree == null) return null;

            var span = node.Span;
            var lineSpan = syntaxTree.GetLineSpan(span);

            return new SourceLocation
            {
                StartLine = lineSpan.StartLinePosition.Line + 1, // Convert to 1-indexed
                EndLine = lineSpan.EndLinePosition.Line + 1,
                StartColumn = lineSpan.StartLinePosition.Character,
                EndColumn = lineSpan.EndLinePosition.Character
            };
        }

        private string GetVisibility(SyntaxTokenList modifiers)
        {
            if (modifiers.Any(SyntaxKind.PublicKeyword)) return "public";
            if (modifiers.Any(SyntaxKind.PrivateKeyword)) return "private";
            if (modifiers.Any(SyntaxKind.ProtectedKeyword)) return "protected";
            if (modifiers.Any(SyntaxKind.InternalKeyword)) return "internal";
            return "private"; // Default in C#
        }

        private string ExtractDocumentationComment(SyntaxNode node)
        {
            var documentationComment = node.GetLeadingTrivia()
                .FirstOrDefault(t => t.IsKind(SyntaxKind.SingleLineDocumentationCommentTrivia) || 
                                    t.IsKind(SyntaxKind.MultiLineDocumentationCommentTrivia));

            if (documentationComment.IsKind(SyntaxKind.None))
                return null;

            return documentationComment.ToString().Trim();
        }

        public async Task<ChunkerOutput> ProcessSolutionAsync(string solutionPath)
        {
            using (var workspace = MSBuildWorkspace.Create())
            {
                try
                {
                    var solution = await workspace.OpenSolutionAsync(solutionPath);
                    
                    foreach (var project in solution.Projects)
                    {
                        await ProcessProjectAsync(project);
                    }
                }
                catch (Exception ex)
                {
                    Console.WriteLine($"Error opening solution: {ex.Message}");
                }
            }

            return CreateOutput();
        }

        public async Task<ChunkerOutput> ProcessProjectAsync(string projectPath)
        {
            using (var workspace = MSBuildWorkspace.Create())
            {
                try
                {
                    var project = await workspace.OpenProjectAsync(projectPath);
                    await ProcessProjectAsync(project);
                }
                catch (Exception ex)
                {
                    Console.WriteLine($"Error opening project: {ex.Message}");
                }
            }

            return CreateOutput();
        }

        private async Task ProcessProjectAsync(Project project)
        {
            var compilation = await project.GetCompilationAsync();
            
            foreach (var document in project.Documents)
            {
                if (document.SourceCodeKind == SourceCodeKind.Regular)
                {
                    await ProcessDocumentAsync(document, compilation);
                }
            }
        }

        private async Task ProcessDocumentAsync(Document document, Compilation compilation)
        {
            try
            {
                var syntaxTree = await document.GetSyntaxTreeAsync();
                var semanticModel = compilation.GetSemanticModel(syntaxTree);
                var root = await syntaxTree.GetRootAsync();
                var sourceText = await document.GetTextAsync();

                // Create file node
                var fileInfo = new FileInfo(document.FilePath);
                var fileNode = new FileNode
                {
                    Id = GenerateNodeId("file"),
                    Name = Path.GetFileName(document.FilePath),
                    FullName = GetRelativePath(document.FilePath),
                    Path = GetRelativePath(document.FilePath),
                    AbsolutePath = document.FilePath,
                    Extension = Path.GetExtension(document.FilePath),
                    Size = fileInfo.Length,
                    Checksum = CalculateChecksum(sourceText.ToString()),
                    Content = sourceText.ToString()
                };

                _nodes.Add(fileNode);
                _processedFiles.Add(document.FilePath);

                // Process the syntax tree
                var walker = new CSharpSyntaxWalker(this, fileNode, syntaxTree, semanticModel);
                walker.Visit(root);
            }
            catch (Exception ex)
            {
                Console.WriteLine($"Error processing document {document.FilePath}: {ex.Message}");
            }
        }

        public async Task<ChunkerOutput> ProcessSingleFileAsync(string filePath)
        {
            try
            {
                var fileContent = await File.ReadAllTextAsync(filePath);
                var syntaxTree = CSharpSyntaxTree.ParseText(fileContent, path: filePath);
                
                // Create a minimal compilation for semantic analysis
                var compilation = CSharpCompilation.Create("TempCompilation")
                    .AddReferences(MetadataReference.CreateFromFile(typeof(object).Assembly.Location))
                    .AddSyntaxTrees(syntaxTree);

                var semanticModel = compilation.GetSemanticModel(syntaxTree);
                var root = await syntaxTree.GetRootAsync();

                // Create file node
                var fileInfo = new FileInfo(filePath);
                var fileNode = new FileNode
                {
                    Id = GenerateNodeId("file"),
                    Name = Path.GetFileName(filePath),
                    FullName = GetRelativePath(filePath),
                    Path = GetRelativePath(filePath),
                    AbsolutePath = filePath,
                    Extension = Path.GetExtension(filePath),
                    Size = fileInfo.Length,
                    Checksum = CalculateChecksum(fileContent),
                    Content = fileContent
                };

                _nodes.Add(fileNode);
                _processedFiles.Add(filePath);

                // Process the syntax tree
                var walker = new CSharpSyntaxWalker(this, fileNode, syntaxTree, semanticModel);
                walker.Visit(root);
            }
            catch (Exception ex)
            {
                Console.WriteLine($"Error processing file {filePath}: {ex.Message}");
            }

            return CreateOutput();
        }

        private ChunkerOutput CreateOutput()
        {
            return new ChunkerOutput
            {
                ProcessedFiles = _processedFiles,
                Nodes = _nodes,
                Relationships = _relationships,
                Metadata = new Dictionary<string, object>
                {
                    ["total_files"] = _processedFiles.Count,
                    ["total_nodes"] = _nodes.Count,
                    ["total_relationships"] = _relationships.Count
                }
            };
        }

        public void AddNode(BaseNode node) => _nodes.Add(node);
        public void AddRelationship(Relationship relationship) => _relationships.Add(relationship);
        public string GenerateId(string prefix = "node") => GenerateNodeId(prefix);

        public SourceLocation GetSourceLocation(SyntaxNode node, SyntaxTree syntaxTree)
        {
            return CreateSourceLocation(node, syntaxTree);
        }

        public string GetNodeVisibility(SyntaxTokenList modifiers)
        {
            return GetVisibility(modifiers);
        }

        public string GetDocumentation(SyntaxNode node)
        {
            return ExtractDocumentationComment(node);
        }
    }

    public class CSharpSyntaxWalker : CSharpSyntaxWalker
    {
        private readonly CSharpCodeChunker _chunker;
        private readonly FileNode _fileNode;
        private readonly SyntaxTree _syntaxTree;
        private readonly SemanticModel _semanticModel;

        public CSharpSyntaxWalker(CSharpCodeChunker chunker, FileNode fileNode, SyntaxTree syntaxTree, SemanticModel semanticModel)
        {
            _chunker = chunker;
            _fileNode = fileNode;
            _syntaxTree = syntaxTree;
            _semanticModel = semanticModel;
        }

        public override void VisitUsingDirective(UsingDirectiveSyntax node)
        {
            var importNode = new ImportNode
            {
                Id = _chunker.GenerateId("import"),
                Name = $"using {node.Name}",
                FullName = $"{_fileNode.FullName}::using::{node.Name}",
                Module = node.Name.ToString(),
                Location = _chunker.GetSourceLocation(node, _syntaxTree)
            };

            if (node.Alias != null)
            {
                importNode.Alias = node.Alias.Name.ToString();
            }

            _chunker.AddNode(importNode);
            _chunker.AddRelationship(new Relationship
            {
                SourceId = _fileNode.Id,
                TargetId = importNode.Id,
                Type = RelationshipType.IMPORTS
            });

            base.VisitUsingDirective(node);
        }

        public override void VisitNamespaceDeclaration(NamespaceDeclarationSyntax node)
        {
            // Process namespace as a container
            base.VisitNamespaceDeclaration(node);
        }

        public override void VisitFileScopedNamespaceDeclaration(FileScopedNamespaceDeclarationSyntax node)
        {
            // Process file-scoped namespace
            base.VisitFileScopedNamespaceDeclaration(node);
        }

        public override void VisitClassDeclaration(ClassDeclarationSyntax node)
        {
            ProcessClassDeclaration(node);
            base.VisitClassDeclaration(node);
        }

        public override void VisitInterfaceDeclaration(InterfaceDeclarationSyntax node)
        {
            ProcessInterfaceDeclaration(node);
            base.VisitInterfaceDeclaration(node);
        }

        public override void VisitMethodDeclaration(MethodDeclarationSyntax node)
        {
            ProcessMethodDeclaration(node);
            base.VisitMethodDeclaration(node);
        }

        public override void VisitConstructorDeclaration(ConstructorDeclarationSyntax node)
        {
            ProcessConstructorDeclaration(node);
            base.VisitConstructorDeclaration(node);
        }

        public override void VisitPropertyDeclaration(PropertyDeclarationSyntax node)
        {
            ProcessPropertyDeclaration(node);
            base.VisitPropertyDeclaration(node);
        }

        public override void VisitFieldDeclaration(FieldDeclarationSyntax node)
        {
            ProcessFieldDeclaration(node);
            base.VisitFieldDeclaration(node);
        }

        private void ProcessClassDeclaration(ClassDeclarationSyntax node)
        {
            var symbol = _semanticModel.GetDeclaredSymbol(node) as INamedTypeSymbol;
            var fullName = symbol?.ToDisplayString() ?? $"{_fileNode.FullName}::{node.Identifier.ValueText}";

            var classNode = new ClassNode
            {
                Id = _chunker.GenerateId("class"),
                Name = node.Identifier.ValueText,
                FullName = fullName,
                RawCode = node.ToString(),
                Location = _chunker.GetSourceLocation(node, _syntaxTree),
                Visibility = _chunker.GetNodeVisibility(node.Modifiers),
                IsAbstract = node.Modifiers.Any(SyntaxKind.AbstractKeyword),
                IsStatic = node.Modifiers.Any(SyntaxKind.StaticKeyword),
                IsSealed = node.Modifiers.Any(SyntaxKind.SealedKeyword),
                Docstring = _chunker.GetDocumentation(node)
            };

            // Process base class and interfaces
            if (node.BaseList != null)
            {
                foreach (var baseType in node.BaseList.Types)
                {
                    var baseSymbol = _semanticModel.GetSymbolInfo(baseType.Type).Symbol as INamedTypeSymbol;
                    var baseName = baseSymbol?.ToDisplayString() ?? baseType.Type.ToString();

                    if (baseSymbol?.TypeKind == TypeKind.Class)
                    {
                        classNode.BaseClasses.Add(baseName);
                    }
                    else if (baseSymbol?.TypeKind == TypeKind.Interface)
                    {
                        classNode.Interfaces.Add(baseName);
                    }
                }
            }

            _chunker.AddNode(classNode);
            _chunker.AddRelationship(new Relationship
            {
                SourceId = _fileNode.Id,
                TargetId = classNode.Id,
                Type = RelationshipType.CONTAINS
            });
        }

        private void ProcessInterfaceDeclaration(InterfaceDeclarationSyntax node)
        {
            var symbol = _semanticModel.GetDeclaredSymbol(node) as INamedTypeSymbol;
            var fullName = symbol?.ToDisplayString() ?? $"{_fileNode.FullName}::{node.Identifier.ValueText}";

            var interfaceNode = new InterfaceNode
            {
                Id = _chunker.GenerateId("interface"),
                Name = node.Identifier.ValueText,
                FullName = fullName,
                RawCode = node.ToString(),
                Location = _chunker.GetSourceLocation(node, _syntaxTree),
                Visibility = _chunker.GetNodeVisibility(node.Modifiers),
                Docstring = _chunker.GetDocumentation(node)
            };

            // Process base interfaces
            if (node.BaseList != null)
            {
                foreach (var baseType in node.BaseList.Types)
                {
                    var baseSymbol = _semanticModel.GetSymbolInfo(baseType.Type).Symbol as INamedTypeSymbol;
                    var baseName = baseSymbol?.ToDisplayString() ?? baseType.Type.ToString();
                    interfaceNode.BaseInterfaces.Add(baseName);
                }
            }

            _chunker.AddNode(interfaceNode);
            _chunker.AddRelationship(new Relationship
            {
                SourceId = _fileNode.Id,
                TargetId = interfaceNode.Id,
                Type = RelationshipType.CONTAINS
            });
        }

        private void ProcessMethodDeclaration(MethodDeclarationSyntax node)
        {
            var symbol = _semanticModel.GetDeclaredSymbol(node) as IMethodSymbol;
            var fullName = symbol?.ToDisplayString() ?? $"{GetContainingTypeName(node)}::{node.Identifier.ValueText}";

            var methodNode = new MethodNode
            {
                Id = _chunker.GenerateId("method"),
                Name = node.Identifier.ValueText,
                FullName = fullName,
                RawCode = node.ToString(),
                Location = _chunker.GetSourceLocation(node, _syntaxTree),
                Visibility = _chunker.GetNodeVisibility(node.Modifiers),
                IsStatic = node.Modifiers.Any(SyntaxKind.StaticKeyword),
                IsAbstract = node.Modifiers.Any(SyntaxKind.AbstractKeyword),
                IsVirtual = node.Modifiers.Any(SyntaxKind.VirtualKeyword),
                IsOverride = node.Modifiers.Any(SyntaxKind.OverrideKeyword),
                IsAsync = node.Modifiers.Any(SyntaxKind.AsyncKeyword),
                ReturnType = node.ReturnType.ToString(),
                Signature = symbol?.ToDisplayString() ?? node.ToString(),
                Docstring = _chunker.GetDocumentation(node)
            };

            // Process parameters
            foreach (var parameter in node.ParameterList.Parameters)
            {
                methodNode.Parameters.Add(parameter.Identifier.ValueText);
                ProcessParameter(parameter, methodNode.Id);
            }

            _chunker.AddNode(methodNode);

            // Find parent class/interface and create relationship
            var parentType = GetParentTypeNode(node);
            if (parentType != null)
            {
                _chunker.AddRelationship(new Relationship
                {
                    SourceId = parentType,
                    TargetId = methodNode.Id,
                    Type = RelationshipType.DEFINES
                });
            }
        }

        private void ProcessConstructorDeclaration(ConstructorDeclarationSyntax node)
        {
            var symbol = _semanticModel.GetDeclaredSymbol(node) as IMethodSymbol;
            var fullName = symbol?.ToDisplayString() ?? $"{GetContainingTypeName(node)}::{node.Identifier.ValueText}";

            var methodNode = new MethodNode
            {
                Id = _chunker.GenerateId("constructor"),
                Name = node.Identifier.ValueText,
                FullName = fullName,
                RawCode = node.ToString(),
                Location = _chunker.GetSourceLocation(node, _syntaxTree),
                Visibility = _chunker.GetNodeVisibility(node.Modifiers),
                IsStatic = node.Modifiers.Any(SyntaxKind.StaticKeyword),
                ReturnType = "void",
                Signature = symbol?.ToDisplayString() ?? node.ToString(),
                Docstring = _chunker.GetDocumentation(node)
            };

            methodNode.Properties["is_constructor"] = true;

            // Process parameters
            foreach (var parameter in node.ParameterList.Parameters)
            {
                methodNode.Parameters.Add(parameter.Identifier.ValueText);
                ProcessParameter(parameter, methodNode.Id);
            }

            _chunker.AddNode(methodNode);

            var parentType = GetParentTypeNode(node);
            if (parentType != null)
            {
                _chunker.AddRelationship(new Relationship
                {
                    SourceId = parentType,
                    TargetId = methodNode.Id,
                    Type = RelationshipType.DEFINES
                });
            }
        }

        private void ProcessPropertyDeclaration(PropertyDeclarationSyntax node)
        {
            var symbol = _semanticModel.GetDeclaredSymbol(node) as IPropertySymbol;
            var fullName = symbol?.ToDisplayString() ?? $"{GetContainingTypeName(node)}::{node.Identifier.ValueText}";

            var variableNode = new VariableNode
            {
                Id = _chunker.GenerateId("property"),
                Name = node.Identifier.ValueText,
                FullName = fullName,
                RawCode = node.ToString(),
                Location = _chunker.GetSourceLocation(node, _syntaxTree),
                Type = node.Type.ToString(),
                Visibility = _chunker.GetNodeVisibility(node.Modifiers),
                IsReadonly = node.AccessorList?.Accessors.All(a => a.IsKind(SyntaxKind.GetAccessorDeclaration)) ?? false,
                Scope = "instance"
            };

            variableNode.Properties["is_property"] = true;

            if (node.Modifiers.Any(SyntaxKind.StaticKeyword))
            {
                variableNode.Scope = "static";
            }

            _chunker.AddNode(variableNode);

            var parentType = GetParentTypeNode(node);
            if (parentType != null)
            {
                _chunker.AddRelationship(new Relationship
                {
                    SourceId = parentType,
                    TargetId = variableNode.Id,
                    Type = RelationshipType.HAS_MEMBER
                });
            }
        }

        private void ProcessFieldDeclaration(FieldDeclarationSyntax node)
        {
            foreach (var variable in node.Declaration.Variables)
            {
                var symbol = _semanticModel.GetDeclaredSymbol(variable) as IFieldSymbol;
                var fullName = symbol?.ToDisplayString() ?? $"{GetContainingTypeName(node)}::{variable.Identifier.ValueText}";

                var variableNode = new VariableNode
                {
                    Id = _chunker.GenerateId("field"),
                    Name = variable.Identifier.ValueText,
                    FullName = fullName,
                    RawCode = node.ToString(),
                    Location = _chunker.GetSourceLocation(variable, _syntaxTree),
                    Type = node.Declaration.Type.ToString(),
                    Visibility = _chunker.GetNodeVisibility(node.Modifiers),
                    IsConstant = node.Modifiers.Any(SyntaxKind.ConstKeyword),
                    IsReadonly = node.Modifiers.Any(SyntaxKind.ReadOnlyKeyword),
                    Scope = node.Modifiers.Any(SyntaxKind.StaticKeyword) ? "static" : "instance"
                };

                if (variable.Initializer != null)
                {
                    variableNode.Value = variable.Initializer.Value.ToString();
                }

                _chunker.AddNode(variableNode);

                var parentType = GetParentTypeNode(node);
                if (parentType != null)
                {
                    _chunker.AddRelationship(new Relationship
                    {
                        SourceId = parentType,
                        TargetId = variableNode.Id,
                        Type = RelationshipType.HAS_MEMBER
                    });
                }
            }
        }

        private void ProcessParameter(ParameterSyntax parameter, string parentMethodId)
        {
            var symbol = _semanticModel.GetDeclaredSymbol(parameter) as IParameterSymbol;
            var fullName = symbol?.ToDisplayString() ?? $"{parentMethodId}::{parameter.Identifier.ValueText}";

            var paramNode = new ParameterNode
            {
                Id = _chunker.GenerateId("param"),
                Name = parameter.Identifier.ValueText,
                FullName = fullName,
                Type = parameter.Type?.ToString(),
                IsOptional = parameter.Default != null,
                IsParams = parameter.Modifiers.Any(SyntaxKind.ParamsKeyword),
                Location = _chunker.GetSourceLocation(parameter, _syntaxTree)
            };

            if (parameter.Default != null)
            {
                paramNode.DefaultValue = parameter.Default.Value.ToString();
            }

            if (parameter.Modifiers.Any(SyntaxKind.RefKeyword))
                paramNode.Modifier = "ref";
            else if (parameter.Modifiers.Any(SyntaxKind.OutKeyword))
                paramNode.Modifier = "out";
            else if (parameter.Modifiers.Any(SyntaxKind.InKeyword))
                paramNode.Modifier = "in";

            _chunker.AddNode(paramNode);
            _chunker.AddRelationship(new Relationship
            {
                SourceId = parentMethodId,
                TargetId = paramNode.Id,
                Type = RelationshipType.DECLARES
            });
        }

        private string GetContainingTypeName(SyntaxNode node)
        {
            var containingType = node.Ancestors().OfType<TypeDeclarationSyntax>().FirstOrDefault();
            if (containingType != null)
            {
                var symbol = _semanticModel.GetDeclaredSymbol(containingType) as INamedTypeSymbol;
                return symbol?.ToDisplayString() ?? containingType.Identifier.ValueText;
            }
            return _fileNode.FullName;
        }

        private string GetParentTypeNode(SyntaxNode node)
        {
            var containingType = node.Ancestors().OfType<TypeDeclarationSyntax>().FirstOrDefault();
            if (containingType != null)
            {
                // Find the corresponding node in our processed nodes
                var symbol = _semanticModel.GetDeclaredSymbol(containingType) as INamedTypeSymbol;
                var fullName = symbol?.ToDisplayString() ?? $"{_fileNode.FullName}::{containingType.Identifier.ValueText}";
                
                var parentNode = _chunker._nodes.OfType<ClassNode>().FirstOrDefault(n => n.FullName == fullName) ??
                                _chunker._nodes.OfType<InterfaceNode>().FirstOrDefault(n => n.FullName == fullName);
                
                return parentNode?.Id;
            }
            return _fileNode.Id;
        }
    }
} 