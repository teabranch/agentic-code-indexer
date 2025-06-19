Here is a step-by-step action item list, with checkboxes, to implement the Agentix Code Indexing System design:

### Agentix Code Indexing System: Step-by-Step Implementation Guide

This guide breaks down the implementation into phases, aligning with the actionable recommendations outlined in the sources.

---

### **Phase 1: Foundation & Chunker Development**

*   **Step 1: Setup Neo4j Database and Schema**
    *   [x] **Install Neo4j**: Set up a Neo4j instance (Community Edition, AuraDB, or Docker).
    *   [x] **Define Schema**: Translate the detailed graph model (Section 3.2) into Cypher schema creation scripts.
    *   [x] **Create Uniqueness Constraints**: Execute Cypher commands to create uniqueness constraints for crucial node properties (critical for `MERGE` performance and data integrity):
        *   [x] `CREATE CONSTRAINT ON (f:File) ASSERT f.path IS UNIQUE`.
        *   [x] `CREATE CONSTRAINT ON (c:Class) ASSERT c.full_name IS UNIQUE`.
        *   [x] `CREATE CONSTRAINT ON (m:Method) ASSERT m.full_name IS UNIQUE`.
        *   [x] Create similar constraints for `Function.full_name` and `Variable.full_name`.
    *   [x] **Create Vector Indexes**: Create vector indexes on the `embedding` property for all searchable node types:
        *   [x] `CREATE VECTOR INDEX code_summaries_file_embedding IF NOT EXISTS FOR (n:File) ON (n.embedding) OPTIONS { indexConfig: { `vector.dimensions`: 768, `vector.similarity_function`: 'cosine' } }`.
        *   [x] Create separate vector indexes for `Class`, `Method`, and `Variable` nodes, ensuring `vector.dimensions` is 768 (as recommended for `jina-embeddings-v2-base-code`).

*   **Step 2: Implement C# Chunker (`Repository/src/csharp-chunker`)**
    *   [ ] **Project Setup**: Create a **.NET console application project** for the C# chunker.
    *   [ ] **Add NuGet Packages**: Install `Microsoft.CodeAnalysis.CSharp` and `Microsoft.CodeAnalysis.Workspaces.MSBuild` NuGet packages.
    *   [ ] **Solution/Project Loading**: Implement logic to **load `.sln` or `.csproj` files using `MSBuildWorkspace.OpenSolutionAsync()`** to provide compilation context for semantic analysis.
    *   [ ] **Syntax Tree Acquisition**: Iterate through `solution.Projects` and `project.Documents` to obtain the `SyntaxTree` for each `Document` (which preserves all trivia like comments and whitespace).
    *   [ ] **Syntactic Traversal**: Implement traversal using a **custom `CSharpSyntaxWalker`** to identify core code elements (`ClassDeclaration`, `MethodDeclaration`, `PropertyDeclaration`, `VariableDeclarator`).
    *   [ ] **Semantic Analysis**: Obtain the `SemanticModel` for each `Document` via `document.GetSemanticModelAsync()`.
    *   [ ] **Symbol Resolution**: Use `GetSymbolInfo()` and `GetDeclaredSymbol()` on syntax nodes to retrieve `ISymbol` objects. From `ISymbol`, extract **fully qualified names** (e.g., using `ToDisplayString(SymbolDisplayFormat.FullyQualifiedFormat)`), types, and visibility, which is essential for precise `CALLS` relationships.
    *   [ ] **Data Extraction**: Extract properties for C# nodes (`Class`, `Method`, `Variable`, `Interface`), including `full_name`, `signature`, `return_type`, `type`, `raw_code`, and location details (start/end lines).
    *   [ ] **Relationship Identification**: Identify structural (`CONTAINS`, `DEFINES`, `HAS_MEMBER`), behavioral (`CALLS`, `INSTANTIATES`), and inheritance (`EXTENDS`, `IMPLEMENTS`) relationships with high precision due to semantic resolution.
    *   [ ] **Output**: Serialize the extracted data into the **common JSON format** (defined in Section 3.1 and Step 5).
    *   [ ] **Testing**: Develop unit tests to ensure accurate parsing and extraction for various C# code constructs.

*   **Step 3: Implement Python Chunker (`Repository/src/python-chunker`)**
    *   [x] **Project Setup**: Create a Python package/module for the Python chunker.
    *   [x] **Install Libraries**: Install **`LibCST`** and **`ast-scope`**.
    *   [x] **Parsing**: Implement parsing logic using **`LibCST`** to generate a Concrete Syntax Tree (CST), meticulously preserving all comments, whitespace, and formatting.
    *   [x] **Scope Analysis**: Integrate **`ast-scope.annotate()`** to resolve variable scopes (e.g., `FunctionScope`, `GlobalScope`) by converting the LibCST tree to a standard `ast` tree if necessary.
    *   [x] **Information Extraction**: Traverse the CST to identify `FunctionDef`, `ClassDef`, and `Assign` nodes, extracting names and identifiers.
    *   [x] **Docstring Extraction**: Reliably extract docstrings using helper functions or by inspecting the first statement within a function/class body.
    *   [x] **Data Extraction**: Extract properties for Python nodes (`File`, `Class`, `Function`, `Method`, `Variable`, `Parameter`), including `raw_code` snippets and location information (start/end lines).
    *   [x] **Relationship Identification**: Identify `CONTAINS`, `DEFINES`, `DECLARES`, and `SCOPES` relationships.
    *   [x] **Output**: Serialize the extracted data into the **common JSON format**.
    *   [ ] **Testing**: Develop unit tests to verify parsing accuracy, comment preservation, and scope resolution.

*   **Step 4: Implement NodeJS Chunker (`Repository/src/nodejs-chunker`)**
    *   [x] **Project Setup**: Create a NodeJS project for the chunker.
    *   [x] **Install Libraries**: Install **`acorn`**.
    *   [x] **TypeScript Setup**: Set up TypeScript compilation for the chunker itself.
    *   [x] **File Type & Module System Detection**: Implement logic to differentiate `.js`, `.ts`, `.tsx` files and detect CommonJS vs. ES Modules based on file extension (`.mjs`, `.cjs`) or the `"type"` field in `package.json`.
    *   [x] **Parsing Logic (Hybrid)**:
        *   [x] For `.js` files, use **`acorn`** with the appropriate `sourceType` option set to `"module"` for ES Modules to recognize `ImportDeclaration` and `ExportNamedDeclaration` nodes.
        *   [x] For `.ts`/`.tsx` files, use the **TypeScript Compiler API** to parse and extract rich type information.
    *   [x] **CommonJS Heuristics**: Implement heuristics for CJS `require` calls and `module.exports`/`exports.someIdentifier` assignments by traversing `CallExpression` and `AssignmentExpression` nodes.
    *   [x] **Data Extraction**: Extract properties for NodeJS nodes (`File`, `Function`, `Class`, `Variable`, `Parameter`), including `name`, `type`, `raw_code`, and location information.
    *   [x] **Relationship Identification**: Identify `CONTAINS`, `DEFINES`, `DECLARES`, and `IMPORTS` relationships.
    *   [x] **Output**: Serialize the extracted data into the **common JSON format**.
    *   [x] **Testing**: Develop tests for both JS and TS parsing, covering different module systems and syntax.

*   **Step 5: Define Common Intermediate Data Format**
    *   [x] **Refine Schema**: Finalize the **precise JSON schema** that each chunker will output.
    *   [x] **Format Structure**: Ensure it includes fields for `label(s)`, `properties`, and ways to represent relationships (e.g., `source_id`, `target_id`, `type`).
    *   [x] **Validation**: Verify the format is flexible enough for all languages but structured enough for easy ingestion into Neo4j.

---

### **Phase 2: Main Indexing Pipeline Development (`Repository/src/agentix_code_indexer`)**

*   **Step 6: Develop File Traversal & Change Detection**
    *   [ ] **Recursive Traversal**: Implement Python code in `agentix_code_indexer` to **recursively walk through directories** and identify target source files (`.py`, `.cs`, `.js`, `.ts`) using `os.walk`.
    *   [ ] **Content Hashing**: Implement **SHA-256 hashing** for file contents.
    *   [ ] **Checksum Storage/Retrieval**: Integrate with Neo4j to **store and retrieve the `checksum` property** on `:File` nodes for incremental updates.
    *   [ ] **Decision Logic**: Implement the logic to identify **new, modified, and unchanged files** based on hash comparison.
    *   [ ] **Processing Queue**: Create an internal queue/list of files that need to be processed (new or modified).
    *   [ ] **Deleted File Handling**: After traversal, implement a process to query the graph for `:File` nodes whose paths no longer exist in the file system and **delete them and their associated sub-graphs**.

*   **Step 7: Implement Graph Structure Population**
    *   [ ] **Chunker Invocation**: Develop Python code to **call the relevant language-specific chunkers** (e.g., via `subprocess.run` to execute console applications).
    *   [ ] **Ingestion Logic**: Implement parsing of the **structured JSON output** from the chunkers.
    *   [ ] **Neo4j Write Operations**: Implement Neo4j write logic using an appropriate Python driver (e.g., `neo4j` library).
    *   [ ] **Idempotent Writes**: Use **`MERGE` clauses extensively** with the unique properties (`path`, `full_name`) to ensure nodes and relationships are created only if they don't exist and updated if they do.
    *   [ ] **Batched Writes**: Implement **`UNWIND` queries** to send large batches of node/relationship data to Neo4j in a single transaction, significantly improving performance.
    *   [ ] **Bulk Data Loading (Optional)**: For initial, large imports, consider exporting parsed data to CSV files and using Neo4j's `LOAD CSV` command with `USING PERIODIC COMMIT` for memory efficiency.

*   **Step 8: Implement Hierarchical Summarization Orchestrator**
    *   [ ] **Topological Traversal**: Design a Python component that **queries Neo4j to identify nodes ready for summarization** in a bottom-up fashion.
    *   [ ] **Order of Processing**:
        *   [ ] First, process all **leaf nodes** in the containment hierarchy (e.g., `Variable` and `Parameter` nodes that lack `generated_summary`).
        *   [ ] Next, process nodes that contain them (e.g., `Method` and `Function` nodes), using the newly generated summaries of their children as context in the LLM prompts.
        *   [ ] Continue up the hierarchy to `Class` nodes, then `File` nodes, and finally `Directory` nodes.
    *   [ ] **State Management**: Potentially use a property on nodes (e.g., `summary_status: 'PENDING', 'GENERATED'`) or query patterns to manage which nodes need processing.

*   **Step 9: Integrate LLM & Embedding Models**
    *   [ ] **API Client Implementation**: Develop Python clients for the chosen LLM (e.g., Anthropic Claude API) and embedding model (e.g., Jina AI API or local inference with Hugging Face `transformers`).
    *   [ ] **Prompt Construction**: Implement the **prompt engineering logic** (Section 3.3.1) to create structured prompts for each node type and hierarchical level.
    *   [ ] **Context Injection**: Dynamically inject context from lower-level summaries (prompt chaining) into higher-level prompts.
    *   [ ] **API Calls**: Send **batched prompts** to the LLM for `generated_summary` and to the embedding model for `embedding` vectors.
    *   [ ] **Result Storage**: Update the respective Neo4j nodes with the `generated_summary` string and `embedding` list property.
    *   [ ] **Configurability**: Ensure LLM/embedding model selection (and API keys/endpoints) is **configurable** via environment variables or a dedicated configuration file.

*   **Step 10: Implement Transaction & Batch Management**
    *   [ ] **Error Handling**: Implement robust error handling and retry mechanisms for API calls and database writes.
    *   [ ] **Performance Tuning**: Monitor and **adjust batch sizes** for LLM/embedding API calls and Neo4j `UNWIND` operations to optimize throughput and cost.
    *   [ ] **Idempotency Review**: Double-check all write operations to ensure they are idempotent using `MERGE` and handle potential re-runs gracefully.

---

### **Phase 3: Retrieval System Development (Initial Focus)**

*   **Step 11: Implement Basic Retrieval Patterns**
    *   [ ] **Specific Entity Lookup**: Create functions/APIs that perform direct `MATCH (n:Label {name: 'EntityName'})` queries in Neo4j for known code elements (highly efficient with indexes).
    *   [ ] **Basic Vector Search**: Implement an endpoint that:
        *   [ ] Takes a natural language query.
        *   [ ] Generates its embedding using the ***same*** embedding model used for indexing (e.g., `jina-embeddings-v2-base-code`).
        *   [ ] Performs a similarity search against the vector index in Neo4j using `CALL db.index.vector.queryNodes('code_summaries_file_embedding', 10, $query_embedding) YIELD node, score RETURN node, score`.

*   **Step 12: Develop Graph Context Expansion**
    *   [ ] **Traversal Logic**: Build Cypher queries that start from the nodes returned by vector search or direct lookups and **traverse relationships** (e.g., `CALLS`, `DEFINES`, `CONTAINS`, `EXTENDS`, `IMPORTS`) to gather related context (GraphRAG).
    *   [ ] **Traversal Strategies**: Define different traversal patterns based on the initial node type (e.g., for a `Method` node, retrieve defining `Class`, containing `File`, `CALLS` relationships, `DECLARES` variables; for a `Class` node, retrieve `DEFINES` methods, inheritance hierarchy, implemented interfaces).
    *   [ ] **Utilize `neo4j-graphrag`**: Explore integrating the `neo4j-graphrag` Python package for battle-tested patterns in constructing these complex GraphRAG queries.

*   **Step 13: Implement Hybrid Search Logic**
    *   [ ] **Query Parsing**: Develop logic to identify specific keywords or entity names within natural language queries that can be used for direct lookups or filtering.
    *   [ ] **Combined Queries**: Construct Cypher queries that **combine vector search results with graph traversals and property filters** (e.g., "Find functions for 'payment processing' that use the Stripe library").

*   **Step 14: Implement Ranking and Optimization**
    *   [ ] **Limit Results**: Apply **`LIMIT` clauses** to all retrieval queries and set reasonable upper bounds for graph traversals (e.g., `[*..5]`) to prevent overwhelming responses and ensure performance.
    *   [ ] **Score Combination**: For hybrid queries, implement a strategy to **combine vector similarity scores** with other relevance signals (e.g., full-text index scores for keywords).
    *   [ ] **Graph-based Ranking (Optional)**: Consider running graph algorithms like **PageRank** offline to pre-compute node importance for ranking.
    *   [ ] **Pre-computed Views (Optional)**: Generate detailed summaries for critical components during indexing as a cache for frequent queries.
    *   [ ] **Query Parameterization**: Ensure all user input in Cypher queries is passed as **parameters** to allow Neo4j's query plan caching and significantly improve performance.

---

## New Items

Items discovered during implementation that were not in the original design:

*   [ ] **C# Chunker Implementation**: Step 2 in the original design is not yet implemented. Need to create the C# chunker using Microsoft.CodeAnalysis.CSharp.
*   [ ] **Docker Compose Setup**: Created docker-compose.yml for easy Neo4j development setup with proper plugins and configuration.
*   [ ] **Environment Configuration**: Created .env support for database connection parameters and API keys.
*   [ ] **Testing Framework Setup**: Need to implement unit tests for all chunkers to ensure accuracy and reliability.
*   [ ] **CI/CD Pipeline**: Need to set up continuous integration for testing and deployment.
*   [ ] **Performance Benchmarking**: Need to implement performance testing to measure chunker speed and accuracy across different codebases.
*   [ ] **Error Handling & Logging**: Enhanced error handling and structured logging across all components.
*   [ ] **Configuration Management**: Centralized configuration management for all chunkers and the main pipeline.
*   [ ] **Python Virtual Environment Setup**: Need to document and automate Python virtual environment setup for development.
*   [x] **NodeJS Package Management**: Enhanced package.json with proper dependencies and development workflow.
*   [x] **Complete NodeJS Chunker Implementation**: Fully implemented TypeScript/JavaScript chunker with comprehensive AST parsing, including classes, interfaces, functions, methods, parameters, variables, imports, and exports.
*   [ ] **Cross-Platform Compatibility**: Ensure all scripts and tools work across Windows, macOS, and Linux.
*   [ ] **Documentation Generation**: Automated documentation generation from code comments and docstrings.
*   [ ] **API Rate Limiting**: Implement rate limiting for external API calls (LLM, embedding models).
*   [ ] **Database Migration Scripts**: Create database migration scripts for schema updates and versioning.
*   [ ] **Backup and Recovery**: Implement backup strategies for Neo4j database and processed data.