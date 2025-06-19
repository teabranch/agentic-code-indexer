#!/usr/bin/env node
/**
 * NodeJS/TypeScript Code Chunker for Agentic Code Indexer
 */

import * as fs from 'fs';
import * as path from 'path';
import * as crypto from 'crypto';
import { glob } from 'glob';
import { Command } from 'commander';
import * as acorn from 'acorn';
import * as ts from 'typescript';

import {
    ChunkerOutput, AnyNode, Relationship, FileNode, FunctionNode, ClassNode,
    VariableNode, ParameterNode, ImportNode, ExportNode, InterfaceNode, MethodNode,
    NodeType, RelationshipType, SourceLocation, ModuleSystem
} from './types';

class NodeJSChunker {
    private projectRoot: string;
    private nodes: AnyNode[] = [];
    private relationships: Relationship[] = [];
    private processedFiles: string[] = [];
    private nodeCounter = 0;

    constructor(projectRoot: string) {
        this.projectRoot = path.resolve(projectRoot);
    }

    private generateNodeId(prefix: string = 'node'): string {
        this.nodeCounter++;
        return `${prefix}_${this.nodeCounter}`;
    }

    private calculateChecksum(content: string): string {
        return crypto.createHash('sha256').update(content, 'utf8').digest('hex');
    }

    private getRelativePath(filePath: string): string {
        return path.relative(this.projectRoot, filePath);
    }

    private createFileNode(filePath: string, content: string, language: string): FileNode {
        const stats = fs.statSync(filePath);
        
        return {
            id: this.generateNodeId('file'),
            label: NodeType.FILE,
            name: path.basename(filePath),
            full_name: this.getRelativePath(filePath),
            path: this.getRelativePath(filePath),
            absolute_path: filePath,
            extension: path.extname(filePath),
            size: stats.size,
            checksum: this.calculateChecksum(content),
            content: content,
            language: language
        };
    }

    private createSourceLocation(node: any, sourceFile?: ts.SourceFile): SourceLocation | undefined {
        if (sourceFile && node.pos !== undefined && node.end !== undefined) {
            const start = sourceFile.getLineAndCharacterOfPosition(node.pos);
            const end = sourceFile.getLineAndCharacterOfPosition(node.end);
            
            return {
                start_line: start.line + 1, // Convert to 1-indexed
                end_line: end.line + 1,
                start_column: start.character,
                end_column: end.character
            };
        }
        
        // For acorn nodes
        if (node.loc) {
            return {
                start_line: node.loc.start.line,
                end_line: node.loc.end.line,
                start_column: node.loc.start.column,
                end_column: node.loc.end.column
            };
        }
        
        return undefined;
    }

    private detectModuleSystem(filePath: string): ModuleSystem {
        const dir = path.dirname(filePath);
        const packageJsonPath = this.findPackageJson(dir);
        
        let packageJsonType: string | undefined;
        let hasPackageJson = false;
        
        if (packageJsonPath) {
            hasPackageJson = true;
            try {
                const packageJson = JSON.parse(fs.readFileSync(packageJsonPath, 'utf8'));
                packageJsonType = packageJson.type;
            } catch (e) {
                // Ignore package.json parsing errors
            }
        }
        
        const ext = path.extname(filePath);
        
        // Determine module system based on extension and package.json
        if (ext === '.mjs' || (ext === '.js' && packageJsonType === 'module')) {
            return { type: 'esm', hasPackageJson, packageJsonType };
        } else if (ext === '.cjs' || (ext === '.js' && packageJsonType === 'commonjs')) {
            return { type: 'cjs', hasPackageJson, packageJsonType };
        } else if (ext === '.ts' || ext === '.tsx') {
            return { type: 'esm', hasPackageJson, packageJsonType }; // TypeScript defaults to ESM-style
        }
        
        return { type: 'cjs', hasPackageJson, packageJsonType }; // Default to CommonJS
    }

    private findPackageJson(dir: string): string | null {
        let currentDir = dir;
        
        while (currentDir !== path.dirname(currentDir)) {
            const packageJsonPath = path.join(currentDir, 'package.json');
            if (fs.existsSync(packageJsonPath)) {
                return packageJsonPath;
            }
            currentDir = path.dirname(currentDir);
        }
        
        return null;
    }

    private processJavaScriptFile(filePath: string, content: string): void {
        const moduleSystem = this.detectModuleSystem(filePath);
        
        try {
            // Parse with acorn
            const ast = acorn.parse(content, {
                ecmaVersion: 2022,
                sourceType: moduleSystem.type === 'esm' ? 'module' : 'script',
                locations: true,
                ranges: true
            });

            // Create file node
            const fileNode = this.createFileNode(filePath, content, 'javascript');
            this.nodes.push(fileNode);

            // Process AST
            this.processAcornNode(ast, fileNode, content, moduleSystem);

        } catch (error) {
            console.error(`Error parsing JavaScript file ${filePath}:`, error);
        }
    }

    private processTypeScriptFile(filePath: string, content: string): void {
        try {
            // Create TypeScript source file
            const sourceFile = ts.createSourceFile(
                filePath,
                content,
                ts.ScriptTarget.Latest,
                true,
                ts.ScriptKind.TS
            );

            // Create file node
            const language = path.extname(filePath) === '.tsx' ? 'typescript-react' : 'typescript';
            const fileNode = this.createFileNode(filePath, content, language);
            this.nodes.push(fileNode);

            // Process TypeScript AST
            this.processTypeScriptNode(sourceFile, fileNode, sourceFile);

        } catch (error) {
            console.error(`Error parsing TypeScript file ${filePath}:`, error);
        }
    }

    private processAcornNode(node: any, parentNode: AnyNode, sourceCode: string, moduleSystem: ModuleSystem): void {
        switch (node.type) {
            case 'FunctionDeclaration':
                this.processFunctionDeclaration(node, parentNode, sourceCode);
                break;
            case 'VariableDeclaration':
                this.processVariableDeclaration(node, parentNode, sourceCode);
                break;
            case 'ImportDeclaration':
                this.processImportDeclaration(node, parentNode);
                break;
            case 'ExportNamedDeclaration':
            case 'ExportDefaultDeclaration':
                this.processExportDeclaration(node, parentNode);
                break;
            case 'ClassDeclaration':
                this.processClassDeclaration(node, parentNode, sourceCode);
                break;
            case 'CallExpression':
                // Handle CommonJS require() calls
                if (moduleSystem.type === 'cjs' && this.isRequireCall(node)) {
                    this.processRequireCall(node, parentNode);
                }
                break;
            case 'AssignmentExpression':
                // Handle CommonJS module.exports
                if (moduleSystem.type === 'cjs' && this.isModuleExports(node)) {
                    this.processModuleExports(node, parentNode);
                }
                break;
        }

        // Recursively process child nodes
        for (const key in node) {
            const child = node[key];
            if (child && typeof child === 'object') {
                if (Array.isArray(child)) {
                    child.forEach(c => {
                        if (c && typeof c === 'object' && c.type) {
                            this.processAcornNode(c, parentNode, sourceCode, moduleSystem);
                        }
                    });
                } else if (child.type) {
                    this.processAcornNode(child, parentNode, sourceCode, moduleSystem);
                }
            }
        }
    }

    private processTypeScriptNode(node: ts.Node, parentNode: AnyNode, sourceFile: ts.SourceFile): void {
        switch (node.kind) {
            case ts.SyntaxKind.FunctionDeclaration:
                this.processTSFunctionDeclaration(node as ts.FunctionDeclaration, parentNode, sourceFile);
                break;
            case ts.SyntaxKind.ClassDeclaration:
                this.processTSClassDeclaration(node as ts.ClassDeclaration, parentNode, sourceFile);
                break;
            case ts.SyntaxKind.InterfaceDeclaration:
                this.processTSInterfaceDeclaration(node as ts.InterfaceDeclaration, parentNode, sourceFile);
                break;
            case ts.SyntaxKind.VariableStatement:
                this.processTSVariableStatement(node as ts.VariableStatement, parentNode, sourceFile);
                break;
            case ts.SyntaxKind.ImportDeclaration:
                this.processTSImportDeclaration(node as ts.ImportDeclaration, parentNode, sourceFile);
                break;
            case ts.SyntaxKind.ExportDeclaration:
            case ts.SyntaxKind.ExportAssignment:
                this.processTSExportDeclaration(node, parentNode, sourceFile);
                break;
        }

        // Continue traversal
        ts.forEachChild(node, child => {
            this.processTypeScriptNode(child, parentNode, sourceFile);
        });
    }

    private processFunctionDeclaration(node: any, parentNode: AnyNode, sourceCode: string): void {
        if (!node.id || !node.id.name) return;

        const functionNode: FunctionNode = {
            id: this.generateNodeId('function'),
            label: NodeType.FUNCTION,
            name: node.id.name,
            full_name: `${parentNode.full_name}::${node.id.name}`,
            raw_code: sourceCode.substring(node.start, node.end),
            location: this.createSourceLocation(node),
            is_async: node.async || false,
            is_generator: node.generator || false,
            parameters: node.params.map((param: any) => param.name || param.left?.name || 'unknown')
        };

        this.nodes.push(functionNode);
        
        // Create relationship
        this.relationships.push({
            source_id: parentNode.id,
            target_id: functionNode.id,
            type: RelationshipType.CONTAINS
        });

        // Process parameters
        node.params.forEach((param: any) => {
            this.processParameter(param, functionNode);
        });
    }

    private processTSFunctionDeclaration(node: ts.FunctionDeclaration, parentNode: AnyNode, sourceFile: ts.SourceFile): void {
        if (!node.name) return;

        const functionNode: FunctionNode = {
            id: this.generateNodeId('function'),
            label: NodeType.FUNCTION,
            name: node.name.getText(sourceFile),
            full_name: `${parentNode.full_name}::${node.name.getText(sourceFile)}`,
            raw_code: node.getFullText(sourceFile),
            location: this.createSourceLocation(node, sourceFile),
            is_async: !!(node.modifiers?.some(mod => mod.kind === ts.SyntaxKind.AsyncKeyword)),
            return_type: node.type ? node.type.getText(sourceFile) : undefined,
            parameters: node.parameters.map(param => param.name.getText(sourceFile))
        };

        this.nodes.push(functionNode);
        
        this.relationships.push({
            source_id: parentNode.id,
            target_id: functionNode.id,
            type: RelationshipType.CONTAINS
        });

        // Process parameters
        node.parameters.forEach(param => {
            this.processTSParameter(param, functionNode, sourceFile);
        });
    }

    private processClassDeclaration(node: any, parentNode: AnyNode, sourceCode: string): void {
        if (!node.id || !node.id.name) return;

        const classNode: ClassNode = {
            id: this.generateNodeId('class'),
            label: NodeType.CLASS,
            name: node.id.name,
            full_name: `${parentNode.full_name}::${node.id.name}`,
            raw_code: sourceCode.substring(node.start, node.end),
            location: this.createSourceLocation(node),
            base_classes: node.superClass ? [this.getNodeName(node.superClass)] : []
        };

        this.nodes.push(classNode);
        
        this.relationships.push({
            source_id: parentNode.id,
            target_id: classNode.id,
            type: RelationshipType.CONTAINS
        });

        // Process class methods
        if (node.body && node.body.body) {
            node.body.body.forEach((member: any) => {
                if (member.type === 'MethodDefinition') {
                    this.processMethodDefinition(member, classNode, sourceCode);
                }
            });
        }
    }

    private processTSClassDeclaration(node: ts.ClassDeclaration, parentNode: AnyNode, sourceFile: ts.SourceFile): void {
        if (!node.name) return;

        const classNode: ClassNode = {
            id: this.generateNodeId('class'),
            label: NodeType.CLASS,
            name: node.name.getText(sourceFile),
            full_name: `${parentNode.full_name}::${node.name.getText(sourceFile)}`,
            raw_code: node.getFullText(sourceFile),
            location: this.createSourceLocation(node, sourceFile),
            is_abstract: !!(node.modifiers?.some(mod => mod.kind === ts.SyntaxKind.AbstractKeyword)),
            base_classes: node.heritageClauses?.filter(clause => clause.token === ts.SyntaxKind.ExtendsKeyword)
                .flatMap(clause => clause.types.map(type => type.expression.getText(sourceFile))) || [],
            interfaces: node.heritageClauses?.filter(clause => clause.token === ts.SyntaxKind.ImplementsKeyword)
                .flatMap(clause => clause.types.map(type => type.expression.getText(sourceFile))) || []
        };

        this.nodes.push(classNode);
        
        this.relationships.push({
            source_id: parentNode.id,
            target_id: classNode.id,
            type: RelationshipType.CONTAINS
        });

        // Process class members
        node.members.forEach(member => {
            if (ts.isMethodDeclaration(member)) {
                this.processTSMethodDeclaration(member, classNode, sourceFile);
            }
        });
    }

    private processTSInterfaceDeclaration(node: ts.InterfaceDeclaration, parentNode: AnyNode, sourceFile: ts.SourceFile): void {
        const interfaceNode: InterfaceNode = {
            id: this.generateNodeId('interface'),
            label: NodeType.INTERFACE,
            name: node.name.getText(sourceFile),
            full_name: `${parentNode.full_name}::${node.name.getText(sourceFile)}`,
            raw_code: node.getFullText(sourceFile),
            location: this.createSourceLocation(node, sourceFile),
            base_interfaces: node.heritageClauses?.flatMap(clause => 
                clause.types.map(type => type.expression.getText(sourceFile))
            ) || []
        };

        this.nodes.push(interfaceNode);
        
        this.relationships.push({
            source_id: parentNode.id,
            target_id: interfaceNode.id,
            type: RelationshipType.CONTAINS
        });
    }

    private processMethodDefinition(node: any, classNode: ClassNode, sourceCode: string): void {
        if (!node.key || !node.key.name) return;

        const methodNode: MethodNode = {
            id: this.generateNodeId('method'),
            label: NodeType.METHOD,
            name: node.key.name,
            full_name: `${classNode.full_name}::${node.key.name}`,
            raw_code: sourceCode.substring(node.start, node.end),
            location: this.createSourceLocation(node),
            is_static: node.static || false,
            parameters: node.value.params.map((param: any) => param.name || 'unknown')
        };

        this.nodes.push(methodNode);
        
        this.relationships.push({
            source_id: classNode.id,
            target_id: methodNode.id,
            type: RelationshipType.DEFINES
        });
    }

    private processTSMethodDeclaration(node: ts.MethodDeclaration, classNode: ClassNode, sourceFile: ts.SourceFile): void {
        if (!node.name) return;

        const methodNode: MethodNode = {
            id: this.generateNodeId('method'),
            label: NodeType.METHOD,
            name: node.name.getText(sourceFile),
            full_name: `${classNode.full_name}::${node.name.getText(sourceFile)}`,
            raw_code: node.getFullText(sourceFile),
            location: this.createSourceLocation(node, sourceFile),
            is_static: !!(node.modifiers?.some(mod => mod.kind === ts.SyntaxKind.StaticKeyword)),
            is_abstract: !!(node.modifiers?.some(mod => mod.kind === ts.SyntaxKind.AbstractKeyword)),
            return_type: node.type ? node.type.getText(sourceFile) : undefined,
            parameters: node.parameters.map(param => param.name.getText(sourceFile))
        };

        this.nodes.push(methodNode);
        
        this.relationships.push({
            source_id: classNode.id,
            target_id: methodNode.id,
            type: RelationshipType.DEFINES
        });

        // Process parameters
        node.parameters.forEach(param => {
            this.processTSParameter(param, methodNode, sourceFile);
        });
    }

    private processParameter(param: any, parentNode: FunctionNode | MethodNode): void {
        const paramName = param.name || param.left?.name || 'unknown';
        
        const paramNode: ParameterNode = {
            id: this.generateNodeId('param'),
            label: NodeType.PARAMETER,
            name: paramName,
            full_name: `${parentNode.full_name}::${paramName}`,
            is_optional: !!param.optional,
            default_value: param.right ? 'has_default' : undefined
        };

        this.nodes.push(paramNode);
        
        this.relationships.push({
            source_id: parentNode.id,
            target_id: paramNode.id,
            type: RelationshipType.DECLARES
        });
    }

    private processTSParameter(param: ts.ParameterDeclaration, parentNode: FunctionNode | MethodNode, sourceFile: ts.SourceFile): void {
        const paramNode: ParameterNode = {
            id: this.generateNodeId('param'),
            label: NodeType.PARAMETER,
            name: param.name.getText(sourceFile),
            full_name: `${parentNode.full_name}::${param.name.getText(sourceFile)}`,
            type: param.type ? param.type.getText(sourceFile) : undefined,
            is_optional: !!param.questionToken,
            default_value: param.initializer ? param.initializer.getText(sourceFile) : undefined
        };

        this.nodes.push(paramNode);
        
        this.relationships.push({
            source_id: parentNode.id,
            target_id: paramNode.id,
            type: RelationshipType.DECLARES
        });
    }

    private processVariableDeclaration(node: any, parentNode: AnyNode, sourceCode: string): void {
        if (!node.declarations) return;

        node.declarations.forEach((decl: any) => {
            if (decl.id && decl.id.name) {
                const varNode: VariableNode = {
                    id: this.generateNodeId('var'),
                    label: NodeType.VARIABLE,
                    name: decl.id.name,
                    full_name: `${parentNode.full_name}::${decl.id.name}`,
                    raw_code: sourceCode.substring(decl.start, decl.end),
                    location: this.createSourceLocation(decl),
                    is_constant: node.kind === 'const',
                    value: decl.init ? 'has_initializer' : undefined
                };

                this.nodes.push(varNode);
                
                this.relationships.push({
                    source_id: parentNode.id,
                    target_id: varNode.id,
                    type: RelationshipType.DECLARES
                });
            }
        });
    }

    private processTSVariableStatement(node: ts.VariableStatement, parentNode: AnyNode, sourceFile: ts.SourceFile): void {
        node.declarationList.declarations.forEach(decl => {
            if (ts.isIdentifier(decl.name)) {
                const varNode: VariableNode = {
                    id: this.generateNodeId('var'),
                    label: NodeType.VARIABLE,
                    name: decl.name.getText(sourceFile),
                    full_name: `${parentNode.full_name}::${decl.name.getText(sourceFile)}`,
                    raw_code: decl.getFullText(sourceFile),
                    location: this.createSourceLocation(decl, sourceFile),
                    is_constant: !!(node.declarationList.flags & ts.NodeFlags.Const),
                    type: decl.type ? decl.type.getText(sourceFile) : undefined,
                    value: decl.initializer ? decl.initializer.getText(sourceFile) : undefined
                };

                this.nodes.push(varNode);
                
                this.relationships.push({
                    source_id: parentNode.id,
                    target_id: varNode.id,
                    type: RelationshipType.DECLARES
                });
            }
        });
    }

    private processImportDeclaration(node: any, parentNode: AnyNode): void {
        if (!node.source || !node.source.value) return;

        const importedNames: string[] = [];
        
        if (node.specifiers) {
            node.specifiers.forEach((spec: any) => {
                if (spec.type === 'ImportDefaultSpecifier') {
                    importedNames.push('default');
                } else if (spec.type === 'ImportNamespaceSpecifier') {
                    importedNames.push('*');
                } else if (spec.type === 'ImportSpecifier') {
                    importedNames.push(spec.imported.name);
                }
            });
        }

        const importNode: ImportNode = {
            id: this.generateNodeId('import'),
            label: NodeType.IMPORT,
            name: `import from ${node.source.value}`,
            full_name: `${parentNode.full_name}::import::${node.source.value}`,
            module: node.source.value,
            imported_names: importedNames,
            is_wildcard: importedNames.includes('*')
        };

        this.nodes.push(importNode);
        
        this.relationships.push({
            source_id: parentNode.id,
            target_id: importNode.id,
            type: RelationshipType.IMPORTS
        });
    }

    private processTSImportDeclaration(node: ts.ImportDeclaration, parentNode: AnyNode, sourceFile: ts.SourceFile): void {
        if (!node.moduleSpecifier || !ts.isStringLiteral(node.moduleSpecifier)) return;

        const importedNames: string[] = [];
        
        if (node.importClause) {
            if (node.importClause.name) {
                importedNames.push('default');
            }
            if (node.importClause.namedBindings) {
                if (ts.isNamespaceImport(node.importClause.namedBindings)) {
                    importedNames.push('*');
                } else if (ts.isNamedImports(node.importClause.namedBindings)) {
                    node.importClause.namedBindings.elements.forEach(element => {
                        importedNames.push(element.name.getText(sourceFile));
                    });
                }
            }
        }

        const importNode: ImportNode = {
            id: this.generateNodeId('import'),
            label: NodeType.IMPORT,
            name: `import from ${node.moduleSpecifier.text}`,
            full_name: `${parentNode.full_name}::import::${node.moduleSpecifier.text}`,
            module: node.moduleSpecifier.text,
            imported_names: importedNames,
            is_wildcard: importedNames.includes('*')
        };

        this.nodes.push(importNode);
        
        this.relationships.push({
            source_id: parentNode.id,
            target_id: importNode.id,
            type: RelationshipType.IMPORTS
        });
    }

    private processExportDeclaration(node: any, parentNode: AnyNode): void {
        const exportedNames: string[] = [];
        let isDefault = false;

        if (node.type === 'ExportDefaultDeclaration') {
            isDefault = true;
            exportedNames.push('default');
        } else if (node.specifiers) {
            node.specifiers.forEach((spec: any) => {
                if (spec.exported) {
                    exportedNames.push(spec.exported.name);
                }
            });
        }

        const exportNode: ExportNode = {
            id: this.generateNodeId('export'),
            label: NodeType.EXPORT,
            name: isDefault ? 'export default' : `export ${exportedNames.join(', ')}`,
            full_name: `${parentNode.full_name}::export`,
            exported_names: exportedNames,
            is_default: isDefault
        };

        this.nodes.push(exportNode);
        
        this.relationships.push({
            source_id: parentNode.id,
            target_id: exportNode.id,
            type: RelationshipType.EXPORTS
        });
    }

    private processTSExportDeclaration(node: ts.Node, parentNode: AnyNode, sourceFile: ts.SourceFile): void {
        const exportedNames: string[] = [];
        let isDefault = false;

        if (ts.isExportAssignment(node)) {
            isDefault = true;
            exportedNames.push('default');
        } else if (ts.isExportDeclaration(node) && node.exportClause) {
            if (ts.isNamedExports(node.exportClause)) {
                node.exportClause.elements.forEach(element => {
                    exportedNames.push(element.name.getText(sourceFile));
                });
            }
        }

        const exportNode: ExportNode = {
            id: this.generateNodeId('export'),
            label: NodeType.EXPORT,
            name: isDefault ? 'export default' : `export ${exportedNames.join(', ')}`,
            full_name: `${parentNode.full_name}::export`,
            exported_names: exportedNames,
            is_default: isDefault
        };

        this.nodes.push(exportNode);
        
        this.relationships.push({
            source_id: parentNode.id,
            target_id: exportNode.id,
            type: RelationshipType.EXPORTS
        });
    }

    private isRequireCall(node: any): boolean {
        return node.type === 'CallExpression' && 
               node.callee.type === 'Identifier' && 
               node.callee.name === 'require' &&
               node.arguments.length > 0 &&
               node.arguments[0].type === 'Literal';
    }

    private processRequireCall(node: any, parentNode: AnyNode): void {
        const moduleName = node.arguments[0].value;
        
        const importNode: ImportNode = {
            id: this.generateNodeId('import'),
            label: NodeType.IMPORT,
            name: `require('${moduleName}')`,
            full_name: `${parentNode.full_name}::require::${moduleName}`,
            module: moduleName
        };

        this.nodes.push(importNode);
        
        this.relationships.push({
            source_id: parentNode.id,
            target_id: importNode.id,
            type: RelationshipType.IMPORTS
        });
    }

    private isModuleExports(node: any): boolean {
        return node.type === 'AssignmentExpression' &&
               node.left.type === 'MemberExpression' &&
               ((node.left.object.name === 'module' && node.left.property.name === 'exports') ||
                node.left.object.name === 'exports');
    }

    private processModuleExports(node: any, parentNode: AnyNode): void {
        const exportNode: ExportNode = {
            id: this.generateNodeId('export'),
            label: NodeType.EXPORT,
            name: 'module.exports',
            full_name: `${parentNode.full_name}::module.exports`,
            exported_names: ['default'],
            is_default: true
        };

        this.nodes.push(exportNode);
        
        this.relationships.push({
            source_id: parentNode.id,
            target_id: exportNode.id,
            type: RelationshipType.EXPORTS
        });
    }

    private getNodeName(node: any): string {
        if (node.type === 'Identifier') {
            return node.name;
        } else if (node.type === 'MemberExpression') {
            return `${this.getNodeName(node.object)}.${this.getNodeName(node.property)}`;
        }
        return 'unknown';
    }

    public async processFile(filePath: string): Promise<void> {
        try {
            console.log(`Processing file: ${filePath}`);
            
            const content = fs.readFileSync(filePath, 'utf8');
            const ext = path.extname(filePath).toLowerCase();
            
            if (ext === '.ts' || ext === '.tsx') {
                this.processTypeScriptFile(filePath, content);
            } else if (ext === '.js' || ext === '.jsx' || ext === '.mjs' || ext === '.cjs') {
                this.processJavaScriptFile(filePath, content);
            }
            
            this.processedFiles.push(filePath);
            
        } catch (error) {
            console.error(`Error processing file ${filePath}:`, error);
        }
    }

    public async processDirectory(dirPath: string): Promise<void> {
        const patterns = [
            '**/*.js',
            '**/*.jsx', 
            '**/*.ts',
            '**/*.tsx',
            '**/*.mjs',
            '**/*.cjs'
        ];

        for (const pattern of patterns) {
            const files = await glob(pattern, { 
                cwd: dirPath,
                absolute: true,
                ignore: ['**/node_modules/**', '**/dist/**', '**/build/**', '**/*.d.ts']
            });

            for (const file of files) {
                await this.processFile(file);
            }
        }
    }

    public getOutput(): ChunkerOutput {
        return {
            language: 'javascript-typescript',
            version: '1.0.0',
            processed_files: this.processedFiles,
            nodes: this.nodes,
            relationships: this.relationships,
            metadata: {
                total_files: this.processedFiles.length,
                total_nodes: this.nodes.length,
                total_relationships: this.relationships.length
            }
        };
    }
}

async function main() {
    const program = new Command();
    
    program
        .name('nodejs-chunker')
        .description('NodeJS/TypeScript Code Chunker for Agentic Code Indexer')
        .version('1.0.0');

    program
        .argument('<input>', 'Input file or directory to process')
        .option('-o, --output <file>', 'Output JSON file', 'nodejs_chunker_output.json')
        .option('--project-root <dir>', 'Project root directory', '.')
        .action(async (input, options) => {
            const inputPath = path.resolve(input);
            const projectRoot = path.resolve(options.projectRoot);
            
            if (!fs.existsSync(inputPath)) {
                console.error(`Input path does not exist: ${inputPath}`);
                process.exit(1);
            }

            const chunker = new NodeJSChunker(projectRoot);
            
            const stats = fs.statSync(inputPath);
            if (stats.isFile()) {
                await chunker.processFile(inputPath);
            } else if (stats.isDirectory()) {
                await chunker.processDirectory(inputPath);
            } else {
                console.error(`Input path is neither a file nor directory: ${inputPath}`);
                process.exit(1);
            }

            const output = chunker.getOutput();
            
            fs.writeFileSync(options.output, JSON.stringify(output, null, 2));
            
            console.log(`NodeJS chunker completed. Output written to: ${options.output}`);
        });

    await program.parseAsync();
}

if (require.main === module) {
    main().catch(console.error);
} 