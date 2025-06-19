const { scanJSService } = require('./scanner');
const { exportToJSON, exportToNeo4j } = require('./exporters');
const { defaultConfig, NODE_TYPES } = require('./constants');

// Specify the root directory of your JS service
const serviceRoot = process.argv[2] || './src';

// Parse configuration options from command line arguments
const configOptions = {};
process.argv.slice(3).forEach(arg => {
  if (arg.startsWith('--')) {
    const [key, value] = arg.substring(2).split('=');
    if (key in defaultConfig) {
      configOptions[key] = value === 'true';
    }
  }
});

// Scan the service and build the graph
console.time('Scan completed in');
const graph = scanJSService(serviceRoot, configOptions);
console.timeEnd('Scan completed in');

// Log some stats
console.log(`\nGraph Statistics:`);
console.log(`- Nodes: ${graph.nodes.length}`);
console.log(`- Relationships: ${graph.relationships.length}`);
console.log(`- Node types: ${new Set(graph.nodes.map(n => n.type)).size}`);
console.log(`- Relationship types: ${new Set(graph.relationships.map(r => r.type)).size}`);

// Count by node type with ID examples
const nodeTypeCount = graph.nodes.reduce((counts, node) => {
  if (!counts[node.type]) {
    counts[node.type] = {
      count: 0,
      examples: []
    };
  }
  
  counts[node.type].count++;
  
  // Store some example IDs for debugging
  if (counts[node.type].examples.length < 3) {
    counts[node.type].examples.push(node.id);
  }
  
  return counts;
}, {});

console.log('\nNode count by type:');
Object.entries(nodeTypeCount).forEach(([type, data]) => {
  console.log(`- ${type}: ${data.count}`);
  console.log(`  Example IDs: ${data.examples.join(', ')}`);
});

// Count external libraries
const externalLibraries = graph.nodes.filter(node => node.type === NODE_TYPES.EXTERNAL_LIBRARY);
console.log(`\nExternal libraries: ${externalLibraries.length}`);
if (externalLibraries.length > 0) {
  console.log('Top external libraries by number of imports:');
  
  // Count imports per library
  const libImportCounts = {};
  graph.relationships
    .filter(rel => rel.type === 'IMPORTS')
    .forEach(rel => {
      const targetNode = graph.nodes.find(n => n.id === rel.target);
      if (targetNode && targetNode.type === NODE_TYPES.EXTERNAL_LIBRARY) {
        libImportCounts[targetNode.name] = (libImportCounts[targetNode.name] || 0) + 1;
      }
    });
  
  // Display top 10 most imported libraries
  Object.entries(libImportCounts)
    .sort((a, b) => b[1] - a[1])
    .slice(0, 10)
    .forEach(([libName, count]) => {
      console.log(`- ${libName}: ${count} imports`);
    });
}

// Analyze relationship consistency
console.log('\nRelationship validation:');
const badRelationships = graph.relationships.filter(rel => {
  const sourceExists = graph.nodes.some(node => node.id === rel.source);
  const targetExists = graph.nodes.some(node => node.id === rel.target);
  return !sourceExists || !targetExists;
});

console.log(`- Total relationships: ${graph.relationships.length}`);
console.log(`- Valid relationships: ${graph.relationships.length - badRelationships.length}`);
console.log(`- Invalid relationships: ${badRelationships.length}`);

if (badRelationships.length > 0) {
  console.log('\nSample of invalid relationships:');
  badRelationships.slice(0, 3).forEach(rel => {
    console.log(`- ID: ${rel.id}`);
    console.log(`  Source: ${rel.source} (${graph.nodes.some(n => n.id === rel.source) ? 'exists' : 'missing'})`);
    console.log(`  Target: ${rel.target} (${graph.nodes.some(n => n.id === rel.target) ? 'exists' : 'missing'})`);
    console.log(`  Type: ${rel.type}`);
  });
}

// Export the graph to JSON
const outputFile = './graph-data.json';
exportToJSON(graph, outputFile);
console.log(`\nGraph data exported to ${outputFile}`);

// Generate Neo4j Cypher statements (optional)
const cypherFile = './neo4j-import.cypher';
const cypher = exportToNeo4j(graph, defaultConfig);
require('fs').writeFileSync(cypherFile, cypher);
console.log(`Neo4j Cypher statements written to ${cypherFile}`);