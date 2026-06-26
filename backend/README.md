# repomind-backend

Python service: clones a repo, parses it (AST for Python, tree-sitter for JS/TS), builds a Neo4j knowledge graph, and answers natural-language questions about it via an NL-to-Cypher chain. Exposed over FastAPI for the TypeScript MCP server to call.
