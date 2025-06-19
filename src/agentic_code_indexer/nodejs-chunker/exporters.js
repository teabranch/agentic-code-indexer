const fs = require('fs');
const { NODE_TYPES, REL_TYPES } = require('./constants');

function exportToNeo4j(graph, config) {

  console.log('[exportToNeo4j] Starting export'); // Added log
  console.log('[exportToNeo4j] Entities:', JSON.stringify(graph.nodes)); // Log entities
  const validRelationships = graph.relationships.filter(rel => {
    console.log(rel);
    if (!rel.source || !rel.target) return false;
    if (typeof rel.source === 'string' && rel.source.startsWith('placeholder_')) return false;
    if (typeof rel.target === 'string' && rel.target.startsWith('placeholder_')) return false;
    const sourceExists = graph.nodes.some(node => node.id === rel.source);
    const targetExists = graph.nodes.some(node => node.id === rel.target);
    return sourceExists && targetExists;
  });
  console.log(`[exportToNeo4j] Valid relationships count: ${validRelationships.length}`); // Added log
  
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
    'CREATE INDEX IF NOT EXISTS FOR (n:File) ON (n.name)'
  ].join(';\n');

const nodesQuery = graph.nodes.map(node => {
    const props = { ...node };
    delete props.id; // Remove 'id' since it's used in MERGE

    if (config.captureContent && [NODE_TYPES.FOLDER, NODE_TYPES.FILE, NODE_TYPES.CLASS, NODE_TYPES.METHOD].includes(node.type)) {
      // Assume content lists are already attached
    }

    // Escape entry code if needed
    const propEntries = Object.entries(props)
      .filter(([, v]) => v !== null && v !== undefined)
      .map(([k, v]) => {
        if (k === 'codeScope' && typeof v === 'string') {
          // Escape the codeScope property explicitly
          const escaped = v.replace(/\\/g, '\\\\').replace(/"/g, '\\"');
          return `n.${k} = ${JSON.stringify(escaped)}`;
        }
        // Handle nested objects (store as JSON string)
        if (typeof v === 'object' && !Array.isArray(v)) {
          return `n.${k} = ${JSON.stringify(JSON.stringify(v))}`;
        }
        return `n.${k} = ${JSON.stringify(v)}`;
      })
      .join(', ');

    return `MERGE (n:${node.type} {id: ${JSON.stringify(node.id)}}) ON CREATE SET ${propEntries} RETURN n`;
}).join(';\n');

  
  const relsQuery = validRelationships.map(rel => {
    const sourceNode = graph.nodes.find(node => node.id === rel.source);
    const targetNode = graph.nodes.find(node => node.id === rel.target);
    if (!sourceNode || !targetNode || sourceNode.id === targetNode.id) return '';
    return `MATCH (a:${sourceNode.type} {id: ${JSON.stringify(sourceNode.id)}}), (b:${targetNode.type} {id: ${JSON.stringify(targetNode.id)}}) WHERE a <> b MERGE (a)-[r:${rel.type}]->(b) ON CREATE SET r.id = ${JSON.stringify(rel.id)} RETURN r`;
  }).filter(Boolean).join(';\n');
  
  const stats = `// Export summary:
  // - ${graph.nodes.length} nodes
  // - ${validRelationships.length} relationships
  // - ${new Set(graph.nodes.map(n => n.type)).size} node types
  // - ${new Set(validRelationships.map(r => r.type)).size} relationship types
  // Exported on: ${new Date().toISOString()}`;
  
  //const transaction = `BEGIN;\n${constraints};\n${nodesQuery};\n${relsQuery};\nCOMMIT;`;
  const transaction = `${constraints};\n${nodesQuery};\n${relsQuery};`;
  console.log('[exportToNeo4j] Export query constructed'); // Added log
  return `${stats}\n\n${transaction}`;
}

function exportToJSON(graph, filePath, config) {
  console.log(`[exportToJSON] Exporting relationships: ${graph.relationships?.length}`); // Existing log
  const validRelationships = graph.relationships.filter(rel => {
    if (!rel.source || !rel.target) return false;
    if (typeof rel.source === 'string' && rel.source.startsWith('placeholder_')) return false;
    if (typeof rel.target === 'string' && rel.target.startsWith('placeholder_')) return false;
    const sourceExists = graph.nodes.some(node => node.id === rel.source);
    const targetExists = graph.nodes.some(node => node.id === rel.target);
    return sourceExists && targetExists;
  });
  
  const enhancedNodes = graph.nodes.map(node => {
    const enhancedNode = { ...node };
    // Attach content lists if needed
    return enhancedNode;
  });
  
  const cleanedGraph = {
    nodes: enhancedNodes,
    relationships: validRelationships,
    contentRegistrySummary: {
      folders: 0, // Can be populated if needed
      files: 0,
      classes: 0,
      methods: 0
    }
  };
  
  try { // Added try/catch for error visibility
    fs.writeFileSync(filePath, JSON.stringify(cleanedGraph, null, 2));
    console.log(`[exportToJSON] Graph exported to ${filePath}`);
  } catch (error) {
    console.error(`[exportToJSON] Error exporting graph: ${error.message}`);
    throw error;
  }
}

module.exports = { exportToNeo4j, exportToJSON };
