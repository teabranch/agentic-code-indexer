"""
Python Scanner Module
Scans directories for Python files and orchestrates the analysis
"""
import os
import json
from pathlib import Path
from constants import NODE_TYPES, VENV_DIRS, PYTHON_EXTENSIONS, DEFAULT_CONFIG
from helpers import get_or_create_folder_node, clear_registries, external_libraries, create_node
from ast_analyzer import analyze_file

def scan_directory(dir_path, graph, config):
    """Recursively scan a directory for Python files"""
    if config.get('ignore_venv') and any(venv_dir in dir_path for venv_dir in VENV_DIRS):
        return
    
    print(f"Scanning directory: {dir_path}")
    
    try:
        items = os.listdir(dir_path)
        for item in items:
            item_path = os.path.join(dir_path, item)
            
            if os.path.isdir(item_path):
                # Skip virtual environment directories
                if config.get('ignore_venv') and item in VENV_DIRS:
                    continue
                scan_directory(item_path, graph, config)
            elif os.path.isfile(item_path):
                # Check if it's a Python file
                if any(item_path.endswith(ext) for ext in PYTHON_EXTENSIONS):
                    analyze_file(item_path, graph, config)
    except PermissionError:
        print(f"Permission denied: {dir_path}")
    except Exception as e:
        print(f"Error scanning directory {dir_path}: {e}")

def parse_requirements_file(root_path):
    """Parse requirements.txt or setup.py to identify project dependencies"""
    dependencies = {}
    
    # Try requirements.txt
    req_files = ['requirements.txt', 'requirements-dev.txt', 'dev-requirements.txt']
    for req_file in req_files:
        req_path = os.path.join(root_path, req_file)
        if os.path.exists(req_path):
            try:
                with open(req_path, 'r', encoding='utf-8') as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith('#') and not line.startswith('-'):
                            # Parse dependency (handle version specs)
                            if '==' in line:
                                name, version = line.split('==', 1)
                                dependencies[name.strip()] = version.strip()
                            elif '>=' in line:
                                name = line.split('>=')[0].strip()
                                dependencies[name] = 'latest'
                            elif '>' in line:
                                name = line.split('>')[0].strip()
                                dependencies[name] = 'latest'
                            else:
                                # Simple package name
                                dependencies[line] = 'latest'
            except Exception as e:
                print(f"Error parsing {req_file}: {e}")
    
    # Try setup.py (basic parsing)
    setup_path = os.path.join(root_path, 'setup.py')
    if os.path.exists(setup_path):
        try:
            with open(setup_path, 'r', encoding='utf-8') as f:
                content = f.read()
                # Look for install_requires or requires
                import re
                requires_match = re.search(r'install_requires\s*=\s*\[(.*?)\]', content, re.DOTALL)
                if requires_match:
                    requires_str = requires_match.group(1)
                    # Extract package names from strings
                    packages = re.findall(r'["\']([^"\'>=<\s]+)', requires_str)
                    for pkg in packages:
                        if pkg not in dependencies:
                            dependencies[pkg] = 'latest'
        except Exception as e:
            print(f"Error parsing setup.py: {e}")
    
    # Try pyproject.toml (basic parsing)
    pyproject_path = os.path.join(root_path, 'pyproject.toml')
    if os.path.exists(pyproject_path):
        try:
            with open(pyproject_path, 'r', encoding='utf-8') as f:
                content = f.read()
                # Look for dependencies in pyproject.toml
                import re
                deps_match = re.search(r'dependencies\s*=\s*\[(.*?)\]', content, re.DOTALL)
                if deps_match:
                    deps_str = deps_match.group(1)
                    packages = re.findall(r'["\']([^"\'>=<\s]+)', deps_str)
                    for pkg in packages:
                        if pkg not in dependencies:
                            dependencies[pkg] = 'latest'
        except Exception as e:
            print(f"Error parsing pyproject.toml: {e}")
    
    return dependencies

def scan_python_service(root_path, custom_config=None):
    """Main function to scan a Python service/project"""
    if custom_config is None:
        custom_config = {}
    
    # Merge with default config
    config = {**DEFAULT_CONFIG, **custom_config}
    
    print(f"Starting scan of Python service at: {root_path}")
    print(f"Configuration: {json.dumps(config, indent=2)}")
    
    # Initialize graph structure
    graph = {'nodes': [], 'relationships': []}
    
    # Clear previous data
    clear_registries()
    
    # Try to find and parse dependency files
    try:
        dependencies = parse_requirements_file(root_path)
        
        # Pre-register all dependencies as external libraries
        for lib_name, version in dependencies.items():
            node = create_node(NODE_TYPES['EXTERNAL_LIBRARY'], lib_name, None, {
                'is_external': True,
                'version': version,
                'from_requirements': True
            })
            graph['nodes'].append(node)
            external_libraries[lib_name] = node
        
        if dependencies:
            print(f"Found {len(dependencies)} dependencies in requirements files")
    except Exception as e:
        print(f"Error parsing dependencies: {e}")
    
    # Initialize root folder
    get_or_create_folder_node(root_path, graph, config)
    
    # Start scanning
    scan_directory(root_path, graph, config)
    
    return graph 