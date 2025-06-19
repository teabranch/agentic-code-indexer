// Constants
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

const REL_TYPES = {
  CONTAINS: 'CONTAINS',
  IMPORTS: 'IMPORTS',
  CALLS: 'CALLS',
  EXTENDS: 'EXTENDS',
  IMPLEMENTS: 'IMPLEMENTS',
  REFERENCES: 'REFERENCES',
  DECLARES: 'DECLARES'
};

const defaultConfig = {
  includeVariables: false,
  includeImports: true,
  includeFolders: true,
  includeFiles: true,
  includeClasses: true,
  includeMethods: true,
  includeFunctions: true,
  ignoreNodeModules: true,
  trackExternalLibraries: false,
  captureContent: true
};

// Registries
const nodeRegistry = {
  folderNodes: new Map(),
  fileNodes: new Map(),
  entityNodes: new Map()
};

const contentRegistry = {
  folderContents: new Map(),
  fileContents: new Map(),
  classScopes: new Map(),
  methodScopes: new Map()
};

// External libraries container
const externalLibraries = new Map();

module.exports = {
  NODE_TYPES,
  REL_TYPES,
  defaultConfig,
  nodeRegistry,
  contentRegistry,
  externalLibraries
};
