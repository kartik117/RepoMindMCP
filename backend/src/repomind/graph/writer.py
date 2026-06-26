from neo4j import Driver

from repomind.parsers.models import ParsedFile


class GraphWriter:
    """Writes parsed files into Neo4j as a structural knowledge graph.

    Two passes, deliberately: the first creates every File/Class/Function/
    Module node plus the DEFINES/IMPORTS edges that don't depend on anything
    outside the file being written. CALLS and INHERITS reference *other*
    functions/classes that may live in a file not processed yet (forward
    references, or calls into a file later in the walk order) -- those only
    get linked in the second pass, once every node that could exist, does.
    """

    def __init__(self, driver: Driver) -> None:
        self._driver = driver

    def clear(self) -> None:
        with self._driver.session() as session:
            session.execute_write(lambda tx: tx.run("MATCH (n) DETACH DELETE n"))

    def write_structure(self, parsed_files: list[ParsedFile]) -> None:
        with self._driver.session() as session:
            for parsed in parsed_files:
                session.execute_write(self._write_structure_tx, parsed)

    def write_relationships(self, parsed_files: list[ParsedFile]) -> None:
        with self._driver.session() as session:
            for parsed in parsed_files:
                all_functions = list(parsed.functions) + [
                    method for cls in parsed.classes for method in cls.methods
                ]
                for func in all_functions:
                    for call_name in func.calls:
                        session.execute_write(self._write_call_tx, func.qualified_name, call_name)
                for cls in parsed.classes:
                    for base_name in cls.bases:
                        session.execute_write(self._write_inherits_tx, cls.qualified_name, base_name)

    @staticmethod
    def _write_structure_tx(tx, parsed: ParsedFile) -> None:
        tx.run("MERGE (f:File {path: $path}) SET f.language = $language", path=parsed.path, language=parsed.language)

        for func in parsed.functions:
            tx.run(
                """
                MATCH (f:File {path: $file_path})
                MERGE (fn:Function {qualified_name: $qualified_name})
                SET fn.name = $name, fn.file_path = $file_path, fn.line_number = $line_number
                MERGE (f)-[:DEFINES]->(fn)
                """,
                file_path=parsed.path,
                qualified_name=func.qualified_name,
                name=func.name,
                line_number=func.line_number,
            )

        for cls in parsed.classes:
            tx.run(
                """
                MATCH (f:File {path: $file_path})
                MERGE (c:Class {qualified_name: $qualified_name})
                SET c.name = $name, c.file_path = $file_path, c.line_number = $line_number
                MERGE (f)-[:DEFINES]->(c)
                """,
                file_path=parsed.path,
                qualified_name=cls.qualified_name,
                name=cls.name,
                line_number=cls.line_number,
            )
            for method in cls.methods:
                tx.run(
                    """
                    MATCH (c:Class {qualified_name: $class_qname})
                    MERGE (m:Function {qualified_name: $qualified_name})
                    SET m.name = $name, m.file_path = $file_path, m.line_number = $line_number
                    MERGE (c)-[:DEFINES]->(m)
                    """,
                    class_qname=cls.qualified_name,
                    qualified_name=method.qualified_name,
                    name=method.name,
                    file_path=method.file_path,
                    line_number=method.line_number,
                )

        for imp in parsed.imports:
            tx.run(
                """
                MATCH (f:File {path: $file_path})
                MERGE (mod:Module {name: $module})
                MERGE (f)-[:IMPORTS]->(mod)
                """,
                file_path=parsed.path,
                module=imp.module,
            )

    @staticmethod
    def _write_call_tx(tx, caller_qname: str, call_name: str) -> None:
        # MATCH, not MERGE, on the callee: only link calls that resolve to a
        # function actually defined in this repo. Otherwise every call to
        # print(), len(), or any third-party function would mint a stub node.
        tx.run(
            """
            MATCH (caller:Function {qualified_name: $caller_qname})
            MATCH (callee:Function {name: $call_name})
            MERGE (caller)-[:CALLS]->(callee)
            """,
            caller_qname=caller_qname,
            call_name=call_name,
        )

    @staticmethod
    def _write_inherits_tx(tx, class_qname: str, base_name: str) -> None:
        # Same reasoning as _write_call_tx: skip bases that aren't classes
        # defined in this repo (e.g. inheriting from a third-party library).
        tx.run(
            """
            MATCH (c:Class {qualified_name: $class_qname})
            MATCH (base:Class {name: $base_name})
            MERGE (c)-[:INHERITS]->(base)
            """,
            class_qname=class_qname,
            base_name=base_name,
        )
