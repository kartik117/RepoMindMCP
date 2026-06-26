from repomind.parsers.models import ParsedClass, ParsedFile, ParsedFunction, ParsedImport


def _run_query(driver, cypher: str, **params) -> list[dict]:
    with driver.session() as session:
        return [record.data() for record in session.run(cypher, **params)]


def test_write_structure_creates_file_function_and_import_nodes(graph_writer, neo4j_driver):
    parsed = ParsedFile(
        path="mod.py",
        language="python",
        functions=[ParsedFunction(name="helper", qualified_name="mod.helper", file_path="mod.py", line_number=1)],
        imports=[ParsedImport(module="os")],
    )

    graph_writer.write_structure([parsed])

    files = _run_query(neo4j_driver, "MATCH (f:File {path: 'mod.py'}) RETURN f.language AS language")
    assert files == [{"language": "python"}]

    functions = _run_query(
        neo4j_driver, "MATCH (:File)-[:DEFINES]->(fn:Function) RETURN fn.qualified_name AS qname"
    )
    assert functions == [{"qname": "mod.helper"}]

    modules = _run_query(neo4j_driver, "MATCH (:File)-[:IMPORTS]->(m:Module) RETURN m.name AS name")
    assert modules == [{"name": "os"}]


def test_write_structure_links_methods_to_class(graph_writer, neo4j_driver):
    parsed = ParsedFile(
        path="mod.py",
        language="python",
        classes=[
            ParsedClass(
                name="Animal",
                qualified_name="mod.Animal",
                file_path="mod.py",
                line_number=1,
                methods=[
                    ParsedFunction(
                        name="speak", qualified_name="mod.Animal.speak", file_path="mod.py", line_number=2
                    )
                ],
            )
        ],
    )

    graph_writer.write_structure([parsed])

    rows = _run_query(
        neo4j_driver,
        "MATCH (c:Class {qualified_name: 'mod.Animal'})-[:DEFINES]->(m:Function) RETURN m.qualified_name AS qname",
    )
    assert rows == [{"qname": "mod.Animal.speak"}]


def test_write_relationships_links_calls_within_repo_only(graph_writer, neo4j_driver):
    parsed = ParsedFile(
        path="mod.py",
        language="python",
        functions=[
            ParsedFunction(
                name="caller", qualified_name="mod.caller", file_path="mod.py", line_number=1, calls=["helper", "print"]
            ),
            ParsedFunction(name="helper", qualified_name="mod.helper", file_path="mod.py", line_number=5),
        ],
    )
    graph_writer.write_structure([parsed])

    graph_writer.write_relationships([parsed])

    calls = _run_query(
        neo4j_driver,
        "MATCH (:Function {qualified_name: 'mod.caller'})-[:CALLS]->(callee:Function) RETURN callee.qualified_name AS qname",
    )
    # print() isn't a function defined in this repo, so it should not appear as a node at all
    assert calls == [{"qname": "mod.helper"}]


def test_write_relationships_links_inheritance_within_repo_only(graph_writer, neo4j_driver):
    parsed = ParsedFile(
        path="mod.py",
        language="python",
        classes=[
            ParsedClass(name="Base", qualified_name="mod.Base", file_path="mod.py", line_number=1),
            ParsedClass(
                name="Animal", qualified_name="mod.Animal", file_path="mod.py", line_number=5, bases=["Base", "ExternalLib"]
            ),
        ],
    )
    graph_writer.write_structure([parsed])

    graph_writer.write_relationships([parsed])

    inherits = _run_query(
        neo4j_driver,
        "MATCH (:Class {qualified_name: 'mod.Animal'})-[:INHERITS]->(base:Class) RETURN base.qualified_name AS qname",
    )
    assert inherits == [{"qname": "mod.Base"}]


def test_clear_removes_all_nodes(graph_writer, neo4j_driver):
    parsed = ParsedFile(path="mod.py", language="python")
    graph_writer.write_structure([parsed])

    graph_writer.clear()

    rows = _run_query(neo4j_driver, "MATCH (n) RETURN count(n) AS count")
    assert rows == [{"count": 0}]
