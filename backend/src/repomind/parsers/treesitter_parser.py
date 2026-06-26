import re
from pathlib import Path

import tree_sitter_javascript
import tree_sitter_typescript
from tree_sitter import Language, Node, Parser

from repomind.parsers.models import ParsedClass, ParsedFile, ParsedFunction, ParsedImport

_JS_LANGUAGE = Language(tree_sitter_javascript.language())
_TS_LANGUAGE = Language(tree_sitter_typescript.language_typescript())

_EXTENSION_RE = re.compile(r"\.(js|jsx|mjs|ts|tsx)$")


def parse_javascript_file(file_path: Path, repo_root: Path) -> ParsedFile:
    return _parse_file(file_path, repo_root, _JS_LANGUAGE, "javascript")


def parse_typescript_file(file_path: Path, repo_root: Path) -> ParsedFile:
    return _parse_file(file_path, repo_root, _TS_LANGUAGE, "typescript")


def _parse_file(file_path: Path, repo_root: Path, language: Language, language_name: str) -> ParsedFile:
    source = file_path.read_bytes()
    tree = Parser(language).parse(source)
    relative_path = str(file_path.relative_to(repo_root))
    module_name = _EXTENSION_RE.sub("", relative_path).replace("/", ".")

    classes = []
    functions = []
    imports = []
    for node in tree.root_node.children:
        if node.type == "function_declaration":
            functions.append(_parse_function(node, source, module_name, relative_path))
        elif node.type == "class_declaration":
            classes.append(_parse_class(node, source, module_name, relative_path))
        elif node.type == "import_statement":
            imports.append(_parse_import(node, source))

    return ParsedFile(
        path=relative_path, language=language_name, classes=classes, functions=functions, imports=imports
    )


def _text(node: Node, source: bytes) -> str:
    return source[node.start_byte : node.end_byte].decode("utf-8", errors="ignore")


def _find_child_by_type(node: Node, type_name: str) -> Node | None:
    for child in node.children:
        if child.type == type_name:
            return child
    return None


def _find_descendant_by_types(node: Node, type_names: set[str]) -> Node | None:
    """Recursive version of _find_child_by_type. Needed for class heritage,
    since plain JS nests the base class identifier directly under
    class_heritage, while TypeScript's grammar adds an extra extends_clause
    level in between -- searching direct children only finds it for one of
    the two grammars."""
    for child in node.children:
        if child.type in type_names:
            return child
        found = _find_descendant_by_types(child, type_names)
        if found is not None:
            return found
    return None


def _parse_function(
    node: Node, source: bytes, module_name: str, file_path: str, class_name: str | None = None
) -> ParsedFunction:
    name_node = node.child_by_field_name("name")
    name = _text(name_node, source) if name_node else "<anonymous>"
    qualified_name = (
        f"{module_name}.{class_name}.{name}" if class_name else f"{module_name}.{name}"
    )
    return ParsedFunction(
        name=name,
        qualified_name=qualified_name,
        file_path=file_path,
        line_number=node.start_point[0] + 1,
        calls=_extract_calls(node, source),
    )


def _extract_calls(node: Node, source: bytes) -> list[str]:
    calls: list[str] = []
    _walk_calls(node, source, calls)
    return calls


def _walk_calls(node: Node, source: bytes, calls: list[str]) -> None:
    if node.type == "call_expression":
        func = node.child_by_field_name("function")
        if func is not None:
            if func.type == "identifier":
                calls.append(_text(func, source))
            elif func.type == "member_expression":
                prop = func.child_by_field_name("property")
                if prop is not None:
                    calls.append(_text(prop, source))
    for child in node.children:
        _walk_calls(child, source, calls)


def _parse_class(node: Node, source: bytes, module_name: str, file_path: str) -> ParsedClass:
    name_node = node.child_by_field_name("name")
    name = _text(name_node, source) if name_node else "<anonymous>"

    bases = []
    heritage = _find_child_by_type(node, "class_heritage")
    if heritage is not None:
        base_node = _find_descendant_by_types(heritage, {"identifier", "type_identifier"})
        if base_node is not None:
            bases.append(_text(base_node, source))

    methods = []
    body = node.child_by_field_name("body")
    if body is not None:
        for child in body.children:
            if child.type == "method_definition":
                methods.append(_parse_function(child, source, module_name, file_path, class_name=name))

    return ParsedClass(
        name=name,
        qualified_name=f"{module_name}.{name}",
        file_path=file_path,
        line_number=node.start_point[0] + 1,
        bases=bases,
        methods=methods,
    )


def _parse_import(node: Node, source: bytes) -> ParsedImport:
    module = ""
    source_node = node.child_by_field_name("source")
    if source_node is not None:
        fragment = _find_child_by_type(source_node, "string_fragment")
        module = _text(fragment, source) if fragment is not None else _text(source_node, source).strip("'\"")

    names = []
    clause = _find_child_by_type(node, "import_clause")
    if clause is not None:
        default_id = _find_child_by_type(clause, "identifier")
        if default_id is not None:
            names.append(_text(default_id, source))
        named = _find_child_by_type(clause, "named_imports")
        if named is not None:
            for spec in named.children:
                if spec.type == "import_specifier":
                    id_node = _find_child_by_type(spec, "identifier")
                    if id_node is not None:
                        names.append(_text(id_node, source))

    return ParsedImport(module=module, names=names)
