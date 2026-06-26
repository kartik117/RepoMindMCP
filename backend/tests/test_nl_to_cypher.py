from dataclasses import dataclass
from unittest.mock import patch

from repomind.parsers.models import ParsedFunction, ParsedFile
from repomind.query.nl_to_cypher import NLToCypherChain


@dataclass
class FakeResponse:
    content: str


class FakeLLM:
    def __init__(self, response_text: str = "fake answer") -> None:
        self.response_text = response_text
        self.prompts_seen: list[str] = []

    async def ainvoke(self, prompt: str) -> FakeResponse:
        self.prompts_seen.append(prompt)
        return FakeResponse(self.response_text)


class FailingLLM:
    """Simulates the answer-synthesis call hitting a rate limit (or any
    other failure) after the Cypher query itself already succeeded."""

    async def ainvoke(self, prompt: str):
        raise RuntimeError("429 RESOURCE_EXHAUSTED")


async def test_ask_runs_generated_cypher_against_real_graph(graph_writer, neo4j_driver):
    parsed = ParsedFile(
        path="mod.py",
        language="python",
        functions=[ParsedFunction(name="helper", qualified_name="mod.helper", file_path="mod.py", line_number=1)],
    )
    graph_writer.write_structure([parsed])

    async def fake_generate_cypher(question: str) -> str:
        return "MATCH (fn:Function) RETURN fn.qualified_name AS qname"

    chain = NLToCypherChain(neo4j_driver, generate_cypher=fake_generate_cypher, llm=FakeLLM("there is one function"))
    result = await chain.ask("what functions exist?")

    assert result["error"] is None
    assert result["results"] == [{"qname": "mod.helper"}]
    assert result["answer"] == "there is one function"


async def test_ask_refuses_write_queries_without_running_them(graph_writer, neo4j_driver):
    async def fake_generate_cypher(question: str) -> str:
        return "MATCH (n) DETACH DELETE n"

    chain = NLToCypherChain(neo4j_driver, generate_cypher=fake_generate_cypher, llm=FakeLLM())
    result = await chain.ask("delete everything")

    assert result["error"] == "refused: generated query contained a write operation"
    with neo4j_driver.session() as session:
        count = session.run("MATCH (n) RETURN count(n) AS count").single()["count"]
    assert count == 0  # nothing existed before, and the refusal proves nothing destructive ran


async def test_ask_handles_invalid_cypher_without_raising(graph_writer, neo4j_driver):
    async def fake_generate_cypher(question: str) -> str:
        return "THIS IS NOT VALID CYPHER"

    chain = NLToCypherChain(neo4j_driver, generate_cypher=fake_generate_cypher, llm=FakeLLM())
    result = await chain.ask("nonsense question")

    assert result["error"] is not None
    assert "failed to run" in result["answer"]


async def test_ask_handles_cypher_generation_failure_without_raising(graph_writer, neo4j_driver):
    # Same live-API smoke test, a different stage: with quota fully spent,
    # generate_cypher itself raised before ask() ever reached the rest of
    # the pipeline -- this was also unguarded.
    async def failing_generate_cypher(question: str) -> str:
        raise RuntimeError("429 RESOURCE_EXHAUSTED")

    chain = NLToCypherChain(neo4j_driver, generate_cypher=failing_generate_cypher, llm=FakeLLM())
    result = await chain.ask("what functions exist?")

    assert result["cypher"] is None
    assert result["error"] is not None
    assert "Couldn't generate a query" in result["answer"]


async def test_ask_degrades_gracefully_when_answer_synthesis_fails(graph_writer, neo4j_driver):
    # Caught via a real live-API smoke test: a successful Cypher query
    # followed by a rate-limited answer-synthesis call used to crash ask()
    # entirely instead of returning the (still valid) raw results.
    parsed = ParsedFile(
        path="mod.py",
        language="python",
        functions=[ParsedFunction(name="helper", qualified_name="mod.helper", file_path="mod.py", line_number=1)],
    )
    graph_writer.write_structure([parsed])

    async def fake_generate_cypher(question: str) -> str:
        return "MATCH (fn:Function) RETURN fn.qualified_name AS qname"

    chain = NLToCypherChain(neo4j_driver, generate_cypher=fake_generate_cypher, llm=FailingLLM())
    result = await chain.ask("what functions exist?")

    assert result["error"] is None
    assert result["results"] == [{"qname": "mod.helper"}]
    assert "mod.helper" in result["answer"]


def test_construction_never_touches_the_real_llm_client(graph_writer, neo4j_driver):
    # Caught by CI, not locally: api/main.py's lifespan constructs a chain
    # at FastAPI startup with no llm override. get_chat_model() validates
    # the Gemini API key immediately on construction, so if that used to
    # happen eagerly in __init__, a backend with no key configured (true
    # for CI, true for any contributor who hasn't set one up) would fail to
    # start at all -- not just fail to answer a /query, fail to start.
    with patch("repomind.query.nl_to_cypher.get_chat_model", side_effect=AssertionError("should not be called yet")):
        NLToCypherChain(neo4j_driver)  # must not raise


async def test_ask_degrades_when_llm_client_construction_itself_fails(graph_writer, neo4j_driver):
    parsed = ParsedFile(
        path="mod.py",
        language="python",
        functions=[ParsedFunction(name="helper", qualified_name="mod.helper", file_path="mod.py", line_number=1)],
    )
    graph_writer.write_structure([parsed])

    async def fake_generate_cypher(question: str) -> str:
        return "MATCH (fn:Function) RETURN fn.qualified_name AS qname"

    with patch(
        "repomind.query.nl_to_cypher.get_chat_model",
        side_effect=ValueError("API key required for Gemini Developer API"),
    ):
        chain = NLToCypherChain(neo4j_driver, generate_cypher=fake_generate_cypher)
        result = await chain.ask("what functions exist?")

    assert result["error"] is None  # the query itself succeeded
    assert result["results"] == [{"qname": "mod.helper"}]
    assert "Raw results" in result["answer"]
