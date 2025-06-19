const fs = require('fs');
const parser = require('@babel/parser');
const traverse = require('@babel/traverse').default;
const {
    NODE_TYPES,
    REL_TYPES
} = require('./constants');
const {
    createEntityNode,
    createRelationship,
    getOrCreateFileNode,
    globalContext
} = require('./helpers');

function analyzeFile(filePath, graph, config) {
    console.log(`Analyzing file: ${filePath}`);
    const fileNode = getOrCreateFileNode(filePath, graph, config);
    globalContext.currentClassContext = null;
    globalContext.currentMethodContext = null;
    globalContext.currentScopeContext = null;
    globalContext.currentClassNode = null;
    globalContext.currentMethodNode = null;

    let code;
    try {
        code = fs.readFileSync(filePath, 'utf-8');
    } catch (error) {
        console.error(`Error reading file ${filePath}:`, error.message);
        return;
    }

    let ast;
    try {
        ast = parser.parse(code, {
            sourceType: 'module',
            plugins: ['jsx', 'typescript', 'classProperties', 'decorators-legacy']
        });
    } catch (error) {
        console.error(`Error parsing ${filePath}:`, error.message);
        return;
    }

    // Scope tracker to manage context during AST traversal
    const scopeTracker = {
        currentClass: null,
        currentMethod: null,
        declaredVariables: new Map(),
        importedModules: new Map()
    };

    traverse(ast, {
        ImportDeclaration(path) {
            const importSource = path.node.source.value;
            // External or internal import handling is retained here.
            if (config.trackExternalLibraries && !importSource.startsWith('.') && !importSource.startsWith('/')) {
                // External library logic (not expanded for brevity)
                // Handle external library import
                const libraryNode = getOrCreateExternalLibraryNode(importSource);
                createRelationship(fileNode.id, libraryNode.id, REL_TYPES.IMPORTS);

                // Track imported specifiers
                path.node.specifiers.forEach(specifier => {
                    const importedName = specifier.local.name;
                    scopeTracker.importedModules.set(importedName, libraryNode.id);
                });
            } else {
                const importNode = createEntityNode(NODE_TYPES.IMPORT, importSource, filePath, path.node.loc, {}, code, graph, config);
                graph.relationships.push(createRelationship(fileNode.id, importNode.id, REL_TYPES.IMPORTS));
                path.node.specifiers.forEach(specifier => {
                    scopeTracker.importedModules.set(specifier.local.name, importNode.id);
                });
            }
        },
        ClassDeclaration(path) {
            const className = path.node.id.name;
            const classNode = createEntityNode(NODE_TYPES.CLASS, className, filePath, path.node.loc, {}, code, graph, config);
            globalContext.currentClassContext = className;
            scopeTracker.currentClass = classNode.id;
            if (path.node.superClass) {
                const superClassName = path.node.superClass.name;
                if (scopeTracker.importedModules.has(superClassName)) {
                    graph.relationships.push(createRelationship(classNode.id, scopeTracker.importedModules.get(superClassName), REL_TYPES.EXTENDS));
                }
            }
        },
        ClassMethod(path) {
            if (!scopeTracker.currentClass) return;
            const methodName = path.node.key.name;
            const methodNode = createEntityNode(
                NODE_TYPES.METHOD,
                methodName,
                filePath,
                path.node.loc,
                { isAsync: path.node.async, isGenerator: path.node.generator, parentClass: globalContext.currentClassContext },
                code,
                graph,
                config
            );
            globalContext.currentMethodContext = methodName;
            globalContext.currentScopeContext = `${globalContext.currentClassContext}.${methodName}`;
            graph.relationships.push(createRelationship(scopeTracker.currentClass, methodNode.id, REL_TYPES.CONTAINS));
            scopeTracker.currentMethod = methodNode.id;
        },
        FunctionDeclaration(path) {
            const funcName = path.node.id.name;
            const funcNode = createEntityNode(NODE_TYPES.FUNCTION, funcName, filePath, path.node.loc, { isAsync: path.node.async, isGenerator: path.node.generator }, code, graph, config);
            globalContext.currentMethodContext = null;
            globalContext.currentScopeContext = funcName;
            scopeTracker.declaredVariables.set(funcName, funcNode.id);
        },
        VariableDeclarator(path) {
            const varName = path.node.id.name;
            const varNode = createEntityNode(NODE_TYPES.VARIABLE, varName, filePath, path.node.loc, {}, code, graph, config);
            scopeTracker.declaredVariables.set(varName, varNode.id);
            if (path.node.init) {
                if (path.node.init.type === 'CallExpression' && path.node.init.callee.name && scopeTracker.declaredVariables.has(path.node.init.callee.name)) {
                    graph.relationships.push(createRelationship(varNode.id, scopeTracker.declaredVariables.get(path.node.init.callee.name), REL_TYPES.CALLS));
                } else if (path.node.init.type === 'Identifier' && scopeTracker.declaredVariables.has(path.node.init.name)) {
                    graph.relationships.push(createRelationship(varNode.id, scopeTracker.declaredVariables.get(path.node.init.name), REL_TYPES.REFERENCES));
                }
            }
            if (scopeTracker.currentMethod) {
                graph.relationships.push(createRelationship(scopeTracker.currentMethod, varNode.id, REL_TYPES.DECLARES));
            } else if (scopeTracker.currentClass) {
                graph.relationships.push(createRelationship(scopeTracker.currentClass, varNode.id, REL_TYPES.DECLARES));
            }
        },
        BlockStatement: {
            enter(path) {
                path.node._parentScope = globalContext.currentScopeContext;
            },
            exit(path) {
                globalContext.currentScopeContext = path.node._parentScope;
            }
        },
        CallExpression(path) {
            if (path.node.callee.type === 'Identifier') {
                const calleeName = path.node.callee.name;
                if (calleeName === 'require' && path.node.arguments?.[0]?.type === 'StringLiteral') {
                    // ...existing require handling...
                }
                if (scopeTracker.declaredVariables.has(calleeName)) {
                    const sourceId = scopeTracker.currentMethod || scopeTracker.currentClass || fileNode.id;
                    graph.relationships.push(createRelationship(sourceId, scopeTracker.declaredVariables.get(calleeName), REL_TYPES.CALLS));
                }
            }
        }
        // ...other AST visitors as needed...
    });
}

module.exports = { analyzeFile };
