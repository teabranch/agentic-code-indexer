const fs = require('fs');
const path = require('path');
const { getOrCreateFolderNode, createNode } = require('./helpers');
const { analyzeFile } = require('./ast');

const {
    NODE_TYPES,
    defaultConfig,
    nodeRegistry,
    contentRegistry,
    externalLibraries
  } = require('./constants');

function scanDirectory(dirPath, graph, config) {
    if (config.ignoreNodeModules && dirPath.includes('node_modules')) return;
    console.log(`Scanning directory: ${dirPath}`);
    const items = fs.readdirSync(dirPath);
    items.forEach(item => {
        const itemPath = path.join(dirPath, item);
        const stats = fs.statSync(itemPath);
        if (stats.isDirectory()) {
            if (config.ignoreNodeModules && item === 'node_modules') return;
            scanDirectory(itemPath, graph, config);
        } else if (stats.isFile() && /\.(js|jsx|ts|tsx)$/.test(itemPath)) {
            analyzeFile(itemPath, graph, config);
        }
    });
}

function scanJSService(rootPath, customConfig = {}) {
    const config = { ...defaultConfig, ...customConfig };
    console.log(`Starting scan of JS service at: ${rootPath}`);
    console.log(`Configuration: ${JSON.stringify(config, null, 2)}`);

    // Graph structure
    const graph = { nodes: [], relationships: [] };

    // Clear existing registries if needed
    // ...existing registry clearing logic using Map.clear()...
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

    // Initialize root folder node
    getOrCreateFolderNode(rootPath, graph, config);

    // Parse package.json for dependencies (optional)
    try {
        const packageJsonPath = path.join(rootPath, 'package.json');
        if (fs.existsSync(packageJsonPath)) {
            const packageJson = JSON.parse(fs.readFileSync(packageJsonPath, 'utf-8'));
            const dependencies = { ...(packageJson.dependencies || {}), ...(packageJson.devDependencies || {}) };
            Object.entries(dependencies).forEach(([libName, version]) => {
                // Create external library node and register it
                const node = createNode(NODE_TYPES.EXTERNAL_LIBRARY, libName, null, {
                    isExternal: true,
                    version: version,
                    fromPackageJson: true
                });
                externalLibraries.set(libName, node);
            });
            console.log(`Found dependencies in package.json`);
        }
    } catch (error) {
        console.error('Error parsing package.json:', error.message);
    }

    // Start scanning
    scanDirectory(rootPath, graph, config);
    return graph;
}

module.exports = { scanJSService };
