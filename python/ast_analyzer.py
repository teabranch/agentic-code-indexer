"""
Python AST Analyzer
Analyzes Python source code using the built-in ast module
"""
import ast
import os
from constants import NODE_TYPES, REL_TYPES, STANDARD_LIBRARY_MODULES
from helpers import (
    create_entity_node, create_relationship, get_or_create_file_node,
    global_context, external_libraries, is_placeholder
)

def is_external_library(module_name):
    """Check if a module is an external library (not standard library or relative import)"""
    if module_name.startswith('.'):
        return False  # Relative import
    
    base_module = module_name.split('.')[0]
    return base_module not in STANDARD_LIBRARY_MODULES

def get_or_create_external_library_node(library_name, graph, config):
    """Get or create an external library node"""
    if library_name in external_libraries:
        return external_libraries[library_name]
    
    # Extract the base library name (e.g., 'requests' from 'requests.auth')
    base_lib_name = library_name.split('.')[0]
    
    # Check if we already have the base library
    if base_lib_name in external_libraries:
        return external_libraries[base_lib_name]
    
    # Create new library node
    from helpers import create_node
    node = create_node(NODE_TYPES['EXTERNAL_LIBRARY'], base_lib_name, None, {
        'is_external': True,
        'original_import': library_name
    })
    
    graph['nodes'].append(node)
    external_libraries[base_lib_name] = node
    return node

class PythonASTVisitor(ast.NodeVisitor):
    """AST visitor for analyzing Python code"""
    
    def __init__(self, file_path, source_code, graph, config):
        self.file_path = file_path
        self.source_code = source_code
        self.graph = graph
        self.config = config
        self.file_node = get_or_create_file_node(file_path, graph, config)
        
        # Scope tracking
        self.scope_tracker = {
            'current_class': None,
            'current_method': None,
            'declared_variables': {},
            'imported_modules': {}
        }
        
        # Reset global context for this file
        global_context['current_class_context'] = None
        global_context['current_method_context'] = None
        global_context['current_scope_context'] = None
        global_context['current_class_node'] = None
        global_context['current_method_node'] = None
    
    def get_location_info(self, node):
        """Extract location information from an AST node"""
        return {
            'lineno': getattr(node, 'lineno', 0),
            'col_offset': getattr(node, 'col_offset', 0),
            'end_lineno': getattr(node, 'end_lineno', 0),
            'end_col_offset': getattr(node, 'end_col_offset', 0)
        }
    
    def visit_Import(self, node):
        """Handle import statements: import module"""
        for alias in node.names:
            import_name = alias.name
            as_name = alias.asname or alias.name
            
            if self.config.get('track_external_libraries') and is_external_library(import_name):
                # Handle external library import
                library_node = get_or_create_external_library_node(import_name, self.graph, self.config)
                relationship = create_relationship(self.file_node['id'], library_node['id'], REL_TYPES['IMPORTS'])
                self.graph['relationships'].append(relationship)
                
                # Track imported module
                self.scope_tracker['imported_modules'][as_name] = library_node['id']
            else:
                # Handle internal/standard library import
                import_node = create_entity_node(
                    NODE_TYPES['IMPORT'],
                    import_name,
                    self.file_path,
                    self.get_location_info(node),
                    {'as_name': as_name},
                    self.source_code,
                    self.graph,
                    self.config
                )
                
                if not is_placeholder(import_node):
                    relationship = create_relationship(self.file_node['id'], import_node['id'], REL_TYPES['IMPORTS'])
                    self.graph['relationships'].append(relationship)
                    
                    # Track imported module
                    self.scope_tracker['imported_modules'][as_name] = import_node['id']
        
        self.generic_visit(node)
    
    def visit_ImportFrom(self, node):
        """Handle from ... import ... statements"""
        module = node.module or ''
        
        for alias in node.names:
            import_name = alias.name
            as_name = alias.asname or alias.name
            full_name = f"{module}.{import_name}" if module else import_name
            
            if self.config.get('track_external_libraries') and is_external_library(module or import_name):
                # Handle external library import
                library_node = get_or_create_external_library_node(module or import_name, self.graph, self.config)
                relationship = create_relationship(self.file_node['id'], library_node['id'], REL_TYPES['IMPORTS'])
                self.graph['relationships'].append(relationship)
                
                # Track imported name
                self.scope_tracker['imported_modules'][as_name] = library_node['id']
            else:
                # Handle internal/standard library import
                import_node = create_entity_node(
                    NODE_TYPES['IMPORT'],
                    full_name,
                    self.file_path,
                    self.get_location_info(node),
                    {'from_module': module, 'import_name': import_name, 'as_name': as_name},
                    self.source_code,
                    self.graph,
                    self.config
                )
                
                if not is_placeholder(import_node):
                    relationship = create_relationship(self.file_node['id'], import_node['id'], REL_TYPES['IMPORTS'])
                    self.graph['relationships'].append(relationship)
                    
                    # Track imported name
                    self.scope_tracker['imported_modules'][as_name] = import_node['id']
        
        self.generic_visit(node)
    
    def visit_ClassDef(self, node):
        """Handle class definitions"""
        class_name = node.name
        class_node = create_entity_node(
            NODE_TYPES['CLASS'],
            class_name,
            self.file_path,
            self.get_location_info(node),
            {
                'is_async': False,
                'decorators': [d.id if isinstance(d, ast.Name) else str(d) for d in node.decorator_list]
            },
            self.source_code,
            self.graph,
            self.config
        )
        
        if not is_placeholder(class_node):
            # Update global context
            global_context['current_class_context'] = class_name
            
            # Track for nested methods
            previous_class = self.scope_tracker['current_class']
            self.scope_tracker['current_class'] = class_node['id']
            
            # Handle class inheritance
            for base in node.bases:
                if isinstance(base, ast.Name):
                    base_name = base.id
                    if base_name in self.scope_tracker['imported_modules']:
                        relationship = create_relationship(
                            class_node['id'],
                            self.scope_tracker['imported_modules'][base_name],
                            REL_TYPES['EXTENDS']
                        )
                        self.graph['relationships'].append(relationship)
            
            # Visit child nodes
            self.generic_visit(node)
            
            # Restore previous context
            self.scope_tracker['current_class'] = previous_class
            global_context['current_class_context'] = None
    
    def visit_FunctionDef(self, node):
        """Handle function definitions"""
        func_name = node.name
        
        # Determine if this is a method or a function
        if self.scope_tracker['current_class']:
            # This is a method
            method_node = create_entity_node(
                NODE_TYPES['METHOD'],
                func_name,
                self.file_path,
                self.get_location_info(node),
                {
                    'is_async': False,
                    'is_generator': any(isinstance(n, ast.Yield) or isinstance(n, ast.YieldFrom) 
                                     for n in ast.walk(node)),
                    'parent_class': global_context['current_class_context'],
                    'decorators': [d.id if isinstance(d, ast.Name) else str(d) for d in node.decorator_list]
                },
                self.source_code,
                self.graph,
                self.config
            )
            
            if not is_placeholder(method_node):
                # Update method context
                global_context['current_method_context'] = func_name
                global_context['current_scope_context'] = f"{global_context['current_class_context']}.{func_name}"
                
                # Create relationship with containing class
                relationship = create_relationship(
                    self.scope_tracker['current_class'],
                    method_node['id'],
                    REL_TYPES['CONTAINS']
                )
                self.graph['relationships'].append(relationship)
                
                # Track current method for variable scope
                previous_method = self.scope_tracker['current_method']
                self.scope_tracker['current_method'] = method_node['id']
                
                # Visit child nodes
                self.generic_visit(node)
                
                # Restore previous context
                self.scope_tracker['current_method'] = previous_method
                global_context['current_method_context'] = None
                global_context['current_scope_context'] = global_context['current_class_context']
        else:
            # This is a function
            func_node = create_entity_node(
                NODE_TYPES['FUNCTION'],
                func_name,
                self.file_path,
                self.get_location_info(node),
                {
                    'is_async': False,
                    'is_generator': any(isinstance(n, ast.Yield) or isinstance(n, ast.YieldFrom) 
                                     for n in ast.walk(node)),
                    'decorators': [d.id if isinstance(d, ast.Name) else str(d) for d in node.decorator_list]
                },
                self.source_code,
                self.graph,
                self.config
            )
            
            if not is_placeholder(func_node):
                # Update context
                global_context['current_method_context'] = None
                global_context['current_scope_context'] = func_name
                
                # Add to scope
                self.scope_tracker['declared_variables'][func_name] = func_node['id']
                
                # Visit child nodes
                self.generic_visit(node)
                
                # Restore context
                global_context['current_scope_context'] = None
    
    def visit_AsyncFunctionDef(self, node):
        """Handle async function definitions"""
        # Similar to visit_FunctionDef but mark as async
        func_name = node.name
        
        if self.scope_tracker['current_class']:
            # This is an async method
            method_node = create_entity_node(
                NODE_TYPES['METHOD'],
                func_name,
                self.file_path,
                self.get_location_info(node),
                {
                    'is_async': True,
                    'is_generator': any(isinstance(n, ast.Yield) or isinstance(n, ast.YieldFrom) 
                                     for n in ast.walk(node)),
                    'parent_class': global_context['current_class_context'],
                    'decorators': [d.id if isinstance(d, ast.Name) else str(d) for d in node.decorator_list]
                },
                self.source_code,
                self.graph,
                self.config
            )
            
            if not is_placeholder(method_node):
                global_context['current_method_context'] = func_name
                global_context['current_scope_context'] = f"{global_context['current_class_context']}.{func_name}"
                
                relationship = create_relationship(
                    self.scope_tracker['current_class'],
                    method_node['id'],
                    REL_TYPES['CONTAINS']
                )
                self.graph['relationships'].append(relationship)
                
                previous_method = self.scope_tracker['current_method']
                self.scope_tracker['current_method'] = method_node['id']
                
                self.generic_visit(node)
                
                self.scope_tracker['current_method'] = previous_method
                global_context['current_method_context'] = None
                global_context['current_scope_context'] = global_context['current_class_context']
        else:
            # This is an async function
            func_node = create_entity_node(
                NODE_TYPES['FUNCTION'],
                func_name,
                self.file_path,
                self.get_location_info(node),
                {
                    'is_async': True,
                    'is_generator': any(isinstance(n, ast.Yield) or isinstance(n, ast.YieldFrom) 
                                     for n in ast.walk(node)),
                    'decorators': [d.id if isinstance(d, ast.Name) else str(d) for d in node.decorator_list]
                },
                self.source_code,
                self.graph,
                self.config
            )
            
            if not is_placeholder(func_node):
                global_context['current_method_context'] = None
                global_context['current_scope_context'] = func_name
                
                self.scope_tracker['declared_variables'][func_name] = func_node['id']
                
                self.generic_visit(node)
                
                global_context['current_scope_context'] = None
    
    def visit_Assign(self, node):
        """Handle variable assignments"""
        for target in node.targets:
            if isinstance(target, ast.Name):
                var_name = target.id
                var_node = create_entity_node(
                    NODE_TYPES['VARIABLE'],
                    var_name,
                    self.file_path,
                    self.get_location_info(target),
                    {},
                    self.source_code,
                    self.graph,
                    self.config
                )
                
                if not is_placeholder(var_node):
                    # Track in current scope
                    self.scope_tracker['declared_variables'][var_name] = var_node['id']
                    
                    # Handle variable initialization references
                    if isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name):
                        callee_name = node.value.func.id
                        if callee_name in self.scope_tracker['declared_variables']:
                            relationship = create_relationship(
                                var_node['id'],
                                self.scope_tracker['declared_variables'][callee_name],
                                REL_TYPES['CALLS']
                            )
                            self.graph['relationships'].append(relationship)
                    elif isinstance(node.value, ast.Name):
                        init_name = node.value.id
                        if init_name in self.scope_tracker['declared_variables']:
                            relationship = create_relationship(
                                var_node['id'],
                                self.scope_tracker['declared_variables'][init_name],
                                REL_TYPES['REFERENCES']
                            )
                            self.graph['relationships'].append(relationship)
                    
                    # Connect to parent scope
                    if self.scope_tracker['current_method']:
                        relationship = create_relationship(
                            self.scope_tracker['current_method'],
                            var_node['id'],
                            REL_TYPES['DECLARES']
                        )
                        self.graph['relationships'].append(relationship)
                    elif self.scope_tracker['current_class']:
                        relationship = create_relationship(
                            self.scope_tracker['current_class'],
                            var_node['id'],
                            REL_TYPES['DECLARES']
                        )
                        self.graph['relationships'].append(relationship)
        
        self.generic_visit(node)
    
    def visit_Call(self, node):
        """Handle function calls"""
        if isinstance(node.func, ast.Name):
            callee_name = node.func.id
            
            # Regular function calls
            if callee_name in self.scope_tracker['declared_variables']:
                # Create a relationship from current scope to the called function
                source_id = None
                if self.scope_tracker['current_method']:
                    source_id = self.scope_tracker['current_method']
                elif self.scope_tracker['current_class']:
                    source_id = self.scope_tracker['current_class']
                else:
                    source_id = self.file_node['id']
                
                relationship = create_relationship(
                    source_id,
                    self.scope_tracker['declared_variables'][callee_name],
                    REL_TYPES['CALLS']
                )
                self.graph['relationships'].append(relationship)
        
        self.generic_visit(node)

def analyze_file(file_path, graph, config):
    """Analyze a Python file and extract its structure"""
    print(f"Analyzing file: {file_path}")
    
    try:
        with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
            source_code = f.read()
        
        # Parse the AST
        tree = ast.parse(source_code, filename=file_path)
        
        # Create and run the visitor
        visitor = PythonASTVisitor(file_path, source_code, graph, config)
        visitor.visit(tree)
        
    except SyntaxError as e:
        print(f"Syntax error in {file_path}: {e}")
    except Exception as e:
        print(f"Error analyzing file {file_path}: {e}") 