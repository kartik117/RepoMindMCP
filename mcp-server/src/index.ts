#!/usr/bin/env node
import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { z } from "zod";

import { BackendClient } from "./backendClient.js";

const backend = new BackendClient();

const server = new McpServer({ name: "repomind", version: "0.1.0" });

server.registerTool(
  "ingest_repo",
  {
    title: "Ingest a GitHub repository",
    description:
      "Clones a public GitHub repo and parses it into a knowledge graph " +
      "(functions, classes, calls, imports, inheritance). Run this before " +
      "asking questions about a repo -- there's one graph at a time, so " +
      "ingesting a new repo replaces whatever was there before.",
    inputSchema: {
      repoUrl: z.string().describe("HTTPS URL of the GitHub repo, e.g. https://github.com/org/repo.git"),
    },
  },
  async ({ repoUrl }) => {
    try {
      const result = await backend.ingestRepo(repoUrl);
      return {
        content: [
          {
            type: "text",
            text: `Ingested ${result.repo_url}: ${result.files_parsed} files parsed, ${result.classes} classes, ${result.functions} functions.`,
          },
        ],
      };
    } catch (error) {
      return {
        content: [{ type: "text", text: `Failed to ingest repo: ${(error as Error).message}` }],
        isError: true,
      };
    }
  },
);

server.registerTool(
  "query_codebase",
  {
    title: "Ask a question about the ingested codebase",
    description:
      "Answers a natural-language structural question about the most " +
      "recently ingested repo (e.g. 'what calls X', 'what does Y inherit " +
      "from', 'what does this file import'), grounded in the actual " +
      "knowledge graph rather than a guess.",
    inputSchema: { question: z.string() },
  },
  async ({ question }) => {
    try {
      const result = await backend.query(question);
      const cypherLine = `\n\nCypher used: ${result.cypher ?? "(none generated)"}`;
      return { content: [{ type: "text", text: result.answer + cypherLine }] };
    } catch (error) {
      return {
        content: [{ type: "text", text: `Failed to query codebase: ${(error as Error).message}` }],
        isError: true,
      };
    }
  },
);

server.registerTool(
  "graph_stats",
  {
    title: "Get knowledge graph statistics",
    description: "Returns counts of files, classes, functions, and relationships currently in the knowledge graph.",
    inputSchema: {},
  },
  async () => {
    try {
      const stats = await backend.graphStats();
      return {
        content: [
          {
            type: "text",
            text: `Files: ${stats.files}, Classes: ${stats.classes}, Functions: ${stats.functions}, Calls: ${stats.calls}, Inherits: ${stats.inherits}, Imports: ${stats.imports}`,
          },
        ],
      };
    } catch (error) {
      return {
        content: [{ type: "text", text: `Failed to get graph stats: ${(error as Error).message}` }],
        isError: true,
      };
    }
  },
);

async function main(): Promise<void> {
  const transport = new StdioServerTransport();
  await server.connect(transport);
}

main().catch((error: unknown) => {
  console.error("Fatal error in main():", error);
  process.exit(1);
});
