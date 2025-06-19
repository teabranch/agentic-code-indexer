# Contributing Guide

## Welcome Contributors!

Thank you for your interest in contributing to the Agentic Code Indexer! This guide will help you get started with contributing to the project.

## Code of Conduct

By participating in this project, you agree to abide by our code of conduct:

- Be respectful and inclusive
- Focus on constructive feedback
- Help maintain a welcoming environment for all contributors
- Follow the project's coding standards and conventions

## How to Contribute

### Types of Contributions

We welcome several types of contributions:

1. **Bug Reports**: Help us identify and fix issues
2. **Feature Requests**: Suggest new functionality
3. **Code Contributions**: Implement fixes or new features
4. **Documentation**: Improve or add documentation
5. **Testing**: Add or improve test coverage
6. **Performance**: Optimize existing functionality

### Getting Started

1. **Fork the Repository**
   ```bash
   git clone https://github.com/your-username/agentic-code-indexer.git
   cd agentic-code-indexer
   ```

2. **Set Up Development Environment**
   ```bash
   # Create virtual environment
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   # or
   venv\Scripts\activate     # Windows
   
   # Install dependencies
   pip install -r requirements-dev.txt
   
   # Install Node.js dependencies
   cd src/agentic_code_indexer/nodejs-chunker
   npm install
   ```

3. **Create a Feature Branch**
   ```bash
   git checkout -b feature/your-feature-name
   # or
   git checkout -b bugfix/issue-description
   ```

## Development Guidelines

### Code Style

#### Python Code Style
- Follow PEP 8 guidelines
- Use meaningful variable and function names
- Add docstrings to all public functions and classes
- Maximum line length: 88 characters (Black formatter)

```python
def example_function(param1: str, param2: int) -> Dict[str, Any]:
    """
    Example function with proper docstring.
    
    Args:
        param1: Description of parameter 1
        param2: Description of parameter 2
        
    Returns:
        Dictionary containing the result
        
    Raises:
        ValueError: If parameters are invalid
    """
    if not param1:
        raise ValueError("param1 cannot be empty")
    
    return {"result": f"{param1}_{param2}"}
```

#### JavaScript Code Style
- Use ES6+ features consistently
- Follow Airbnb JavaScript style guide
- Use meaningful variable names
- Add JSDoc comments for functions

```javascript
/**
 * Example function with proper JSDoc
 * @param {string} param1 - Description of parameter 1
 * @param {number} param2 - Description of parameter 2
 * @returns {Object} The result object
 * @throws {Error} If parameters are invalid
 */
function exampleFunction(param1, param2) {
    if (!param1) {
        throw new Error('param1 cannot be empty');
    }
    
    return { result: `${param1}_${param2}` };
}
```

### Testing

#### Python Tests
We use pytest for Python testing:

```python
# tests/test_code_indexer.py
import pytest
from src.agentic_code_indexer.code_indexer import CodeIndexer

class TestCodeIndexer:
    def test_detect_project_type_python(self, tmp_path):
        # Create a test Python project
        (tmp_path / "requirements.txt").write_text("pytest==7.0.0")
        (tmp_path / "main.py").write_text("print('hello')")
        
        indexer = CodeIndexer()
        project_type = indexer.detect_project_type(str(tmp_path))
        
        assert project_type == "python"
    
    def test_detect_project_type_nodejs(self, tmp_path):
        # Create a test Node.js project
        (tmp_path / "package.json").write_text('{"name": "test"}')
        
        indexer = CodeIndexer()
        project_type = indexer.detect_project_type(str(tmp_path))
        
        assert project_type == "nodejs"
    
    @pytest.fixture
    def mock_openai_client(self):
        # Mock OpenAI client for testing
        pass
```

#### JavaScript Tests
We use Jest for JavaScript testing:

```javascript
// tests/js-scanner.test.js
const jsScanner = require('../src/agentic_code_indexer/nodejs-chunker/js-scanner');

describe('JS Scanner', () => {
    test('should parse simple function', () => {
        const code = 'function test() { return "hello"; }';
        const result = jsScanner.parseCode(code);
        
        expect(result.nodes).toHaveLength(1);
        expect(result.nodes[0].type).toBe('Function');
        expect(result.nodes[0].name).toBe('test');
    });
    
    test('should handle syntax errors gracefully', () => {
        const invalidCode = 'function test( { return "hello"; }';
        
        expect(() => {
            jsScanner.parseCode(invalidCode);
        }).not.toThrow();
    });
});
```

#### Running Tests

```bash
# Run Python tests
pytest tests/ -v

# Run JavaScript tests
cd src/agentic_code_indexer/nodejs-chunker
npm test

# Run all tests with coverage
pytest tests/ --cov=src/agentic_code_indexer --cov-report=html
npm run test:coverage
```

### Adding New Features

#### Adding Language Support

To add support for a new programming language:

1. **Create a new chunker directory**:
   ```
   src/agentic_code_indexer/[language]-chunker/
   ├── main.py (or main.js)
   ├── scanner.py/js
   ├── ast_analyzer.py/js
   ├── constants.py/js
   ├── helpers.py/js
   └── exporters.py/js
   ```

2. **Implement the required interfaces**:
   ```python
   def scan_language_service(root_path: str, config: Dict[str, Any]) -> Dict[str, Any]:
       """
       Main entry point for language chunker
       
       Args:
           root_path: Path to analyze
           config: Configuration options
           
       Returns:
           Graph data with nodes and relationships
       """
       # Implementation here
       pass
   ```

3. **Update the main orchestrator**:
   ```python
   # In code_indexer.py
   def detect_project_type(self, folder_path: str) -> str:
       # Add detection logic for new language
       if self._is_new_language_project(folder_path):
           return 'new_language'
       # ... existing logic
   
   def _chunk_new_language_code(self, folder_path: str) -> Dict[str, Any]:
       # Implementation for new language
       pass
   ```

4. **Add tests** for the new language support

5. **Update documentation** with the new language capabilities

#### Adding Node Types

To add new node types:

1. **Update constants**:
   ```python
   # In constants.py
   NODE_TYPES = {
       # ... existing types
       'NEW_TYPE': 'NewType'
   }
   ```

2. **Update AST analyzer**:
   ```python
   def extract_new_type_nodes(self, node, parent_id=None):
       """Extract new type nodes from AST"""
       # Implementation here
       pass
   ```

3. **Update Neo4j constraints**:
   ```python
   # In code_indexer.py
   constraints = [
       # ... existing constraints
       "CREATE CONSTRAINT IF NOT EXISTS FOR (n:NewType) REQUIRE n.id IS UNIQUE"
   ]
   ```

#### Adding Relationship Types

To add new relationship types:

1. **Update constants**:
   ```python
   RELATIONSHIP_TYPES = {
       # ... existing types
       'NEW_RELATIONSHIP': 'NEW_RELATIONSHIP'
   }
   ```

2. **Update analysis logic**:
   ```python
   def create_new_relationship(self, source_id, target_id, properties=None):
       """Create new type of relationship"""
       relationship = {
           'id': f"{source_id}_NEW_RELATIONSHIP_{target_id}",
           'type': 'NEW_RELATIONSHIP',
           'source': source_id,
           'target': target_id
       }
       if properties:
           relationship.update(properties)
       return relationship
   ```

### Performance Optimization

When contributing performance improvements:

1. **Profile first**: Use profiling tools to identify bottlenecks
   ```python
   import cProfile
   
   pr = cProfile.Profile()
   pr.enable()
   # Your code here
   pr.disable()
   pr.dump_stats('profile_output.prof')
   ```

2. **Benchmark changes**: Measure performance before and after
   ```python
   import time
   
   def benchmark_function(func, *args, **kwargs):
       start = time.time()
       result = func(*args, **kwargs)
       end = time.time()
       print(f"Function took {end - start:.4f} seconds")
       return result
   ```

3. **Consider memory usage**: Use memory profilers for large datasets
   ```python
   from memory_profiler import profile
   
   @profile
   def memory_intensive_function():
       # Your code here
       pass
   ```

## Submitting Changes

### Pull Request Process

1. **Create a Pull Request**
   - Use a descriptive title
   - Reference any related issues
   - Provide a detailed description of changes
   - Include screenshots for UI changes

2. **Pull Request Template**:
   ```markdown
   ## Description
   Brief description of the changes
   
   ## Type of Change
   - [ ] Bug fix
   - [ ] New feature
   - [ ] Breaking change
   - [ ] Documentation update
   
   ## Testing
   - [ ] Tests pass locally
   - [ ] New tests added for new functionality
   - [ ] Manual testing completed
   
   ## Checklist
   - [ ] Code follows project style guidelines
   - [ ] Self-review completed
   - [ ] Documentation updated
   - [ ] No new warnings introduced
   ```

3. **Review Process**
   - Maintainers will review your PR
   - Address feedback promptly
   - Keep PR focused and atomic
   - Rebase if requested

### Commit Guidelines

Use conventional commit messages:

```
type(scope): description

[optional body]

[optional footer]
```

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes
- `refactor`: Code refactoring
- `test`: Adding or updating tests
- `chore`: Maintenance tasks

Examples:
```
feat(chunker): add support for TypeScript decorators

fix(neo4j): handle connection timeout gracefully

docs(api): update CodeIndexer class documentation

test(scanner): add tests for error handling
```

## Issue Reporting

### Bug Reports

Use this template for bug reports:

```markdown
## Bug Description
Clear description of the bug

## Steps to Reproduce
1. Step one
2. Step two
3. Step three

## Expected Behavior
What should happen

## Actual Behavior
What actually happens

## Environment
- OS: [e.g., Ubuntu 20.04]
- Python version: [e.g., 3.9.7]
- Node.js version: [e.g., 18.15.0]
- Neo4j version: [e.g., 5.5.0]

## Additional Context
Any other relevant information
```

### Feature Requests

Use this template for feature requests:

```markdown
## Feature Description
Clear description of the proposed feature

## Use Case
Why is this feature needed?

## Proposed Implementation
How might this be implemented?

## Alternatives Considered
What alternatives have you considered?

## Additional Context
Any other relevant information
```

## Development Environment

### Required Tools

- Python 3.7+
- Node.js 16+
- Neo4j 4.4+
- Git
- Code editor (VS Code recommended)

### Recommended VS Code Extensions

- Python
- Pylance
- Black Formatter
- ESLint
- Prettier
- Neo4j Cypher
- GitLens

### Environment Variables for Development

```env
# Development .env file
OPENAI_API_KEY=your_dev_api_key
NEO4J_URI=bolt://localhost:7687
NEO4J_USER=neo4j
NEO4J_PASSWORD=dev_password

# Development flags
DEBUG=true
LOG_LEVEL=DEBUG
CHUNKER_VERBOSE=true
```

## Release Process

### Version Numbering

We follow Semantic Versioning (SemVer):
- MAJOR: Breaking changes
- MINOR: New features (backward compatible)
- PATCH: Bug fixes (backward compatible)

### Release Checklist

For maintainers releasing new versions:

1. **Pre-release**
   - [ ] All tests pass
   - [ ] Documentation updated
   - [ ] CHANGELOG.md updated
   - [ ] Version bumped in relevant files

2. **Release**
   - [ ] Create release branch
   - [ ] Tag the release
   - [ ] Build and test packages
   - [ ] Publish release

3. **Post-release**
   - [ ] Update main branch
   - [ ] Announce release
   - [ ] Monitor for issues

## Community

### Communication Channels

- **GitHub Issues**: Bug reports and feature requests
- **GitHub Discussions**: General questions and discussions
- **Pull Requests**: Code contributions and reviews

### Getting Help

If you need help:

1. Check existing documentation
2. Search GitHub issues
3. Create a new issue with the "question" label
4. Join GitHub discussions

## Recognition

Contributors will be recognized in:
- README.md contributors section
- Release notes
- Project documentation

Thank you for contributing to Agentic Code Indexer! 