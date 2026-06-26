import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from pydantic import BaseModel

from repomind.graph import get_driver
from repomind.ingest import ingest_repo
from repomind.query import NLToCypherChain

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    driver = get_driver()
    app.state.driver = driver
    # Stored on app.state, not constructed fresh per-request, specifically so
    # tests can swap in a fake chain (real Gemini calls aren't something a
    # unit test suite should depend on) without needing a request-scoped
    # dependency-injection layer just for this one seam.
    app.state.chain = NLToCypherChain(driver)
    yield
    driver.close()


app = FastAPI(title="RepoMind", version="0.1.0", lifespan=lifespan)


class IngestRequest(BaseModel):
    repo_url: str


class IngestResponse(BaseModel):
    repo_url: str
    files_parsed: int
    classes: int
    functions: int


class QueryRequest(BaseModel):
    question: str


class QueryResponse(BaseModel):
    question: str
    cypher: str | None
    results: list[dict]
    error: str | None
    answer: str


class GraphStats(BaseModel):
    files: int
    classes: int
    functions: int
    calls: int
    inherits: int
    imports: int


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.post("/ingest", response_model=IngestResponse)
def ingest(request: IngestRequest) -> IngestResponse:
    """Clones, parses, and graphs a repo. Synchronous (FastAPI runs `def`
    routes in a thread pool) since git clone + parsing is itself blocking IO
    and CPU work with no async equivalent worth introducing here."""
    try:
        result = ingest_repo(request.repo_url)
    except Exception as exc:
        logger.exception("Failed to ingest %s", request.repo_url)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return IngestResponse(**result)


@app.post("/query", response_model=QueryResponse)
async def query(request: QueryRequest, http_request: Request) -> QueryResponse:
    result = await http_request.app.state.chain.ask(request.question)
    return QueryResponse(**result)


@app.get("/graph/stats", response_model=GraphStats)
async def graph_stats(http_request: Request) -> GraphStats:
    driver = http_request.app.state.driver
    with driver.session() as session:
        # Each COUNT {} subquery is independent, so a graph with zero classes
        # (or zero of anything) still returns a row of zeros. Chaining plain
        # MATCH clauses with WITH doesn't: a MATCH with no matches drops the
        # row entirely, which made this query return no row at all on a
        # graph that had files but, say, no CALLS edges yet.
        row = session.run(
            """
            RETURN
              COUNT { MATCH (f:File) } AS files,
              COUNT { MATCH (c:Class) } AS classes,
              COUNT { MATCH (fn:Function) } AS functions,
              COUNT { MATCH ()-[:CALLS]->() } AS calls,
              COUNT { MATCH ()-[:INHERITS]->() } AS inherits,
              COUNT { MATCH ()-[:IMPORTS]->() } AS imports
            """
        ).single()
    return GraphStats(**dict(row))
