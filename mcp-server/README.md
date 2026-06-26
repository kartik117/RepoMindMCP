# repomind-mcp-server

The MCP server Claude Desktop / Cursor actually connect to. It's a thin protocol adapter over stdio — all the real work (cloning, parsing, the knowledge graph, the NL-to-Cypher chain) happens in `../backend`, which this calls over HTTP.

## Tools exposed

- `ingest_repo(repoUrl)` — clone + parse + graph a public repo
- `query_codebase(question)` — ask a structural question about the ingested repo
- `graph_stats()` — counts of files/classes/functions/relationships currently in the graph

## Setup

```bash
npm install
npm run build
```

Requires the backend (and Neo4j) running — see the root README.

## Connecting it to Claude Desktop

Add to `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "repomind": {
      "command": "node",
      "args": ["/absolute/path/to/RepoMindMCP/mcp-server/dist/index.js"],
      "env": { "REPOMIND_BACKEND_URL": "http://localhost:8000" }
    }
  }
}
```

Restart Claude Desktop, then ask it to ingest a repo and answer questions about it.

## Testing

```bash
npm test
```
