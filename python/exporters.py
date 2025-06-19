"""
Export functions for Python Code Indexer
Handles exporting the graph to JSON and Neo4j Cypher format
"""
import json
import os
from datetime import datetime
from constants import NODE_TYPES, REL_TYPES
from helpers import is_placeholder, content_registry

def export_to_json(graph, file_path):
    """Export the graph to JSON format"""
    print(f"[export_to_json] Exporting relationships: {len(graph.get('relationships', []))}")
    
    # Filter out invalid relationships
    valid_relationships = []
    node_ids = set(node['id'] for node in graph['nodes'])
    
    for rel in graph['relationships']:
        # Skip if source or target is null, undefined or a placeholder
        if not rel.get('source') or not rel.get('target'):
            continue
        if is_placeholder(rel['source']) or is_placeholder(rel['target']):
            continue
        
        # Skip if source or target node doesn't exist in the graph
        if rel['source'] not in node_ids or rel['target'] not in node_ids:
            continue
        
        valid_relationships.append(rel)
    
    # Enhance nodes with content lists
    enhanced_nodes = []
    for node in graph['nodes']:
        enhanced_node = dict(node)
        
        # Add content lists for applicable node types
        if node['type'] in [NODE_TYPES['FOLDER'], NODE_TYPES['FILE'], NODE_TYPES['CLASS'], NODE_TYPES['METHOD']]:
            content_lists = get_content_lists_by_name(node['name'], node['type'])
            if content_lists:
                enhanced_node['content_lists'] = content_lists
        
        enhanced_nodes.append(enhanced_node)
    
    cleaned_graph = {
        'nodes': enhanced_nodes,
        'relationships': valid_relationships,
        'content_registry_summary': {
            'folders': len(content_registry['folder_contents']),
            'files': len(content_registry['file_contents']),
            'classes': len(content_registry['class_scopes']),
            'methods': len(content_registry['method_scopes'])
        }
    }
    
    try:
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(cleaned_graph, f, indent=2, ensure_ascii=False, default=str)
        print(f"[export_to_json] Graph exported to {file_path}")
    except Exception as e:
        print(f"[export_to_json] Error exporting graph: {e}")
        raise

def get_content_lists_by_name(name, node_type):
    """Get content lists for a node by name and type"""
    registry = None
    if node_type == NODE_TYPES['FOLDER']:
        registry = content_registry['folder_contents']
    elif node_type == NODE_TYPES['FILE']:
        registry = content_registry['file_contents']
    elif node_type == NODE_TYPES['CLASS']:
        registry = content_registry['class_scopes']
    elif node_type == NODE_TYPES['METHOD']:
        registry = content_registry['method_scopes']
    else:
        return None
    
    return registry.get(name, [])

def export_to_neo4j(graph, config):
    """Export the graph to Neo4j Cypher format"""
    print('[export_to_neo4j] Starting export')
    print(f'[export_to_neo4j] Entities: {len(graph["nodes"])}')
    
    # Filter out invalid relationships
    valid_relationships = []
    node_ids = set(node['id'] for node in graph['nodes'])
    
    for rel in graph['relationships']:
        if not rel.get('source') or not rel.get('target'):
            continue
        if is_placeholder(rel['source']) or is_placeholder(rel['target']):
            continue
        
        source_exists = rel['source'] in node_ids
        target_exists = rel['target'] in node_ids
        if source_exists and target_exists:
            valid_relationships.append(rel)
    
    print(f'[export_to_neo4j] Valid relationships count: {len(valid_relationships)}')
    
    # Create constraints and indexes
    constraints = [
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
    ]
    constraints_query = ';\n'.join(constraints)
    
    # Create Cypher queries for nodes
    nodes_queries = []
    for node in graph['nodes']:
        props = dict(node)
        del props['id']  # Remove 'id' since it's used in MERGE
        
        # Add content lists if applicable
        if config.get('capture_content'):
            if node['type'] in [NODE_TYPES['FOLDER'], NODE_TYPES['FILE'], NODE_TYPES['CLASS'], NODE_TYPES['METHOD']]:
                content_lists = get_content_lists_by_name(node['name'], node['type'])
                if content_lists:
                    props['content_lists'] = content_lists
        
        # Build property entries
        prop_entries = []
        for k, v in props.items():
            if v is not None:
                if k == 'code_scope' and isinstance(v, str):
                    # Escape the code_scope property explicitly
                    escaped = v.replace('\\', '\\\\').replace('"', '\\"')
                    prop_entries.append(f'n.{k} = {json.dumps(escaped)}')
                elif isinstance(v, dict) and not isinstance(v, list):
                    # Handle nested objects (store as JSON string)
                    prop_entries.append(f'n.{k} = {json.dumps(json.dumps(v))}')
                else:
                    prop_entries.append(f'n.{k} = {json.dumps(v, default=str)}')
        
        prop_string = ', '.join(prop_entries)
        query = f'MERGE (n:{node["type"]} {{id: {json.dumps(node["id"])}}}) ON CREATE SET {prop_string} RETURN n'
        nodes_queries.append(query)
    
    nodes_query = ';\n'.join(nodes_queries)
    
    # Create Cypher queries for relationships
    rels_queries = []
    for rel in valid_relationships:
        source_node = next((n for n in graph['nodes'] if n['id'] == rel['source']), None)
        target_node = next((n for n in graph['nodes'] if n['id'] == rel['target']), None)
        
        if not source_node or not target_node or source_node['id'] == target_node['id']:
            continue
        
        query = (f'MATCH (a:{source_node["type"]} {{id: {json.dumps(source_node["id"])}}}),'
                f' (b:{target_node["type"]} {{id: {json.dumps(target_node["id"])}}}) '
                f'WHERE a <> b MERGE (a)-[r:{rel["type"]}]->(b) '
                f'ON CREATE SET r.id = {json.dumps(rel["id"])} RETURN r')
        rels_queries.append(query)
    
    rels_query = ';\n'.join(rels_queries)
    
    # Summary statistics
    stats = f"""// Export summary:
  // - {len(graph['nodes'])} nodes
  // - {len(valid_relationships)} relationships
  // - {len(set(node['type'] for node in graph['nodes']))} node types
  // - {len(set(rel['type'] for rel in valid_relationships))} relationship types
  // Exported on: {datetime.now().isoformat()}"""
    
    # Combine everything
    transaction = f"{constraints_query};\n{nodes_query};\n{rels_query};"
    
    print('[export_to_neo4j] Export query constructed')
    return f"{stats}\n\n{transaction}" 