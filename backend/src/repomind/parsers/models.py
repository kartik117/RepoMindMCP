from dataclasses import dataclass, field


@dataclass
class ParsedFunction:
    name: str
    qualified_name: str
    file_path: str
    line_number: int
    calls: list[str] = field(default_factory=list)


@dataclass
class ParsedClass:
    name: str
    qualified_name: str
    file_path: str
    line_number: int
    bases: list[str] = field(default_factory=list)
    methods: list[ParsedFunction] = field(default_factory=list)


@dataclass
class ParsedImport:
    module: str
    names: list[str] = field(default_factory=list)


@dataclass
class ParsedFile:
    path: str
    language: str
    classes: list[ParsedClass] = field(default_factory=list)
    functions: list[ParsedFunction] = field(default_factory=list)
    imports: list[ParsedImport] = field(default_factory=list)
