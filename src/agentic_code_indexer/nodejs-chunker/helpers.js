const fs = require('fs');
const path = require('path');
const parser = require('@babel/parser');
const traverse = require('@babel/traverse').default;
const { v4: uuidv4 } = require('uuid');
const {
  NODE_TYPES,
  REL_TYPES,
  defaultConfig,
  nodeRegistry,
  contentRegistry,
  externalLibraries
} = require('./constants');

// Global context for AST traversal
const globalContext = {
  currentClassContext: null,
  currentMethodContext: null,
  currentScopeContext: null,
  currentClassNode: null,
  currentMethodNode: null
};

// Helpers region
function isPlaceholder(id) {
  return typeof id === 'string' && id.startsWith('placeholder_');
}

function generateMeaningfulId(type, name, filePath = null, location = null) {
  const cleanName = name.replace(/[^a-zA-Z0-9_]/g, '_').substring(0, 40);
  let id = `${type.toLowerCase()}-${cleanName}`;

  if (type === NODE_TYPES.FOLDER && filePath) {
    const folderName = path.basename(filePath);
    const normalizedPath = path.normalize(filePath).replace(/\\/g, '/');
    id = `folder-${folderName.replace(/[^a-zA-Z0-9_]/g, '_')}-${Buffer.from(normalizedPath).toString('base64').substring(0, 8)}`;
  } else if (type === NODE_TYPES.FILE && filePath) {
    const filename = path.basename(filePath);
    const normalizedPath = path.normalize(filePath).replace(/\\/g, '/');
    id = `file-${filename.replace(/[^a-zA-Z0-9_.]/g, '_')}-${Buffer.from(normalizedPath).toString('base64').substring(0, 8)}`;
  } else if (type === NODE_TYPES.CLASS && filePath) {
    const filename = path.basename(filePath).replace(/\.[^/.]+$/, "");
    id = `class-${cleanName}-${filename.replace(/[^a-zA-Z0-9_]/g, '_')}`;
    if (location) { id += `-L${location.start.line}`; }
  } else if (type === NODE_TYPES.METHOD && filePath) {
    const filename = path.basename(filePath).replace(/\.[^/.]+$/, "");
    const classContext = globalContext.currentClassContext || '';
    id = `method-${cleanName}-${classContext}-${filename.replace(/[^a-zA-Z0-9_]/g, '_')}`;
    if (location) { id += `-L${location.start.line}`; }
  } else if (type === NODE_TYPES.FUNCTION && filePath) {
    const filename = path.basename(filePath).replace(/\.[^/.]+$/, "");
    id = `function-${cleanName}-${filename.replace(/[^a-zA-Z0-9_]/g, '_')}`;
    if (location) { id += `-L${location.start.line}`; }
  } else if (type === NODE_TYPES.VARIABLE && filePath) {
    const filename = path.basename(filePath).replace(/\.[^/.]+$/, "");
    const scopeContext = globalContext.currentScopeContext || '';
    id = `variable-${cleanName}-${scopeContext}-${filename.replace(/[^a-zA-Z0-9_]/g, '_')}`;
    if (location) { id += `-L${location.start.line}`; }
  } else if (type === NODE_TYPES.EXTERNAL_LIBRARY) {
    const version = globalContext.packageVersions && globalContext.packageVersions[name]
      ? `-${globalContext.packageVersions[name].replace(/[^a-zA-Z0-9_.]/g, '_')}` : '';
    id = `lib-${cleanName}${version}`;
  }

  return id;
}

function createNode(type, name, filePath = null, metadata = {}) {
  const location = metadata.location || null;
  const id = generateMeaningfulId(type, name, filePath, location);
  const node = { id, type, name, filePath, ...metadata };
 //externalLibraries.set(baseLibName, node);

  // Assuming graph is managed externally (set in scanner.js)
  return node;
}

function createRelationship(sourceId, targetId, type, metadata = {}) {
  return {
    id: `${sourceId}-${type}-${targetId}`,
    source: sourceId,
    target: targetId,
    type,
    ...metadata
  };
}

function registerContent(type, name, content, config) {
  if (!config.captureContent) return;
  let registry;
  switch (type) {
    case NODE_TYPES.FOLDER: registry = contentRegistry.folderContents; break;
    case NODE_TYPES.FILE: registry = contentRegistry.fileContents; break;
    case NODE_TYPES.CLASS: registry = contentRegistry.classScopes; break;
    case NODE_TYPES.METHOD: registry = contentRegistry.methodScopes; break;
    default: return;
  }
  if (registry.has(name)) {
    registry.get(name).push(content);
  } else {
    registry.set(name, [content]);
  }
}

function extractSourceCode(sourceCode, loc) {
  if (!sourceCode || !loc) return '';
  try {
    const lines = sourceCode.split('\n');
    const startLine = loc.start.line - 1;
    const endLine = loc.end.line - 1;
    if (startLine === endLine) {
      return lines[startLine].substring(loc.start.column, loc.end.column);
    }
    const codeLines = [];
    codeLines.push(lines[startLine].substring(loc.start.column));
    for (let i = startLine + 1; i < endLine; i++) { codeLines.push(lines[i]); }
    codeLines.push(lines[endLine].substring(0, loc.end.column));
    return codeLines.join('\n');
  } catch (error) {
    console.error('Error extracting source code:', error.message);
    return '';
  }
}

function getOrCreateFolderNode(folderPath, graph, config) {
  if (nodeRegistry.folderNodes.has(folderPath)) return nodeRegistry.folderNodes.get(folderPath);
  const folderName = path.basename(folderPath);
  const node = createNode(NODE_TYPES.FOLDER, folderName, folderPath);
  graph.nodes.push(node);
  nodeRegistry.folderNodes.set(folderPath, node);
  const parentPath = path.dirname(folderPath);
  if (parentPath !== folderPath) {
    const parentNode = getOrCreateFolderNode(parentPath, graph, config);
    graph.relationships.push(createRelationship(parentNode.id, node.id, REL_TYPES.CONTAINS));
  }
  if (config.captureContent) {
    try {
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
      node.contentCount = folderContent.length;
      node.contentSummary = `${folderContent.filter(i => i.type === 'folder').length} folders, ${folderContent.filter(i => i.type === 'file').length} files`;
      registerContent(NODE_TYPES.FOLDER, folderName, folderContent, config);
    } catch (error) {
      console.error(`Error reading folder ${folderPath}:`, error.message);
    }
  }
  return node;
}

function getOrCreateFileNode(filePath, graph, config) {
  if (nodeRegistry.fileNodes.has(filePath)) return nodeRegistry.fileNodes.get(filePath);
  const fileName = path.basename(filePath);
  const node = createNode(NODE_TYPES.FILE, fileName, filePath);
  graph.nodes.push(node);
  nodeRegistry.fileNodes.set(filePath, node);
  const folderPath = path.dirname(filePath);
  const folderNode = getOrCreateFolderNode(folderPath, graph, config);
  graph.relationships.push(createRelationship(folderNode.id, node.id, REL_TYPES.CONTAINS));
  if (config.captureContent) {
    try {
      const fileContent = fs.readFileSync(filePath, 'utf-8');
      node.fileSize = fileContent.length;
      node.lineCount = fileContent.split('\n').length;
      registerContent(NODE_TYPES.FILE, fileName, fileContent, config);
    } catch (error) {
      console.error(`Error reading file ${filePath}:`, error.message);
    }
  }
  return node;
}

function createEntityNode(type, name, filePath, loc, metadata = {}, sourceCode, graph, config) {
  if (
    (type === NODE_TYPES.VARIABLE && !config.includeVariables) ||
    (type === NODE_TYPES.IMPORT && !config.includeImports) ||
    (type === NODE_TYPES.CLASS && !config.includeClasses) ||
    (type === NODE_TYPES.METHOD && !config.includeMethods) ||
    (type === NODE_TYPES.FUNCTION && !config.includeFunctions)
  ) {
    return `placeholder_${type}_${name}`;
  }
  const key = `${filePath}:${type}:${name}:${loc.start.line}:${loc.start.column}`;
  if (nodeRegistry.entityNodes.has(key)) return nodeRegistry.entityNodes.get(key);
  if (config.captureContent && sourceCode) {
    const codeContent = extractSourceCode(sourceCode, loc);
    if (codeContent) {
      metadata.codeScope = codeContent;
      if (type === NODE_TYPES.CLASS || type === NODE_TYPES.METHOD) {
        registerContent(type, name, codeContent, config);
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
  graph.nodes.push(node);
  nodeRegistry.entityNodes.set(key, node);
  const fileNode = getOrCreateFileNode(filePath, graph, config);
  graph.relationships.push(createRelationship(fileNode.id, node.id, REL_TYPES.CONTAINS));
  if (type === NODE_TYPES.CLASS) { globalContext.currentClassNode = node.id; }
  else if (type === NODE_TYPES.METHOD) { globalContext.currentMethodNode = node.id; }
  return node;
}

module.exports = {
  isPlaceholder,
  generateMeaningfulId,
  createNode,
  createRelationship,
  registerContent,
  extractSourceCode,
  getOrCreateFolderNode,
  getOrCreateFileNode,
  createEntityNode,
  globalContext
};
