export interface IngestResult {
  repo_url: string;
  files_parsed: number;
  classes: number;
  functions: number;
}

export interface QueryResult {
  question: string;
  cypher: string | null;
  results: Record<string, unknown>[];
  error: string | null;
  answer: string;
}

export interface GraphStats {
  files: number;
  classes: number;
  functions: number;
  calls: number;
  inherits: number;
  imports: number;
}

const DEFAULT_BACKEND_URL = "http://localhost:8000";

/** Thin HTTP wrapper around the Python backend. This is the only place in
 * the MCP server that knows the backend's API shape -- the actual repo
 * parsing, graph storage, and NL-to-Cypher logic all live there. */
export class BackendClient {
  constructor(private readonly baseUrl: string = process.env.REPOMIND_BACKEND_URL ?? DEFAULT_BACKEND_URL) {}

  async ingestRepo(repoUrl: string): Promise<IngestResult> {
    return this.post<IngestResult>("/ingest", { repo_url: repoUrl });
  }

  async query(question: string): Promise<QueryResult> {
    return this.post<QueryResult>("/query", { question });
  }

  async graphStats(): Promise<GraphStats> {
    return this.get<GraphStats>("/graph/stats");
  }

  private async post<T>(path: string, body: unknown): Promise<T> {
    const response = await fetch(`${this.baseUrl}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    return this.handleResponse<T>(response);
  }

  private async get<T>(path: string): Promise<T> {
    const response = await fetch(`${this.baseUrl}${path}`);
    return this.handleResponse<T>(response);
  }

  private async handleResponse<T>(response: Response): Promise<T> {
    if (!response.ok) {
      const body = await response.text();
      throw new Error(`Backend request failed (${response.status}): ${body}`);
    }
    return (await response.json()) as T;
  }
}
