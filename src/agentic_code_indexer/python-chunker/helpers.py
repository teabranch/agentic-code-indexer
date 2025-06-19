"""
Helper functions for Python Code Indexer
"""
import os
import base64
import hashlib
from pathlib import Path
from constants import NODE_TYPES, REL_TYPES

# Registries for tracking nodes and content
node_registry = {
    'folder_nodes': {},
    'file_nodes': {},
    'entity_nodes': {}
}

content_registry = {
    'folder_contents': {},
    'file_contents': {},
    'class_scopes': {},
    'method_scopes': {}
}

external_libraries = {}

# Global context for AST traversal
global_context = {
    'current_class_context': None,
    'current_method_context': None,
    'current_scope_context': None,
    'current_class_node': None,
    'current_method_node': None
}

def is_placeholder(node_id):
    """Check if a node ID is a placeholder"""
    return isinstance(node_id, str) and node_id.startswith('placeholder_')

def generate_meaningful_id(node_type, name, file_path=None, location=None):
    """Generate a meaningful ID for a node"""
    # Clean up the name to use in the ID
    clean_name = ''.join(c if c.isalnum() or c == '_' else '_' for c in name)[:40]
    
    # Base format: [type]-[name]
    node_id = f"{node_type.lower()}-{clean_name}"
    
    if node_type == NODE_TYPES['FOLDER'] and file_path:
        folder_name = os.path.basename(file_path)
        normalized_path = os.path.normpath(file_path).replace('\\', '/')
        
        if folder_name in ['.', '..']:
            # Handle current/parent directory references
            path_segments = [p for p in normalized_path.split('/') if p]
            dir_name = path_segments[-1] if path_segments else 'root'
            path_hash = base64.b64encode(normalized_path.encode()).decode()[:8]
            node_id = f"folder-{dir_name.replace('.', '_')}-{path_hash}"
        else:
            # Normal folder - add path hash for uniqueness
            clean_folder = ''.join(c if c.isalnum() or c == '_' else '_' for c in folder_name)
            path_hash = base64.b64encode(normalized_path.encode()).decode()[:8]
            node_id = f"folder-{clean_folder}-{path_hash}"
    
    elif node_type == NODE_TYPES['FILE'] and file_path:
        filename = os.path.basename(file_path)
        normalized_path = os.path.normpath(file_path).replace('\\', '/')
        clean_filename = ''.join(c if c.isalnum() or c in '._' else '_' for c in filename)
        path_hash = base64.b64encode(normalized_path.encode()).decode()[:8]
        node_id = f"file-{clean_filename}-{path_hash}"
    
    elif node_type == NODE_TYPES['CLASS'] and file_path:
        filename = os.path.splitext(os.path.basename(file_path))[0]
        clean_filename = ''.join(c if c.isalnum() or c == '_' else '_' for c in filename)
        node_id = f"class-{clean_name}-{clean_filename}"
        
        if location:
            node_id += f"-L{location.get('lineno', 0)}"
    
    elif node_type == NODE_TYPES['METHOD'] and file_path:
        filename = os.path.splitext(os.path.basename(file_path))[0]
        clean_filename = ''.join(c if c.isalnum() or c == '_' else '_' for c in filename)
        class_context = global_context['current_class_context'] or ''
        clean_class = ''.join(c if c.isalnum() or c == '_' else '_' for c in class_context)
        node_id = f"method-{clean_name}-{clean_class}-{clean_filename}"
        
        if location:
            node_id += f"-L{location.get('lineno', 0)}"
    
    elif node_type == NODE_TYPES['FUNCTION'] and file_path:
        filename = os.path.splitext(os.path.basename(file_path))[0]
        clean_filename = ''.join(c if c.isalnum() or c == '_' else '_' for c in filename)
        node_id = f"function-{clean_name}-{clean_filename}"
        
        if location:
            node_id += f"-L{location.get('lineno', 0)}"
    
    elif node_type == NODE_TYPES['VARIABLE'] and file_path:
        filename = os.path.splitext(os.path.basename(file_path))[0]
        clean_filename = ''.join(c if c.isalnum() or c == '_' else '_' for c in filename)
        scope_context = global_context['current_scope_context'] or ''
        clean_scope = ''.join(c if c.isalnum() or c == '_' else '_' for c in scope_context)
        node_id = f"variable-{clean_name}-{clean_scope}-{clean_filename}"
        
        if location:
            node_id += f"-L{location.get('lineno', 0)}"
    
    elif node_type == NODE_TYPES['EXTERNAL_LIBRARY']:
        node_id = f"lib-{clean_name}"
    
    return node_id

def create_node(node_type, name, file_path=None, metadata=None):
    """Create a node with the given parameters"""
    if metadata is None:
        metadata = {}
    
    location = metadata.get('location')
    node_id = generate_meaningful_id(node_type, name, file_path, location)
    
    node = {
        'id': node_id,
        'type': node_type,
        'name': name,
        'file_path': file_path,
        **metadata
    }
    
    return node

def create_relationship(source_id, target_id, rel_type, metadata=None):
    """Create a relationship between two nodes"""
    if metadata is None:
        metadata = {}
    
    relationship = {
        'id': f"{source_id}-{rel_type}-{target_id}",
        'source': source_id,
        'target': target_id,
        'type': rel_type,
        **metadata
    }
    
    return relationship

def register_content(node_type, name, content, config):
    """Register content for a node if capture_content is enabled"""
    if not config.get('capture_content'):
        return
    
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
        return
    
    if name in registry:
        registry[name].append(content)
    else:
        registry[name] = [content]

def extract_source_code(source_code, location):
    """Extract source code from location information"""
    if not source_code or not location:
        return ''
    
    try:
        lines = source_code.split('\n')
        start_line = location.get('lineno', 1) - 1
        end_line = location.get('end_lineno', start_line + 1) - 1
        
        if start_line == end_line:
            col_offset = location.get('col_offset', 0)
            end_col_offset = location.get('end_col_offset', len(lines[start_line]))
            return lines[start_line][col_offset:end_col_offset]
        else:
            code_lines = []
            # First line from start column to end
            col_offset = location.get('col_offset', 0)
            code_lines.append(lines[start_line][col_offset:])
            
            # Middle lines (if any)
            for i in range(start_line + 1, end_line):
                if i < len(lines):
                    code_lines.append(lines[i])
            
            # Last line from beginning to end column
            if end_line < len(lines):
                end_col_offset = location.get('end_col_offset', len(lines[end_line]))
                code_lines.append(lines[end_line][:end_col_offset])
            
            return '\n'.join(code_lines)
    except Exception as e:
        print(f"Error extracting source code: {e}")
        return ''

def get_or_create_folder_node(folder_path, graph, config):
    """Get or create a folder node"""
    if folder_path in node_registry['folder_nodes']:
        return node_registry['folder_nodes'][folder_path]
    
    folder_name = os.path.basename(folder_path) or folder_path
    node = create_node(NODE_TYPES['FOLDER'], folder_name, folder_path)
    graph['nodes'].append(node)
    node_registry['folder_nodes'][folder_path] = node
    
    # Create relationship with parent folder
    parent_path = os.path.dirname(folder_path)
    if parent_path != folder_path and parent_path:
        parent_node = get_or_create_folder_node(parent_path, graph, config)
        relationship = create_relationship(parent_node['id'], node['id'], REL_TYPES['CONTAINS'])
        graph['relationships'].append(relationship)
    
    # Register folder content if config allows
    if config.get('capture_content'):
        try:
            if os.path.exists(folder_path):
                items = os.listdir(folder_path)
                folder_content = []
                for item in items:
                    item_path = os.path.join(folder_path, item)
                    if os.path.isdir(item_path):
                        folder_content.append({
                            'name': item,
                            'type': 'folder',
                            'size': 0,
                            'last_modified': os.path.getmtime(item_path)
                        })
                    else:
                        folder_content.append({
                            'name': item,
                            'type': 'file',
                            'size': os.path.getsize(item_path),
                            'last_modified': os.path.getmtime(item_path)
                        })
                
                folders = len([f for f in folder_content if f['type'] == 'folder'])
                files = len([f for f in folder_content if f['type'] == 'file'])
                node['content_count'] = len(folder_content)
                node['content_summary'] = f"{folders} folders, {files} files"
                
                register_content(NODE_TYPES['FOLDER'], folder_name, folder_content, config)
        except Exception as e:
            print(f"Error reading folder contents for {folder_path}: {e}")
    
    return node

def get_or_create_file_node(file_path, graph, config):
    """Get or create a file node"""
    if file_path in node_registry['file_nodes']:
        return node_registry['file_nodes'][file_path]
    
    filename = os.path.basename(file_path)
    node = create_node(NODE_TYPES['FILE'], filename, file_path)
    graph['nodes'].append(node)
    node_registry['file_nodes'][file_path] = node
    
    # Create relationship with containing folder
    folder_path = os.path.dirname(file_path)
    folder_node = get_or_create_folder_node(folder_path, graph, config)
    relationship = create_relationship(folder_node['id'], node['id'], REL_TYPES['CONTAINS'])
    graph['relationships'].append(relationship)
    
    # Register file content if config allows
    if config.get('capture_content'):
        try:
            if os.path.exists(file_path):
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    file_content = f.read()
                    node['file_size'] = len(file_content)
                    node['line_count'] = len(file_content.split('\n'))
                    
                    register_content(NODE_TYPES['FILE'], filename, file_content, config)
        except Exception as e:
            print(f"Error reading file content for {file_path}: {e}")
    
    return node

def create_entity_node(node_type, name, file_path, location, metadata, source_code, graph, config):
    """Create an entity node (class, method, function, variable, etc.)"""
    # Check if this type of node should be included based on configuration
    if (
        (node_type == NODE_TYPES['VARIABLE'] and not config.get('include_variables')) or
        (node_type == NODE_TYPES['IMPORT'] and not config.get('include_imports')) or
        (node_type == NODE_TYPES['CLASS'] and not config.get('include_classes')) or
        (node_type == NODE_TYPES['METHOD'] and not config.get('include_methods')) or
        (node_type == NODE_TYPES['FUNCTION'] and not config.get('include_functions'))
    ):
        # Return a placeholder id for tracking in scope but not in actual graph
        return f"placeholder_{node_type}_{name}"
    
    key = f"{file_path}:{node_type}:{name}:{location.get('lineno', 0)}:{location.get('col_offset', 0)}"
    
    if key in node_registry['entity_nodes']:
        return node_registry['entity_nodes'][key]
    
    # Add code scope content if provided
    if config.get('capture_content') and source_code:
        code_content = extract_source_code(source_code, location)
        if code_content:
            metadata['code_scope'] = code_content
            
            # Register content in appropriate registry
            if node_type in [NODE_TYPES['CLASS'], NODE_TYPES['METHOD']]:
                register_content(node_type, name, code_content, config)
    
    node = create_node(node_type, name, file_path, {
        'location': {
            'line': location.get('lineno', 0),
            'column': location.get('col_offset', 0),
            'end_line': location.get('end_lineno', 0),
            'end_column': location.get('end_col_offset', 0)
        },
        **metadata
    })
    
    graph['nodes'].append(node)
    node_registry['entity_nodes'][key] = node
    
    # Create relationship with containing file
    file_node = get_or_create_file_node(file_path, graph, config)
    relationship = create_relationship(file_node['id'], node['id'], REL_TYPES['CONTAINS'])
    graph['relationships'].append(relationship)
    
    # Update global tracking for class and method contexts
    if node_type == NODE_TYPES['CLASS']:
        global_context['current_class_node'] = node['id']
    elif node_type == NODE_TYPES['METHOD']:
        global_context['current_method_node'] = node['id']
    
    return node

def clear_registries():
    """Clear all registries for a fresh start"""
    node_registry['folder_nodes'].clear()
    node_registry['file_nodes'].clear()
    node_registry['entity_nodes'].clear()
    
    content_registry['folder_contents'].clear()
    content_registry['file_contents'].clear()
    content_registry['class_scopes'].clear()
    content_registry['method_scopes'].clear()
    
    external_libraries.clear()
    
    global_context['current_class_context'] = None
    global_context['current_method_context'] = None
    global_context['current_scope_context'] = None
    global_context['current_class_node'] = None
    global_context['current_method_node'] = None 