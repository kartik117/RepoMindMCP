from repomind.parsers.python_parser import parse_python_file

_SOURCE = '''\
import os
from collections import OrderedDict as OD

def helper():
    return 1

class Animal(Base):
    def speak(self):
        return helper()
'''


def test_parses_imports(tmp_path):
    file_path = tmp_path / "pkg" / "mod.py"
    file_path.parent.mkdir(parents=True)
    file_path.write_text(_SOURCE)

    parsed = parse_python_file(file_path, tmp_path)

    assert parsed.language == "python"
    assert parsed.path == "pkg/mod.py"
    modules = [imp.module for imp in parsed.imports]
    assert "os" in modules
    assert "collections" in modules
    collections_import = next(imp for imp in parsed.imports if imp.module == "collections")
    assert collections_import.names == ["OrderedDict"]


def test_parses_top_level_function(tmp_path):
    file_path = tmp_path / "mod.py"
    file_path.write_text(_SOURCE)

    parsed = parse_python_file(file_path, tmp_path)

    assert len(parsed.functions) == 1
    func = parsed.functions[0]
    assert func.name == "helper"
    assert func.qualified_name == "mod.helper"
    assert func.line_number == 4


def test_parses_class_with_base_and_method_calls(tmp_path):
    file_path = tmp_path / "mod.py"
    file_path.write_text(_SOURCE)

    parsed = parse_python_file(file_path, tmp_path)

    assert len(parsed.classes) == 1
    cls = parsed.classes[0]
    assert cls.name == "Animal"
    assert cls.qualified_name == "mod.Animal"
    assert cls.bases == ["Base"]
    assert len(cls.methods) == 1
    speak = cls.methods[0]
    assert speak.name == "speak"
    assert speak.qualified_name == "mod.Animal.speak"
    assert speak.calls == ["helper"]


def test_parses_nested_module_path(tmp_path):
    file_path = tmp_path / "pkg" / "sub" / "mod.py"
    file_path.parent.mkdir(parents=True)
    file_path.write_text("def f(): pass")

    parsed = parse_python_file(file_path, tmp_path)

    assert parsed.functions[0].qualified_name == "pkg.sub.mod.f"
