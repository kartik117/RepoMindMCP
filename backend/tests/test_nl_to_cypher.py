from dataclasses import dataclass

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
