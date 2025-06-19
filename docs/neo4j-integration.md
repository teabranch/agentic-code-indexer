# Neo4j Integration Guide

## Database Schema

The Agentic Code Indexer creates a rich graph schema in Neo4j that represents code structure and relationships. This document details the database design, querying patterns, and optimization strategies.

## Node Types

### Core Node Types

#### Folder Nodes
```cypher
(:Folder {
  id: "unique_folder_id",
  name: "folder_name",
  path: "/absolute/path/to/folder",
  file_count: 15,
  subfolder_count: 3,
  description: "AI-generated folder description",
  embedding: [0.1, 0.2, ...] // Optional
})
```

#### File Nodes
```cypher
(:File {
  id: "unique_file_id",
  name: "filename.py",
  path: "/absolute/path/to/file.py",
  extension: ".py",
  size: 2048,
  line_count: 120,
  content: "full_file_content",
  description: "AI-generated file description",
  embedding: [0.1, 0.2, ...]
})
```

#### Class Nodes
```cypher
(:Class {
  id: "unique_class_id",
  name: "ClassName",
  code_scope: "class definition code",
  line_start: 10,
  line_end: 50,
  inheritance: ["BaseClass", "Mixin"],
  is_abstract: false,
  description: "AI-generated class description",
  embedding: [0.1, 0.2, ...]
})
```

#### Method Nodes
```cypher
(:Method {
  id: "unique_method_id",
  name: "method_name",
  code_scope: "method definition code",
  line_start: 15,
  line_end: 25,
  is_static: false,
  is_private: false,
  parameters: ["self", "param1", "param2"],
  return_type: "str",
  description: "AI-generated method description",
  embedding: [0.1, 0.2, ...]
})
```

#### Function Nodes
```cypher
(:Function {
  id: "unique_function_id",
  name: "function_name",
  code_scope: "function definition code",
  line_start: 5,
  line_end: 15,
  parameters: ["param1", "param2"],
  return_type: "dict",
  is_async: false,
  description: "AI-generated function description",
  embedding: [0.1, 0.2, ...]
})
```

#### Variable Nodes
```cypher
(:Variable {
  id: "unique_variable_id",
  name: "variable_name",
  value: "variable_value",
  type: "str",
  line_number: 8,
  scope: "global|local|class",
  description: "AI-generated variable description"
})
```

#### Import Nodes
```cypher
(:Import {
  id: "unique_import_id",
  name: "imported_module",
  alias: "module_alias",
  import_type: "from|import|require",
  line_number: 2,
  is_relative: false
})
```

#### External Library Nodes
```cypher
(:ExternalLibrary {
  id: "unique_library_id",
  name: "library_name",
  version: "1.2.3",
  package_manager: "pip|npm",
  description: "Library description from package metadata"
})
```

## Relationship Types

### CONTAINS
Represents hierarchical containment relationships:

```cypher
(:Folder)-[:CONTAINS]->(:File)
(:File)-[:CONTAINS]->(:Class)
(:Class)-[:CONTAINS]->(:Method)
(:File)-[:CONTAINS]->(:Function)
```

### IMPORTS
Tracks import and dependency relationships:

```cypher
(:File)-[:IMPORTS {alias: "pd", line_number: 3}]->(:ExternalLibrary)
(:File)-[:IMPORTS {import_type: "from"}]->(:Import)
```

### CALLS
Function and method call relationships:

```cypher
(:Function)-[:CALLS {call_count: 5, line_numbers: [15, 23, 34]}]->(:Function)
(:Method)-[:CALLS]->(:ExternalLibrary)
```

### EXTENDS
Class inheritance relationships:

```cypher
(:Class)-[:EXTENDS]->(:Class)
(:Class)-[:EXTENDS]->(:ExternalLibrary) // For external base classes
```

### REFERENCES
Variable and symbol references:

```cypher
(:Function)-[:REFERENCES]->(:Variable)
(:Method)-[:REFERENCES]->(:Class)
```

### DECLARES
Variable and function declarations:

```cypher
(:Function)-[:DECLARES]->(:Variable)
(:Class)-[:DECLARES]->(:Method)
```

## Database Constraints and Indexes

### Unique Constraints

```cypher
-- Ensure unique node IDs
CREATE CONSTRAINT folder_id_unique IF NOT EXISTS FOR (n:Folder) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT file_id_unique IF NOT EXISTS FOR (n:File) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT class_id_unique IF NOT EXISTS FOR (n:Class) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT method_id_unique IF NOT EXISTS FOR (n:Method) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT function_id_unique IF NOT EXISTS FOR (n:Function) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT variable_id_unique IF NOT EXISTS FOR (n:Variable) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT import_id_unique IF NOT EXISTS FOR (n:Import) REQUIRE n.id IS UNIQUE;
CREATE CONSTRAINT external_library_id_unique IF NOT EXISTS FOR (n:ExternalLibrary) REQUIRE n.id IS UNIQUE;
```

### Performance Indexes

```cypher
-- Name-based searches
CREATE INDEX folder_name_index IF NOT EXISTS FOR (n:Folder) ON (n.name);
CREATE INDEX file_name_index IF NOT EXISTS FOR (n:File) ON (n.name);
CREATE INDEX class_name_index IF NOT EXISTS FOR (n:Class) ON (n.name);
CREATE INDEX method_name_index IF NOT EXISTS FOR (n:Method) ON (n.name);
CREATE INDEX function_name_index IF NOT EXISTS FOR (n:Function) ON (n.name);
CREATE INDEX variable_name_index IF NOT EXISTS FOR (n:Variable) ON (n.name);

-- Path-based searches
CREATE INDEX file_path_index IF NOT EXISTS FOR (n:File) ON (n.path);
CREATE INDEX folder_path_index IF NOT EXISTS FOR (n:Folder) ON (n.path);

-- Type-based searches
CREATE INDEX file_extension_index IF NOT EXISTS FOR (n:File) ON (n.extension);
CREATE INDEX variable_type_index IF NOT EXISTS FOR (n:Variable) ON (n.type);

-- Composite indexes for complex queries
CREATE INDEX class_inheritance_index IF NOT EXISTS FOR (n:Class) ON (n.name, n.inheritance);
```

## Common Query Patterns

### 1. Find All Classes in a File

```cypher
MATCH (f:File {name: "models.py"})-[:CONTAINS]->(c:Class)
RETURN c.name, c.description, c.inheritance
ORDER BY c.line_start;
```

### 2. Get Class Hierarchy

```cypher
MATCH path = (child:Class)-[:EXTENDS*]->(ancestor:Class)
WHERE child.name = "SpecificClass"
RETURN path;
```

### 3. Find Functions That Call External APIs

```cypher
MATCH (f:Function)-[:CALLS]->(ext:ExternalLibrary)
WHERE ext.name CONTAINS "requests" OR ext.name CONTAINS "axios"
RETURN f.name, f.description, ext.name as library
ORDER BY f.name;
```

### 4. Analyze Import Dependencies

```cypher
MATCH (file:File)-[:IMPORTS]->(lib:ExternalLibrary)
RETURN file.name, COLLECT(lib.name) as dependencies, COUNT(lib) as dependency_count
ORDER BY dependency_count DESC;
```

### 5. Find Files with Most Classes

```cypher
MATCH (f:File)-[:CONTAINS]->(c:Class)
RETURN f.name, COUNT(c) as class_count
ORDER BY class_count DESC
LIMIT 10;
```

### 6. Get Method Call Graph

```cypher
MATCH (m1:Method)-[:CALLS*1..3]->(m2:Method)
WHERE m1.name = "main_method"
RETURN m1.name, m2.name, LENGTH(SHORTESTPATH((m1)-[:CALLS*]->(m2))) as call_depth;
```

### 7. Find Unused Functions

```cypher
MATCH (f:Function)
WHERE NOT EXISTS(()-[:CALLS]->(f))
AND NOT f.name IN ["main", "__init__", "setUp", "tearDown"]
RETURN f.name, f.description;
```

### 8. Semantic Search Integration

```cypher
// This would be called from Python with computed similarity scores
MATCH (n)
WHERE EXISTS(n.embedding)
RETURN n.id, n.name, n.type, n.description
// Similarity calculation happens in Python layer
```

## Advanced Queries

### 1. Complex Dependency Analysis

```cypher
// Find circular dependencies
MATCH cycle = (f1:File)-[:IMPORTS*2..10]->(f1)
WHERE ALL(r IN relationships(cycle) WHERE type(r) = "IMPORTS")
RETURN cycle;

// Find files that are heavily imported
MATCH (importedFile:File)<-[:IMPORTS]-(importingFile:File)
RETURN importedFile.name, COUNT(DISTINCT importingFile) as import_count
ORDER BY import_count DESC
LIMIT 20;
```

### 2. Code Quality Metrics

```cypher
// Find large classes (high complexity)
MATCH (c:Class)-[:CONTAINS]->(m:Method)
RETURN c.name, COUNT(m) as method_count, 
       c.line_end - c.line_start as line_count
ORDER BY method_count DESC, line_count DESC;

// Find methods with many parameters
MATCH (m:Method)
WHERE SIZE(m.parameters) > 5
RETURN m.name, SIZE(m.parameters) as param_count, m.description
ORDER BY param_count DESC;
```

### 3. Framework Pattern Detection

```cypher
// Find Django models
MATCH (c:Class)-[:EXTENDS]->(base:ExternalLibrary)
WHERE base.name CONTAINS "Model"
RETURN c.name, c.description;

// Find React components
MATCH (c:Class)-[:EXTENDS]->(base)
WHERE base.name IN ["Component", "PureComponent"]
   OR c.name ENDS WITH "Component"
RETURN c.name, c.description;
```

### 4. Dead Code Detection

```cypher
// Find potentially unused classes
MATCH (c:Class)
WHERE NOT EXISTS((c)<-[:EXTENDS]-()) 
  AND NOT EXISTS((c)<-[:CALLS]-())
  AND NOT EXISTS((c)<-[:REFERENCES]-())
RETURN c.name, c.description;
```

## Performance Optimization

### 1. Query Optimization Tips

```cypher
// Use specific labels and properties in MATCH clauses
MATCH (f:File {extension: ".py"})  // Better than MATCH (f:File) WHERE f.extension = ".py"

// Use indexes for WHERE clauses
MATCH (c:Class)
WHERE c.name STARTS WITH "User"  // Uses index if available

// Limit early in the query
MATCH (f:Function)
RETURN f.name
ORDER BY f.name
LIMIT 100;
```

### 2. Batch Operations

```cypher
// Use UNWIND for batch processing
UNWIND $node_data as node
MERGE (n:Function {id: node.id})
SET n += node.properties;
```

### 3. Memory Management

```cypher
// Use PERIODIC COMMIT for large operations (Neo4j 4.x and earlier)
USING PERIODIC COMMIT 1000
LOAD CSV FROM "file:///large_dataset.csv" AS row
CREATE (:Node {property: row.value});

// For Neo4j 5.x, use batching in application layer
```

## Integration with Semantic Search

### Embedding Storage

```cypher
// Store embeddings as arrays
MATCH (n:Function {id: $node_id})
SET n.embedding = $embedding_vector;
```

### Similarity Search Helper Queries

```cypher
// Get all nodes with embeddings for similarity calculation
MATCH (n)
WHERE EXISTS(n.embedding)
RETURN n.id, n.name, n.type, n.description, n.embedding;

// Get context for a specific node
MATCH (center {id: $node_id})
OPTIONAL MATCH path = (center)-[*1..3]-(related)
RETURN center, COLLECT(DISTINCT related) as context;
```

## Backup and Maintenance

### Regular Maintenance Queries

```cypher
// Check database statistics
CALL db.stats.retrieve('GRAPH COUNTS');

// Analyze index usage
CALL db.indexes();

// Check constraint violations
CALL db.constraints();
```

### Data Cleanup

```cypher
// Remove orphaned nodes (be careful with this!)
MATCH (n)
WHERE NOT EXISTS((n)--())
DELETE n;

// Update stale embeddings
MATCH (n)
WHERE EXISTS(n.embedding) AND n.last_updated < datetime() - duration('P7D')
REMOVE n.embedding;
```

## Export and Import

### Export Graph Data

```cypher
// Export to JSON format compatible with the indexer
CALL apoc.export.json.all("graph-export.json", {
  useTypes: true,
  format: "neo4j-shell"
});
```

### Import from Cypher Files

```bash
# Import the generated Cypher file
cat neo4j-import.cypher | cypher-shell -u neo4j -p password --database neo4j
```

## Monitoring and Debugging

### Query Performance Analysis

```cypher
// Profile query performance
PROFILE
MATCH (c:Class)-[:CONTAINS]->(m:Method)
WHERE c.name = "MyClass"
RETURN m.name;

// Explain query plan
EXPLAIN
MATCH (f:Function)-[:CALLS*1..3]->(target:Function)
WHERE f.name = "main"
RETURN target.name;
```

### Database Health Checks

```cypher
// Check node counts by type
MATCH (n)
RETURN labels(n) as node_type, COUNT(n) as count
ORDER BY count DESC;

// Check relationship counts by type
MATCH ()-[r]->()
RETURN type(r) as relationship_type, COUNT(r) as count
ORDER BY count DESC;

// Find nodes without required properties
MATCH (n:Function)
WHERE NOT EXISTS(n.name)
RETURN n;
``` 