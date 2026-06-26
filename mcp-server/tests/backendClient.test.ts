import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { BackendClient } from "../src/backendClient.js";

describe("BackendClient", () => {
  beforeEach(() => {
    vi.stubGlobal("fetch", vi.fn());
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("posts to /ingest with the repo URL and returns the parsed JSON", async () => {
    const fakeResult = { repo_url: "https://github.com/x/y.git", files_parsed: 3, classes: 1, functions: 2 };
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify(fakeResult), { status: 200 }),
    );

    const client = new BackendClient("http://backend.test");
    const result = await client.ingestRepo("https://github.com/x/y.git");

    expect(result).toEqual(fakeResult);
    expect(fetch).toHaveBeenCalledWith(
      "http://backend.test/ingest",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({ repo_url: "https://github.com/x/y.git" }),
      }),
    );
  });

  it("posts to /query with the question and returns the parsed JSON", async () => {
    const fakeResult = {
      question: "what calls foo?",
      cypher: "MATCH (n) RETURN n",
      results: [{ a: 1 }],
      error: null,
      answer: "one function calls foo",
    };
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify(fakeResult), { status: 200 }),
    );

    const client = new BackendClient("http://backend.test");
    const result = await client.query("what calls foo?");

    expect(result).toEqual(fakeResult);
  });

  it("gets /graph/stats and returns the parsed JSON", async () => {
    const fakeStats = { files: 5, classes: 1, functions: 6, calls: 2, inherits: 0, imports: 4 };
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response(JSON.stringify(fakeStats), { status: 200 }),
    );

    const client = new BackendClient("http://backend.test");
    const result = await client.graphStats();

    expect(result).toEqual(fakeStats);
    expect(fetch).toHaveBeenCalledWith("http://backend.test/graph/stats");
  });

  it("throws with the response body when the backend returns an error status", async () => {
    vi.mocked(fetch).mockResolvedValueOnce(
      new Response("repo not found", { status: 400 }),
    );

    const client = new BackendClient("http://backend.test");

    await expect(client.ingestRepo("bad-url")).rejects.toThrow(/400.*repo not found/s);
  });

  it("defaults to localhost:8000 when no base URL or env var is set", async () => {
    delete process.env.REPOMIND_BACKEND_URL;
    vi.mocked(fetch).mockResolvedValueOnce(new Response("{}", { status: 200 }));

    const client = new BackendClient();
    await client.graphStats();

    expect(fetch).toHaveBeenCalledWith("http://localhost:8000/graph/stats");
  });
});
