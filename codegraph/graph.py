"""Knowledge graph data structures for CodeGraph."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class Symbol:
    """A symbol found in the codebase (function, class, method, import, etc.)."""
    name: str
    kind: str  # function, class, method, variable, import, module, decorator
    file: str  # relative path from project root
    line: int
    column: int
    signature: str = ""  # e.g., "def foo(x: int) -> str"
    docstring: str = ""
    access: str = "public"  # public, private, protected
    decorators: list[str] = field(default_factory=list)
    parents: list[str] = field(default_factory=list)  # enclosing scopes
    parameters: list[str] = field(default_factory=list)
    return_type: str = ""
    is_async: bool = False
    is_static: bool = False
    is_property: bool = False
    lines_spanned: int = 0
    references: int = 0  # how many times this symbol is referenced elsewhere


@dataclass
class ImportInfo:
    """An import statement."""
    source_file: str
    module: str  # e.g., "os.path"
    names: list[str]  # e.g., ["join", "exists"]
    alias: dict[str, str] = field(default_factory=dict)  # name -> alias
    is_relative: bool = False
    line: int = 0
    kind: str = "import"  # import, from ... import


@dataclass
class CallEdge:
    """A call edge between two symbols."""
    caller: str  # "file.py:42"
    callee: str  # "module.Class.method"
    call_type: str = "direct"  # direct, dynamic, import, super
    line: int = 0


@dataclass
class GraphSummary:
    """Summary statistics for the graph."""
    total_symbols: int = 0
    total_files: int = 0
    total_functions: int = 0
    total_classes: int = 0
    total_imports: int = 0
    total_edges: int = 0
    languages: dict[str, int] = field(default_factory=dict)
    total_lines_indexed: int = 0


@dataclass
class CodeGraph:
    """The complete knowledge graph for a codebase."""
    symbols: dict[str, Symbol] = field(default_factory=dict)
    edges: list[CallEdge] = field(default_factory=list)
    imports: list[ImportInfo] = field(default_factory=list)
    summary: GraphSummary = field(default_factory=GraphSummary)
    root_path: str = ""

    def add_symbol(self, symbol: Symbol) -> None:
        key = f"{symbol.file}:{symbol.line}"
        self.symbols[key] = symbol

    def add_edge(self, edge: CallEdge) -> None:
        self.edges.append(edge)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "metadata": {
                "version": "0.1.0",
                "root": self.root_path,
                "generated_at": "TODO",
            },
            "summary": asdict(self.summary),
            "symbols": {k: asdict(v) for k, v in self.symbols.items()},
            "edges": [asdict(e) for e in self.edges],
            "imports": [asdict(i) for i in self.imports],
        }

    def to_json(self, indent: int = 2) -> str:
        """Serialize to JSON string."""
        return json.dumps(self.to_dict(), indent=indent, default=str)

    def save(self, path: str | Path) -> None:
        """Save the graph to a JSON file."""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w") as f:
            f.write(self.to_json(indent=2))
