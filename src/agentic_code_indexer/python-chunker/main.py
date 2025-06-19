#!/usr/bin/env python3
"""
Python Code Indexer - Main Entry Point
Analyzes Python code and generates Neo4j Cypher import statements
"""
import sys
import os
import argparse
import time
from scanner import scan_python_service
from exporters import export_to_json, export_to_neo4j
from constants import DEFAULT_CONFIG, NODE_TYPES

def parse_arguments():
    parser = argparse.ArgumentParser(description='Analyze Python code and generate Neo4j import')
    parser.add_argument('root_path', nargs='?', default='./src', 
                       help='Root directory of your Python service (default: ./src)')
    parser.add_argument('--include-variables', action='store_true', default=False,
                       help='Include variable nodes in the graph')
    parser.add_argument('--include-imports', action='store_true', default=True,
                       help='Include import nodes in the graph')
    parser.add_argument('--include-folders', action='store_true', default=True,
                       help='Include folder nodes in the graph')
    parser.add_argument('--include-files', action='store_true', default=True,
                       help='Include file nodes in the graph')
    parser.add_argument('--include-classes', action='store_true', default=True,
                       help='Include class nodes in the graph')
    parser.add_argument('--include-methods', action='store_true', default=True,
                       help='Include method nodes in the graph')
    parser.add_argument('--include-functions', action='store_true', default=True,
                       help='Include function nodes in the graph')
    parser.add_argument('--ignore-venv', action='store_true', default=True,
                       help='Ignore virtual environment directories')
    parser.add_argument('--track-external-libraries', action='store_true', default=False,
                       help='Track external library imports')
    parser.add_argument('--capture-content', action='store_true', default=True,
                       help='Capture code content for nodes')
    parser.add_argument('--output-json', default='./graph-data.json',
                       help='Output JSON file path')
    parser.add_argument('--output-cypher', default='./neo4j-import.cypher',
                       help='Output Cypher file path')
    
    return parser.parse_args()

def main():
    args = parse_arguments()
    
    # Build config from arguments
    config = {
        'include_variables': args.include_variables,
        'include_imports': args.include_imports,
        'include_folders': args.include_folders,
        'include_files': args.include_files,
        'include_classes': args.include_classes,
        'include_methods': args.include_methods,
        'include_functions': args.include_functions,
        'ignore_venv': args.ignore_venv,
        'track_external_libraries': args.track_external_libraries,
        'capture_content': args.capture_content
    }
    
    print(f"Starting scan of Python service at: {args.root_path}")
    print(f"Configuration: {config}")
    
    # Scan the service and build the graph
    start_time = time.time()
    graph = scan_python_service(args.root_path, config)
    end_time = time.time()
    
    print(f"Scan completed in {end_time - start_time:.2f} seconds")
    
    # Log some stats
    print(f"\nGraph Statistics:")
    print(f"- Nodes: {len(graph['nodes'])}")
    print(f"- Relationships: {len(graph['relationships'])}")
    print(f"- Node types: {len(set(node['type'] for node in graph['nodes']))}")
    print(f"- Relationship types: {len(set(rel['type'] for rel in graph['relationships']))}")
    
    # Count by node type with ID examples
    node_type_count = {}
    for node in graph['nodes']:
        node_type = node['type']
        if node_type not in node_type_count:
            node_type_count[node_type] = {'count': 0, 'examples': []}
        
        node_type_count[node_type]['count'] += 1
        
        # Store some example IDs for debugging
        if len(node_type_count[node_type]['examples']) < 3:
            node_type_count[node_type]['examples'].append(node['id'])
    
    print('\nNode count by type:')
    for node_type, data in node_type_count.items():
        print(f"- {node_type}: {data['count']}")
        print(f"  Example IDs: {', '.join(data['examples'])}")
    
    # Count external libraries
    external_libraries = [node for node in graph['nodes'] if node['type'] == NODE_TYPES['EXTERNAL_LIBRARY']]
    print(f"\nExternal libraries: {len(external_libraries)}")
    
    if external_libraries:
        print('Top external libraries by number of imports:')
        
        # Count imports per library
        lib_import_counts = {}
        for rel in graph['relationships']:
            if rel['type'] == 'IMPORTS':
                target_node = next((n for n in graph['nodes'] if n['id'] == rel['target']), None)
                if target_node and target_node['type'] == NODE_TYPES['EXTERNAL_LIBRARY']:
                    lib_name = target_node['name']
                    lib_import_counts[lib_name] = lib_import_counts.get(lib_name, 0) + 1
        
        # Display top 10 most imported libraries
        sorted_libs = sorted(lib_import_counts.items(), key=lambda x: x[1], reverse=True)[:10]
        for lib_name, count in sorted_libs:
            print(f"- {lib_name}: {count} imports")
    
    # Analyze relationship consistency
    print('\nRelationship validation:')
    node_ids = set(node['id'] for node in graph['nodes'])
    bad_relationships = []
    
    for rel in graph['relationships']:
        source_exists = rel['source'] in node_ids
        target_exists = rel['target'] in node_ids
        if not source_exists or not target_exists:
            bad_relationships.append(rel)
    
    print(f"- Total relationships: {len(graph['relationships'])}")
    print(f"- Valid relationships: {len(graph['relationships']) - len(bad_relationships)}")
    print(f"- Invalid relationships: {len(bad_relationships)}")
    
    if bad_relationships:
        print('\nSample of invalid relationships:')
        for rel in bad_relationships[:3]:
            print(f"- ID: {rel['id']}")
            print(f"  Source: {rel['source']} ({'exists' if rel['source'] in node_ids else 'missing'})")
            print(f"  Target: {rel['target']} ({'exists' if rel['target'] in node_ids else 'missing'})")
            print(f"  Type: {rel['type']}")
    
    # Export the graph to JSON
    export_to_json(graph, args.output_json)
    print(f"\nGraph data exported to {args.output_json}")
    
    # Generate Neo4j Cypher statements
    cypher = export_to_neo4j(graph, config)
    with open(args.output_cypher, 'w', encoding='utf-8') as f:
        f.write(cypher)
    print(f"Neo4j Cypher statements written to {args.output_cypher}")

if __name__ == '__main__':
    main() 