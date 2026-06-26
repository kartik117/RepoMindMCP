import pytest

from repomind.parsers.treesitter_parser import parse_javascript_file, parse_typescript_file

_JS_SOURCE = """\
import { foo, bar as baz } from "./utils";
import Default from "default-pkg";

class Animal extends Base {
  speak() {
    return helper();
  }
}

function helper() {
  return 1;
}
"""


@pytest.fixture(params=[("mod.js", parse_javascript_file), ("mod.ts", parse_typescript_file)])
def parsed(request, tmp_path):
    filename, parse_fn = request.param
    file_path = tmp_path / filename
    file_path.write_text(_JS_SOURCE)
    return parse_fn(file_path, tmp_path)


def test_parses_imports(parsed):
    modules = [imp.module for imp in parsed.imports]
    assert "./utils" in modules
    assert "default-pkg" in modules
    utils_import = next(imp for imp in parsed.imports if imp.module == "./utils")
    assert utils_import.names == ["foo", "bar"]


def test_parses_class_with_base_and_method_calls(parsed):
    assert len(parsed.classes) == 1
    cls = parsed.classes[0]
    assert cls.name == "Animal"
    assert cls.bases == ["Base"]
    assert len(cls.methods) == 1
    speak = cls.methods[0]
    assert speak.name == "speak"
    assert speak.calls == ["helper"]


def test_parses_top_level_function(parsed):
    assert len(parsed.functions) == 1
    func = parsed.functions[0]
    assert func.name == "helper"
    assert func.qualified_name.endswith(".helper")


def test_member_expression_calls_extract_property_name(tmp_path):
    source = """\
function run() {
  return this.service.execute();
}
"""
    file_path = tmp_path / "mod.js"
    file_path.write_text(source)

    parsed = parse_javascript_file(file_path, tmp_path)

    assert parsed.functions[0].calls == ["execute"]
