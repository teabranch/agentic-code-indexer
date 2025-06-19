// Node types
const NODE_TYPES = {
    FOLDER: 'Folder',
    FILE: 'File',
    CLASS: 'Class',
    METHOD: 'Method',
    VARIABLE: 'Variable',
    FUNCTION: 'Function',
    IMPORT: 'Import',
    EXTERNAL_LIBRARY: 'ExternalLibrary'
  };
  
  // Relationship types
  const REL_TYPES = {
    CONTAINS: 'CONTAINS',
    IMPORTS: 'IMPORTS',
    CALLS: 'CALLS',
    EXTENDS: 'EXTENDS',
    IMPLEMENTS: 'IMPLEMENTS',
    REFERENCES: 'REFERENCES',
    DECLARES: 'DECLARES'
  };
  
  // Track created nodes to avoid duplicates
  const nodeRegistry = {
    folderNodes: new Map(),
    fileNodes: new Map(),
    entityNodes: new Map()
  };
  
  // Track content for duplicate entity names
  const contentRegistry = {
    folderContents: new Map(), // Map of folder name -> array of folder contents
    fileContents: new Map(),   // Map of file name -> array of file contents
    classScopes: new Map(),    // Map of class name -> array of class scope contents
    methodScopes: new Map()    // Map of method name -> array of method scope contents
  };
  
  // Helper to check if an ID is a placeholder
  function isPlaceholder(id) {
    return typeof id === 'string' && id.startsWith('placeholder_');
  }
  
  // Track global context during AST traversal
  const global = {
    currentClassContext: null,
    currentMethodContext: null,  
    currentScopeContext: null,
    currentClassNode: null,
    currentMethodNode: null
  };
  
  // Check if a path is an external library
  function isExternalLibrary(importPath) {
    // Checks if the import path doesn't start with ./ or ../ or /
    return !importPath.startsWith('.') && !importPath.startsWith('/');
  }
  
  // Get or create an external library node
  function getOrCreateExternalLibraryNode(libraryName) {
    if (externalLibraries.has(libraryName)) {
      return externalLibraries.get(libraryName);
    }
    
    // Extract the base library name (e.g., 'lodash' from 'lodash/map')
    const baseLibName = libraryName.split('/')[0];
    
    // Check if we already have the base library
    if (externalLibraries.has(baseLibName)) {
      return externalLibraries.get(baseLibName);
    }
    
    // Create new library node
    const node = createNode(NODE_TYPES.EXTERNAL_LIBRARY, baseLibName, null, {
      isExternal: true,
      originalImport: libraryName
    });
    
    externalLibraries.set(baseLibName, node);
    return node;
  }
  
  const fs = require('fs');
  const path = require('path');
  const parser = require('@babel/parser');
  const traverse = require('@babel/traverse').default;
  const { v4: uuidv4 } = require('uuid');
  
  // Default configuration
  const defaultConfig = {
    includeVariables: false,  // Variables are excluded by default
    includeImports: true,
    includeFolders: true,
    includeFiles: true,
    includeClasses: true,
    includeMethods: true,
    includeFunctions: true,
    ignoreNodeModules: true,  // Ignore node_modules by default
    trackExternalLibraries: true,  // Track external libraries as single entities
    captureContent: true  // New flag to control detailed content capture
  };
  
  // Main graph data structure
  const graph = {
    nodes: [],
    relationships: []
  };
  
  // Active configuration
  let config = { ...defaultConfig };
  
  // Track external libraries
  const externalLibraries = new Map();
  
  // Helper to generate a meaningful, stable ID
  function generateMeaningfulId(type, name, filePath = null, location = null) {
    // Clean up the name to use in the ID
    const cleanName = name.replace(/[^a-zA-Z0-9_]/g, '_').substring(0, 40);
    
    // Base format: [type]-[name]
    let id = `${type.toLowerCase()}-${cleanName}`;
    
    // Handle folder paths specially to avoid self-references
    if (type === NODE_TYPES.FOLDER) {
      // Special handling for root folders
      if (filePath === '.' || filePath === './' || filePath === '\\') {
        return 'folder-root';
      }
      
      // For folders, add normalized path hash to ensure uniqueness
      if (filePath) {
        const folderName = path.basename(filePath);
        const normalizedPath = path.normalize(filePath).replace(/\\/g, '/');
        
        if (folderName === '.' || folderName === '..') {
          // Handle current/parent directory references
          const pathSegments = normalizedPath.split('/').filter(Boolean);
          const dirName = pathSegments.length > 0 ? pathSegments[pathSegments.length - 1] : 'root';
          id = `folder-${dirName}-${Buffer.from(normalizedPath).toString('base64').substring(0, 8)}`;
        } else {
          // Normal folder - add path hash for uniqueness
          id = `folder-${folderName.replace(/[^a-zA-Z0-9_]/g, '_')}-${Buffer.from(normalizedPath).toString('base64').substring(0, 8)}`;
        }
      }
    } else if (type === NODE_TYPES.FILE) {
      // For files, include normalized path hash for uniqueness
      if (filePath) {
        const filename = path.basename(filePath);
        const normalizedPath = path.normalize(filePath).replace(/\\/g, '/');
        id = `file-${filename.replace(/[^a-zA-Z0-9_.]/g, '_')}-${Buffer.from(normalizedPath).toString('base64').substring(0, 8)}`;
      }
    } else if (type === NODE_TYPES.CLASS) {
      // Classes should include file path to ensure uniqueness
      if (filePath) {
        const filename = path.basename(filePath).replace(/\.[^/.]+$/, "");
        id = `class-${cleanName}-${filename.replace(/[^a-zA-Z0-9_]/g, '_')}`;
        
        // Add location info for extra uniqueness if available
        if (location) {
          id += `-L${location.start.line}`;
        }
      }
    } else if (type === NODE_TYPES.METHOD) {
      // Methods need class context and file for uniqueness
      if (filePath) {
        const filename = path.basename(filePath).replace(/\.[^/.]+$/, "");
        // Use class context when available
        const classContext = global.currentClassContext || '';
        id = `method-${cleanName}-${classContext}-${filename.replace(/[^a-zA-Z0-9_]/g, '_')}`;
        
        // Add location info for extra uniqueness
        if (location) {
          id += `-L${location.start.line}`;
        }
      }
    } else if (type === NODE_TYPES.FUNCTION) {
      // Functions need file context for uniqueness
      if (filePath) {
        const filename = path.basename(filePath).replace(/\.[^/.]+$/, "");
        id = `function-${cleanName}-${filename.replace(/[^a-zA-Z0-9_]/g, '_')}`;
        
        // Add location info for uniqueness
        if (location) {
          id += `-L${location.start.line}`;
        }
      }
    } else if (type === NODE_TYPES.VARIABLE) {
      // Variables need scope and file context
      if (filePath) {
        const filename = path.basename(filePath).replace(/\.[^/.]+$/, "");
        const scopeContext = global.currentScopeContext || '';
        id = `variable-${cleanName}-${scopeContext}-${filename.replace(/[^a-zA-Z0-9_]/g, '_')}`;
        
        if (location) {
          id += `-L${location.start.line}`;
        }
      }
    } else if (type === NODE_TYPES.EXTERNAL_LIBRARY) {
      // External libraries - add version info if available
      const version = global.packageVersions && global.packageVersions[name] 
        ? `-${global.packageVersions[name].replace(/[^a-zA-Z0-9_.]/g, '_')}`
        : '';
      id = `lib-${cleanName}${version}`;
    }
    
    return id;
  }
    
  // Helper to create a node
  function createNode(type, name, filePath = null, metadata = {}) {
    const location = metadata.location || null;
    const id = generateMeaningfulId(type, name, filePath, location);
    
    const node = {
      id,
      type,
      name,
      filePath,
      ...metadata
    };
    
    graph.nodes.push(node);
    return node;
  }
  
  // Helper to create relationships
  function createRelationship(sourceId, targetId, type, metadata = {}) {
    const relationship = {
      id: `${sourceId}-${type}-${targetId}`,  // Changed: use a concatenated id
      source: sourceId,
      target: targetId,
      type,
      ...metadata
    };
    
    graph.relationships.push(relationship);
    return relationship;
  }
  
  // Helper to add content to contentRegistry for duplicate handling
  function registerContent(type, name, content) {
    if (!config.captureContent) return;
    
    let registry;
    switch (type) {
      case NODE_TYPES.FOLDER:
        registry = contentRegistry.folderContents;
        break;
      case NODE_TYPES.FILE:
        registry = contentRegistry.fileContents;
        break;
      case NODE_TYPES.CLASS:
        registry = contentRegistry.classScopes;
        break;
      case NODE_TYPES.METHOD:
        registry = contentRegistry.methodScopes;
        break;
      default:
        return; // Don't register for other types
    }
    
    // Add content to registry
    if (registry.has(name)) {
      registry.get(name).push(content);
    } else {
      registry.set(name, [content]);
    }
  }
  
  // Create or get folder node
  function getOrCreateFolderNode(folderPath) {
    if (nodeRegistry.folderNodes.has(folderPath)) {
      return nodeRegistry.folderNodes.get(folderPath);
    }
    
    const folderName = path.basename(folderPath);
    // Clean and ensure uniqueness by including path hash
    const node = createNode(NODE_TYPES.FOLDER, folderName, folderPath);
    nodeRegistry.folderNodes.set(folderPath, node);
    
    // Create relationship with parent folder
    const parentPath = path.dirname(folderPath);
    if (parentPath !== folderPath) {
      const parentNode = getOrCreateFolderNode(parentPath);
      createRelationship(parentNode.id, node.id, REL_TYPES.CONTAINS);
    }
    
    // Register folder content if config allows
    if (config.captureContent) {
      try {
        // Get list of files/folders in this directory
        const items = fs.readdirSync(folderPath);
        const folderContent = items.map(item => {
          const itemPath = path.join(folderPath, item);
          const stats = fs.statSync(itemPath);
          return {
            name: item,
            type: stats.isDirectory() ? 'folder' : 'file',
            size: stats.size,
            lastModified: stats.mtime
          };
        });
        
        // Update node with folder contents
        node.contentCount = folderContent.length;
        node.contentSummary = `${folderContent.filter(i => i.type === 'folder').length} folders, ${folderContent.filter(i => i.type === 'file').length} files`;
        
        // Register content in content registry
        registerContent(NODE_TYPES.FOLDER, folderName, folderContent);
      } catch (error) {
        console.error(`Error reading folder contents for ${folderPath}:`, error.message);
      }
    }
    
    return node;
  }
  
  // Create or get file node
  function getOrCreateFileNode(filePath) {
    if (nodeRegistry.fileNodes.has(filePath)) {
      return nodeRegistry.fileNodes.get(filePath);
    }
    
    const fileName = path.basename(filePath);
    const node = createNode(NODE_TYPES.FILE, fileName, filePath);
    nodeRegistry.fileNodes.set(filePath, node);
    
    // Create relationship with containing folder
    const folderPath = path.dirname(filePath);
    const folderNode = getOrCreateFolderNode(folderPath);
    createRelationship(folderNode.id, node.id, REL_TYPES.CONTAINS);
    
    // Register file content if config allows
    if (config.captureContent) {
      try {
        const fileContent = fs.readFileSync(filePath, 'utf-8');
        node.fileSize = fileContent.length;
        node.lineCount = fileContent.split('\n').length;
        
        // Register content in content registry
        registerContent(NODE_TYPES.FILE, fileName, fileContent);
      } catch (error) {
        console.error(`Error reading file content for ${filePath}:`, error.message);
      }
    }
    
    return node;
  }
  
  // Extract content from AST node
  function extractSourceCode(sourceCode, loc) {
    if (!sourceCode || !loc) return '';
    
    try {
      const lines = sourceCode.split('\n');
      const startLine = loc.start.line - 1;
      const endLine = loc.end.line - 1;
      
      if (startLine === endLine) {
        return lines[startLine].substring(loc.start.column, loc.end.column);
      } else {
        const codeLines = [];
        // First line from start column to end
        codeLines.push(lines[startLine].substring(loc.start.column));
        
        // Middle lines (if any)
        for (let i = startLine + 1; i < endLine; i++) {
          codeLines.push(lines[i]);
        }
        
        // Last line from beginning to end column
        codeLines.push(lines[endLine].substring(0, loc.end.column));
        
        return codeLines.join('\n');
      }
    } catch (error) {
      console.error(`Error extracting source code:`, error.message);
      return '';
    }
  }
  
  // Create entity node (class, method, variable, etc)
  function createEntityNode(type, name, filePath, loc, metadata = {}, sourceCode = null) {
    // Check if this type of node should be included based on configuration
    if (
      (type === NODE_TYPES.VARIABLE && !config.includeVariables) ||
      (type === NODE_TYPES.IMPORT && !config.includeImports) ||
      (type === NODE_TYPES.CLASS && !config.includeClasses) ||
      (type === NODE_TYPES.METHOD && !config.includeMethods) ||
      (type === NODE_TYPES.FUNCTION && !config.includeFunctions)
    ) {
      // Return a placeholder id as string for tracking in scope but not in actual graph
      return `placeholder_${type}_${name}`;
    }
    
    const key = `${filePath}:${type}:${name}:${loc.start.line}:${loc.start.column}`;
    
    if (nodeRegistry.entityNodes.has(key)) {
      return nodeRegistry.entityNodes.get(key);
    }
    
    // Add code scope content if provided
    if (config.captureContent && sourceCode) {
      const codeContent = extractSourceCode(sourceCode, loc);
      if (codeContent) {
        metadata.codeScope = codeContent;
        
        // Register content in appropriate registry
        if (type === NODE_TYPES.CLASS || type === NODE_TYPES.METHOD) {
          registerContent(type, name, codeContent);
        }
      }
    }
    
    const node = createNode(type, name, filePath, {
      location: {
        start: { line: loc.start.line, column: loc.start.column },
        end: { line: loc.end.line, column: loc.end.column }
      },
      ...metadata
    });
    
    nodeRegistry.entityNodes.set(key, node);
    
    // Create relationship with containing file
    const fileNode = getOrCreateFileNode(filePath);
    createRelationship(fileNode.id, node.id, REL_TYPES.CONTAINS);
    
    // Update global tracking for class and method contexts
    if (type === NODE_TYPES.CLASS) {
      global.currentClassNode = node.id;
    } else if (type === NODE_TYPES.METHOD) {
      global.currentMethodNode = node.id;
    }
    
    return node;
  }
  
  // Parse and analyze a JS file
  function analyzeFile(filePath) {
    console.log(`Analyzing file: ${filePath}`);
    const fileNode = getOrCreateFileNode(filePath);
    
    // Reset global context for this file
    global.currentClassContext = null;
    global.currentMethodContext = null;
    global.currentScopeContext = null;
    global.currentClassNode = null;
    global.currentMethodNode = null;
    
    try {
      const code = fs.readFileSync(filePath, 'utf-8');
      
      // Parse the code
      const ast = parser.parse(code, {
        sourceType: 'module',
        plugins: ['jsx', 'typescript', 'classProperties', 'decorators-legacy']
      });
      
      // Track scope for variable references
      const scopeTracker = {
        currentClass: null,
        currentMethod: null,
        declaredVariables: new Map(),
        importedModules: new Map()
      };
      
      // Traverse the AST
      traverse(ast, {
        ImportDeclaration(path) {
          const importSource = path.node.source.value;
          
          if (config.trackExternalLibraries && isExternalLibrary(importSource)) {
            // Handle external library import
            const libraryNode = getOrCreateExternalLibraryNode(importSource);
            createRelationship(fileNode.id, libraryNode.id, REL_TYPES.IMPORTS);
            
            // Track imported specifiers
            path.node.specifiers.forEach(specifier => {
              const importedName = specifier.local.name;
              scopeTracker.importedModules.set(importedName, libraryNode.id);
            });
          } else {
            // Handle internal module import
            const importNode = createEntityNode(
              NODE_TYPES.IMPORT, 
              importSource, 
              filePath, 
              path.node.loc,
              {},
              code
            );
            
            createRelationship(fileNode.id, importNode.id, REL_TYPES.IMPORTS);
            
            // Track imported specifiers
            path.node.specifiers.forEach(specifier => {
              const importedName = specifier.local.name;
              scopeTracker.importedModules.set(importedName, importNode.id);
            });
          }
        },
        
        ClassDeclaration(path) {
          const className = path.node.id.name;
          const classNode = createEntityNode(
            NODE_TYPES.CLASS, 
            className, 
            filePath, 
            path.node.loc,
            {},
            code
          );
          
          // Update global context
          global.currentClassContext = className;
          
          // Track for nested methods
          scopeTracker.currentClass = classNode.id;
          
          // Handle class extensions
          if (path.node.superClass) {
            const superClassName = path.node.superClass.name;
            if (scopeTracker.importedModules.has(superClassName)) {
              createRelationship(
                classNode.id, 
                scopeTracker.importedModules.get(superClassName),
                REL_TYPES.EXTENDS
              );
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
            { 
              isAsync: path.node.async, 
              isGenerator: path.node.generator,
              parentClass: global.currentClassContext
            },
            code
          );
          
          // Update method context
          global.currentMethodContext = methodName;
          global.currentScopeContext = `${global.currentClassContext}.${methodName}`;
          
          createRelationship(
            scopeTracker.currentClass, 
            methodNode.id, 
            REL_TYPES.CONTAINS
          );
          
          // Track current method for variable scope
          scopeTracker.currentMethod = methodNode.id;
        },
        
        FunctionDeclaration(path) {
          const funcName = path.node.id.name;
          const funcNode = createEntityNode(
            NODE_TYPES.FUNCTION, 
            funcName, 
            filePath, 
            path.node.loc,
            { 
              isAsync: path.node.async, 
              isGenerator: path.node.generator
            },
            code
          );
          
          // Update context
          global.currentMethodContext = null;
          global.currentScopeContext = funcName;
          
          // Add to scope
          scopeTracker.declaredVariables.set(funcName, funcNode.id);
        },
        
        VariableDeclarator(path) {
          const varName = path.node.id.name;
          const varNode = createEntityNode(
            NODE_TYPES.VARIABLE, 
            varName, 
            filePath, 
            path.node.loc,
            {},
            code
          );
          
          // Track in current scope
          scopeTracker.declaredVariables.set(varName, varNode.id);
          
          // If variable is initialized, create reference relationship
          if (path.node.init) {
            if (path.node.init.type === 'CallExpression') {
              const calleeName = path.node.init.callee.name;
              if (scopeTracker.declaredVariables.has(calleeName)) {
                createRelationship(
                  varNode.id,
                  scopeTracker.declaredVariables.get(calleeName),
                  REL_TYPES.CALLS
                );
              }
            } else if (path.node.init.type === 'Identifier') {
              const initName = path.node.init.name;
              if (scopeTracker.declaredVariables.has(initName)) {
                createRelationship(
                  varNode.id,
                  scopeTracker.declaredVariables.get(initName),
                  REL_TYPES.REFERENCES
                );
              }
            }
          }
          
          // Connect to parent scope
          if (scopeTracker.currentMethod) {
            createRelationship(
              scopeTracker.currentMethod, 
              varNode.id, 
              REL_TYPES.DECLARES
            );
          } else if (scopeTracker.currentClass) {
            createRelationship(
              scopeTracker.currentClass, 
              varNode.id, 
              REL_TYPES.DECLARES
            );
          }
        },
        
        // Track scope changes
        BlockStatement: {
          enter(path) {
            // Save parent scope
            path.node._parentScope = global.currentScopeContext;
          },
          exit(path) {
            // Restore parent scope
            global.currentScopeContext = path.node._parentScope;
          }
        },
        
        MemberExpression(path) {
          // Track object property references
          if (path.node.object.type === 'ThisExpression' && scopeTracker.currentClass) {
            // Reference to class property
            if (path.node.property.type === 'Identifier') {
              const propertyName = path.node.property.name;
              // We could create nodes for these, but for now just track the reference
            }
          }
        },
        
        // Handle require calls
        CallExpression(path) {
          // Track function calls
          if (path.node.callee.type === 'Identifier') {
            const calleeName = path.node.callee.name;
            
            // Handle require statements
            if (calleeName === 'require' && 
                path.node.arguments.length > 0 && 
                path.node.arguments[0].type === 'StringLiteral') {
              
              const requirePath = path.node.arguments[0].value;
              
              if (config.trackExternalLibraries && isExternalLibrary(requirePath)) {
                // Handle external library require
                const libraryNode = getOrCreateExternalLibraryNode(requirePath);
                createRelationship(fileNode.id, libraryNode.id, REL_TYPES.IMPORTS);
                
                // If this is part of a variable declaration, track the variable
                const parentPath = path.parentPath;
                if (parentPath && parentPath.node.type === 'VariableDeclarator') {
                  const varName = parentPath.node.id.name;
                  scopeTracker.importedModules.set(varName, libraryNode.id);
                }
              }
            }
            
            // Regular function calls
            if (scopeTracker.declaredVariables.has(calleeName)) {
              // Create a relationship from current scope to the called function
              let sourceId;
              if (scopeTracker.currentMethod) {
                sourceId = scopeTracker.currentMethod;
              } else if (scopeTracker.currentClass) {
                sourceId = scopeTracker.currentClass;
              } else {
                sourceId = fileNode.id;
              }
              
              createRelationship(
                sourceId,
                scopeTracker.declaredVariables.get(calleeName),
                REL_TYPES.CALLS
              );
            }
          }
        }
      });
      
    } catch (error) {
      console.error(`Error analyzing file ${filePath}:`, error.message);
    }
  }
  
  // Scan directory recursively and analyze JS files
  function scanDirectory(dirPath) {
    // Skip node_modules if configured to do so
    if (config.ignoreNodeModules && dirPath.includes('node_modules')) {
      return;
    }
  
    console.log(`Scanning directory: ${dirPath}`);
    const items = fs.readdirSync(dirPath);
    
    for (const item of items) {
      const itemPath = path.join(dirPath, item);
      const stats = fs.statSync(itemPath);
      
      if (stats.isDirectory()) {
        // Skip node_modules if configured
        if (config.ignoreNodeModules && item === 'node_modules') {
          continue;
        }
        scanDirectory(itemPath);
      } else if (stats.isFile() && /\.(js|jsx|ts|tsx)$/.test(itemPath)) {
        analyzeFile(itemPath);
      }
    }
  }
  
  // Main function to start scanning
  function scanJSService(rootPath, customConfig = {}) {
    // Apply custom configuration
    config = { ...defaultConfig, ...customConfig };
    console.log(`Starting scan of JS service at: ${rootPath}`);
    console.log(`Configuration: ${JSON.stringify(config, null, 2)}`);
    
    // Clear previous data
    graph.nodes = [];
    graph.relationships = [];
    nodeRegistry.folderNodes.clear();
    nodeRegistry.fileNodes.clear();
    nodeRegistry.entityNodes.clear();
    externalLibraries.clear();
    
    // Clear content registries
    contentRegistry.folderContents.clear();
    contentRegistry.fileContents.clear();
    contentRegistry.classScopes.clear();
    contentRegistry.methodScopes.clear();
    
    // Try to find and parse package.json to identify project dependencies
    try {
      const packageJsonPath = path.join(rootPath, 'package.json');
      if (fs.existsSync(packageJsonPath)) {
        const packageJson = JSON.parse(fs.readFileSync(packageJsonPath, 'utf-8'));
        
        // Pre-register all dependencies as external libraries
        const dependencies = {
          ...packageJson.dependencies || {},
          ...packageJson.devDependencies || {}
        };
        
        for (const [libName, version] of Object.entries(dependencies)) {
          const node = createNode(NODE_TYPES.EXTERNAL_LIBRARY, libName, null, {
            isExternal: true,
            version: version,
            fromPackageJson: true
          });
          externalLibraries.set(libName, node);
        }
        
        console.log(`Found ${externalLibraries.size} dependencies in package.json`);
      }
    } catch (error) {
      console.error(`Error parsing package.json:`, error.message);
    }
    
    // Initialize root folder
    getOrCreateFolderNode(rootPath);
    
    // Scan the directory
    scanDirectory(rootPath);
    
    return graph;
  }
  
  // Function to get content lists for an entity
  function getContentListsByName(name, type) {
    let registry;
    switch (type) {
      case NODE_TYPES.FOLDER:
        registry = contentRegistry.folderContents;
        break;
      case NODE_TYPES.FILE:
        registry = contentRegistry.fileContents;
        break;
      case NODE_TYPES.CLASS:
        registry = contentRegistry.classScopes;
        break;
      case NODE_TYPES.METHOD:
        registry = contentRegistry.methodScopes;
        break;
      default:
        return null;
    }
    
    return registry.has(name) ? registry.get(name) : [];
  }
  
// Export Neo4j compatible format with MATCH by node names
function exportToNeo4j() {
    // Filter out any invalid relationships
    const validRelationships = graph.relationships.filter(rel => {
      if (!rel.source || !rel.target || isPlaceholder(rel.source) || isPlaceholder(rel.target)) {
        return false;
      }
      const sourceExists = graph.nodes.some(node => node.id === rel.source);
      const targetExists = graph.nodes.some(node => node.id === rel.target);
      return sourceExists && targetExists;
    });
  
    // Create constraints and indexes for better performance
    const constraints = [
      'CREATE CONSTRAINT IF NOT EXISTS FOR (n:Folder) REQUIRE n.id IS UNIQUE',
      'CREATE CONSTRAINT IF NOT EXISTS FOR (n:File) REQUIRE n.id IS UNIQUE',
      'CREATE CONSTRAINT IF NOT EXISTS FOR (n:Class) REQUIRE n.id IS UNIQUE',
      'CREATE CONSTRAINT IF NOT EXISTS FOR (n:Method) REQUIRE n.id IS UNIQUE',
      'CREATE CONSTRAINT IF NOT EXISTS FOR (n:Function) REQUIRE n.id IS UNIQUE',
      'CREATE CONSTRAINT IF NOT EXISTS FOR (n:Variable) REQUIRE n.id IS UNIQUE',
      'CREATE CONSTRAINT IF NOT EXISTS FOR (n:Import) REQUIRE n.id IS UNIQUE',
      'CREATE CONSTRAINT IF NOT EXISTS FOR (n:ExternalLibrary) REQUIRE n.id IS UNIQUE',
      'CREATE INDEX IF NOT EXISTS FOR (n:Folder) ON (n.name)',
      'CREATE INDEX IF NOT EXISTS FOR (n:File) ON (n.name)',
    ].join(';\n');
  
    // Create Cypher queries for nodes using MERGE to avoid duplicates
    const nodesQuery = graph.nodes.map(node => {
      // Clone properties and remove the internal id property from the props
      const props = { ...node };
      delete props.id;
      
      // Add content lists if applicable
      if (config.captureContent) {
        if ([NODE_TYPES.FOLDER, NODE_TYPES.FILE, NODE_TYPES.CLASS, NODE_TYPES.METHOD].includes(node.type)) {
          const contentLists = getContentListsByName(node.name, node.type);
          if (contentLists && contentLists.length > 0) {
            props.contentLists = contentLists;
          }
        }
      }
      
      // Build property string, converting complex objects to JSON strings
      const propEntries = Object.entries(props)
        .filter(([_, v]) => v !== null && v !== undefined)
        .map(([k, v]) => `${k}: ${JSON.stringify(v)}`)
        .join(', ');
      
      // Use MERGE to prevent duplicates, with the id as the unique key
      return `MERGE (n:${node.type} {id: ${JSON.stringify(node.id)}})  ON CREATE SET n.name = ${JSON.stringify(node.name)}, ${propEntries}`;
    }).join(';\n');
  
    // Create Cypher queries for relationships using node IDs for matching
    const relsQuery = validRelationships.map(rel => {
      // Look up source and target nodes in the graph by their generated id
      const sourceNode = graph.nodes.find(node => node.id === rel.source);
      const targetNode = graph.nodes.find(node => node.id === rel.target);
      
      // Skip if source or target is missing or if it's a self-reference
      if (!sourceNode || !targetNode || sourceNode.id === targetNode.id) {
        console.log(`Skipping invalid relationship: ${rel.id} (${rel.source} -> ${rel.target})`);
        return '';
      }
      
      // Check for unique source/target pair to avoid duplicate relationships
      return `MATCH (a:${sourceNode.type} {id: ${JSON.stringify(sourceNode.id)}}), (b:${targetNode.type} {id: ${JSON.stringify(targetNode.id)}})  WHERE a <> b // Ensure we're not creating self-relationships  MERGE (a)-[r:${rel.type}]->(b)  ON CREATE SET r.id = ${JSON.stringify(rel.id)}`;
    }).filter(Boolean).join(';\n');
  
    // Summary statistics to add as a comment
    const stats = `// Export summary:
  // - ${graph.nodes.length} nodes
  // - ${validRelationships.length} relationships
  // - ${new Set(graph.nodes.map(n => n.type)).size} node types
  // - ${new Set(validRelationships.map(r => r.type)).size} relationship types
  // Exported on: ${new Date().toISOString()}`;
  
    // Wrap everything in a transaction block
    const transactionStart = 'BEGIN';
    const transactionEnd = 'COMMIT';
    
    return `${stats}
  
  ${transactionStart};
  
  // Create constraints and indexes
  ${constraints};
  
  // Create nodes
  ${nodesQuery};
  
  // Create relationships
  ${relsQuery};
  
  ${transactionEnd};`;
  }

  // Export JSON format with enhanced metadata
  function exportToJSON(filePath) {
    // Filter out any invalid relationships
    const validRelationships = graph.relationships.filter(rel => {
      // Skip if source or target is null, undefined or a placeholder
      if (!rel.source || !rel.target || isPlaceholder(rel.source) || isPlaceholder(rel.target)) {
        return false;
      }
      
      // Skip if source or target node doesn't exist in the graph
      const sourceExists = graph.nodes.some(node => node.id === rel.source);
      const targetExists = graph.nodes.some(node => node.id === rel.target);
      
      return sourceExists && targetExists;
    });
    
    // Enhance nodes with content lists
    const enhancedNodes = graph.nodes.map(node => {
      const enhancedNode = {...node};
      
      // Add content lists for applicable node types
      if (config.captureContent) {
        if ([NODE_TYPES.FOLDER, NODE_TYPES.FILE, NODE_TYPES.CLASS, NODE_TYPES.METHOD].includes(node.type)) {
          const contentLists = getContentListsByName(node.name, node.type);
          if (contentLists && contentLists.length > 0) {
            enhancedNode.contentLists = contentLists;
          }
        }
      }
      
      return enhancedNode;
    });
    
    const cleanedGraph = {
      nodes: enhancedNodes,
      relationships: validRelationships,
      contentRegistrySummary: {
        folders: contentRegistry.folderContents.size,
        files: contentRegistry.fileContents.size,
        classes: contentRegistry.classScopes.size,
        methods: contentRegistry.methodScopes.size
      }
    };
    
    fs.writeFileSync(filePath, JSON.stringify(cleanedGraph, null, 2));
    console.log(`Graph exported to ${filePath}`);
  }


  module.exports = {
    scanJSService,
    exportToJSON,
    exportToNeo4j,
    NODE_TYPES,
    REL_TYPES,
    defaultConfig
  };
  
    // Example usage:
  // const jsScanner = require('./js-scanner');
  // const graph = jsScanner.scanJSService('/path/to/js/service');
  // jsScanner.exportToJSON('./graph-data.json');
