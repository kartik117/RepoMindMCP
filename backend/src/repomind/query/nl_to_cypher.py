import re
from collections.abc import Awaitable, Callable

from neo4j import Driver
from pydantic import BaseModel, Field

from repomind.clients import get_chat_model

GRAPH_SCHEMA = """
Nodes:
  File {path, language}
  Module {name}
  Class {qualified_name, name, file_path, line_number}
  Function {qualified_name, name, file_path, line_number}

Relationships:
  (File)-[:DEFINES]->(Class)
  (File)-[:DEFINES]->(Function)
  (Class)-[:DEFINES]->(Function)        // methods
  (Class)-[:INHERITS]->(Class)
  (Function)-[:CALLS]->(Function)
  (File)-[:IMPORTS]->(Module)
"""

_CYPHER_PROMPT = """You are translating a natural-language question about a codebase into a single Cypher query for Neo4j.

Graph schema:
{schema}

Question: {question}

Write exactly one read-only Cypher query (MATCH/RETURN, no writes) that answers \
this question, using only the labels, relationship types, and properties listed \
above. Limit results to 25 rows.
"""

_ANSWER_PROMPT = """Answer the question using only the Cypher query results below. \
If the results are empty, say plainly that nothing was found rather than guessing.

Question: {question}
Results: {results}
"""

_WRITE_KEYWORDS = re.compile(r"\b(CREATE|MERGE|DELETE|SET|REMOVE|DROP|DETACH)\b", re.IGNORECASE)


class CypherQuery(BaseModel):
    cypher: str = Field(description="A single read-only Cypher query")


GenerateCypher = Callable[[str], Awaitable[str]]


async def generate_cypher_with_llm(question: str) -> str:
    structured_llm = get_chat_model().with_structured_output(CypherQuery)
    prompt = _CYPHER_PROMPT.format(schema=GRAPH_SCHEMA, question=question)
    result: CypherQuery = await structured_llm.ainvoke(prompt)
    return result.cypher


def _is_read_only(cypher: str) -> bool:
    return not _WRITE_KEYWORDS.search(cypher)


class NLToCypherChain:
    """Answers natural-language questions about the graph: generates Cypher
    via an LLM, runs it, and synthesizes a plain-language answer from the
    results. This is the brief's "LangChain GraphCypherQAChain" pattern,
    built by hand against the same Gemini structured-output setup used
    elsewhere rather than depending on langchain_community's graph chain
    (separately being sunset -- see the ragas compat issue in MedallionNYC)."""

    def __init__(
        self,
        driver: Driver,
        generate_cypher: GenerateCypher = generate_cypher_with_llm,
        llm=None,
    ) -> None:
        self._driver = driver
        self._generate_cypher = generate_cypher
        # Lazy, deliberately: constructing ChatGoogleGenerativeAI validates
        # the API key immediately, and this constructor runs at FastAPI
        # startup (see api/main.py's lifespan) -- a backend with no Gemini
        # key configured would otherwise fail to start at all, rather than
        # starting fine and degrading gracefully only if /query is actually
        # called, which is what the try/except in _synthesize_answer is for.
        self._llm = llm

    def _get_llm(self):
        if self._llm is None:
            self._llm = get_chat_model()
        return self._llm

    async def ask(self, question: str) -> dict:
        try:
            cypher = await self._generate_cypher(question)
        except Exception as exc:  # noqa: BLE001 -- e.g. the LLM call itself rate-limited
            return {
                "question": question,
                "cypher": None,
                "results": [],
                "error": str(exc),
                "answer": f"Couldn't generate a query for that question: {exc}",
            }

        if not _is_read_only(cypher):
            return {
                "question": question,
                "cypher": cypher,
                "results": [],
                "error": "refused: generated query contained a write operation",
                "answer": "I couldn't safely answer that -- the generated query attempted a write.",
            }

        try:
            results = self._run_cypher(cypher)
            error = None
        except Exception as exc:  # noqa: BLE001 -- surfaced to the caller, not swallowed
            results = []
            error = str(exc)

        answer = await self._synthesize_answer(question, results, error)
        return {"question": question, "cypher": cypher, "results": results, "error": error, "answer": answer}

    def _run_cypher(self, cypher: str) -> list[dict]:
        with self._driver.session() as session:
            return [record.data() for record in session.run(cypher)]

    async def _synthesize_answer(self, question: str, results: list[dict], error: str | None) -> str:
        if error:
            return f"The generated query failed to run: {error}"
        prompt = _ANSWER_PROMPT.format(question=question, results=results)
        try:
            response = await self._get_llm().ainvoke(prompt)
        except Exception as exc:  # noqa: BLE001 -- the query itself succeeded; degrade, don't crash
            return f"Query succeeded but the answer couldn't be generated ({exc}). Raw results: {results}"
        return response.content
