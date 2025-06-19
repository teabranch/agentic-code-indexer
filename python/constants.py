"""
Constants for Python Code Indexer
"""

# Node Types
NODE_TYPES = {
    'FOLDER': 'Folder',
    'FILE': 'File',
    'CLASS': 'Class',
    'METHOD': 'Method',
    'VARIABLE': 'Variable',
    'FUNCTION': 'Function',
    'IMPORT': 'Import',
    'EXTERNAL_LIBRARY': 'ExternalLibrary'
}

# Relationship Types
REL_TYPES = {
    'CONTAINS': 'CONTAINS',
    'IMPORTS': 'IMPORTS',
    'CALLS': 'CALLS',
    'EXTENDS': 'EXTENDS',
    'IMPLEMENTS': 'IMPLEMENTS',
    'REFERENCES': 'REFERENCES',
    'DECLARES': 'DECLARES'
}

# Default Configuration
DEFAULT_CONFIG = {
    'include_variables': False,
    'include_imports': True,
    'include_folders': True,
    'include_files': True,
    'include_classes': True,
    'include_methods': True,
    'include_functions': True,
    'ignore_venv': True,
    'track_external_libraries': False,
    'capture_content': True
}

# Virtual environment directories to ignore
VENV_DIRS = {
    'venv', 'env', '.venv', '.env', 'virtualenv', 
    '__pycache__', '.git', '.pytest_cache', 
    'node_modules', '.mypy_cache', '.tox',
    'site-packages', 'dist', 'build', 'egg-info'
}

# Python file extensions
PYTHON_EXTENSIONS = {'.py', '.pyx', '.pyi'}

# Standard library modules (subset - most commonly used)
STANDARD_LIBRARY_MODULES = {
    'os', 'sys', 'json', 'time', 'datetime', 'math', 'random', 'string',
    'collections', 'itertools', 'functools', 'operator', 'typing',
    'pathlib', 'tempfile', 'shutil', 'glob', 'fnmatch', 'linecache',
    'pickle', 'csv', 'xml', 'html', 'urllib', 'http', 'email',
    'base64', 'hashlib', 'hmac', 'secrets', 'ssl', 'socket',
    'threading', 'multiprocessing', 'concurrent', 'asyncio',
    'logging', 'warnings', 'traceback', 'inspect', 'gc',
    'weakref', 'copy', 'pprint', 'reprlib', 'enum', 'dataclasses',
    'contextlib', 'abc', 'atexit', 'argparse', 'getopt', 'readline',
    'subprocess', 'platform', 'ctypes', 'struct', 'codecs',
    'unicodedata', 'stringprep', 'io', 'mmap', 'select', 'selectors',
    'signal', 'errno', 'stat', 'filecmp', 'zipfile', 'tarfile',
    'gzip', 'bz2', 'lzma', 'zlib', 'sqlite3', 'dbm', 'shelve'
} 