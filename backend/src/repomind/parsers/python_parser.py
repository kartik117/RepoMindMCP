import ast
from pathlib import Path

from repomind.parsers.models import ParsedClass, ParsedFile, ParsedFunction, ParsedImport


def parse_python_file(file_path: Path, repo_root: Path) -> ParsedFile:
    source = file_path.read_text(encoding="utf-8", errors="ignore")
    tree = ast.parse(source, filename=str(file_path))
    relative_path = str(file_path.relative_to(repo_root))
    module_name = relative_path.removesuffix(".py").replace("/", ".")

    imports = _extract_imports(tree)
    functions = []
    classes = []

    for node in tree.body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            functions.append(_parse_function(node, module_name, relative_path))
        elif isinstance(node, ast.ClassDef):
            classes.append(_parse_class(node, module_name, relative_path))

    return ParsedFile(
        path=relative_path, language="python", classes=classes, functions=functions, imports=imports
    )


def _extract_imports(tree: ast.Module) -> list[ParsedImport]:
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(ParsedImport(module=alias.name))
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.append(ParsedImport(module=node.module, names=[alias.name for alias in node.names]))
    return imports


def _parse_function(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    module_name: str,
    file_path: str,
    class_name: str | None = None,
) -> ParsedFunction:
    qualified_name = (
        f"{module_name}.{class_name}.{node.name}" if class_name else f"{module_name}.{node.name}"
    )
    return ParsedFunction(
        name=node.name,
        qualified_name=qualified_name,
        file_path=file_path,
        line_number=node.lineno,
        calls=_extract_calls(node),
    )


def _extract_calls(node: ast.AST) -> list[str]:
    calls = []
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            func = child.func
            if isinstance(func, ast.Name):
                calls.append(func.id)
            elif isinstance(func, ast.Attribute):
                calls.append(func.attr)
    return calls


def _parse_class(node: ast.ClassDef, module_name: str, file_path: str) -> ParsedClass:
    qualified_name = f"{module_name}.{node.name}"
    methods = [
        _parse_function(item, module_name, file_path, class_name=node.name)
        for item in node.body
        if isinstance(item, ast.FunctionDef | ast.AsyncFunctionDef)
    ]
    return ParsedClass(
        name=node.name,
        qualified_name=qualified_name,
        file_path=file_path,
        line_number=node.lineno,
        bases=[_base_name(base) for base in node.bases],
        methods=methods,
    )


def _base_name(node: ast.expr) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ast.unparse(node)
