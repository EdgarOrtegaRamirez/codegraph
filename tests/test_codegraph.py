"""Tests for CodeGraph."""

import json
import tempfile
from pathlib import Path

import pytest

from codegraph.graph import CodeGraph, Symbol
from codegraph.indexer import Indexer
from codegraph.output import format_markdown, format_stats
from codegraph.parsers.python import PythonParser
from codegraph.utils import discover_files, detect_language


# --- Test fixtures ---

SAMPLE_PYTHON = '''
"""Sample module docstring."""

import os
from typing import Optional


class MyClass:
    """A sample class."""

    def __init__(self, name: str):
        """Initialize."""
        self.name = name

    def greet(self) -> str:
        """Say hello."""
        return f"Hello, {self.name}"


def standalone(x: int, y: int = 10) -> int:
    """A standalone function."""
    return x + y


async def async_func(data: str) -> dict:
    """An async function."""
    return {"data": data}
'''


@pytest.fixture
def sample_file(tmp_path: Path) -> Path:
    """Create a temporary Python file with sample code."""
    f = tmp_path / "sample.py"
    f.write_text(SAMPLE_PYTHON)
    return f


@pytest.fixture
def sample_graph() -> CodeGraph:
    """Create an empty graph for testing."""
    return CodeGraph(root_path="/test")


# --- Test file discovery ---

class TestDiscoverFiles:
    def test_discovers_py_files(self, tmp_path: Path) -> None:
        (tmp_path / "a.py").write_text("# a")
        (tmp_path / "b.py").write_text("# b")
        (tmp_path / "sub").mkdir()
        (tmp_path / "sub" / "c.py").write_text("# c")
        files = list(discover_files(tmp_path))
        names = {f.name for f in files}
        assert names == {"a.py", "b.py", "c.py"}

    def test_ignores_node_modules(self, tmp_path: Path) -> None:
        (tmp_path / "main.py").write_text("# main")
        (tmp_path / "node_modules").mkdir()
        (tmp_path / "node_modules" / "pkg.py").write_text("# pkg")
        files = list(discover_files(tmp_path))
        names = {f.name for f in files}
        assert names == {"main.py"}

    def test_ignores_pycache(self, tmp_path: Path) -> None:
        (tmp_path / "main.py").write_text("# main")
        (tmp_path / "__pycache__").mkdir()
        (tmp_path / "__pycache__" / "mod.pyc").write_text("# pyc")
        files = list(discover_files(tmp_path))
        names = {f.name for f in files}
        assert names == {"main.py"}


# --- Test language detection ---

class TestDetectLanguage:
    def test_python(self) -> None:
        assert detect_language(Path("foo.py")) == "python"

    def test_javascript(self) -> None:
        assert detect_language(Path("foo.js")) == "javascript"
        assert detect_language(Path("foo.ts")) == "typescript"

    def test_unknown(self) -> None:
        assert detect_language(Path("foo.xyz")) is None


# --- Test Python parser ---

class TestPythonParser:
    def test_parses_functions(self, sample_file: Path, sample_graph: CodeGraph) -> None:
        parser = PythonParser(sample_file.parent)
        parser.parse_file(sample_file, sample_graph)

        funcs = [s for s in sample_graph.symbols.values() if s.kind == "function"]
        assert len(funcs) == 2  # standalone + async_func
        names = {f.name for f in funcs}
        assert "standalone" in names
        assert "async_func" in names

    def test_parses_classes(self, sample_file: Path, sample_graph: CodeGraph) -> None:
        parser = PythonParser(sample_file.parent)
        parser.parse_file(sample_file, sample_graph)

        classes = [s for s in sample_graph.symbols.values() if s.kind == "class"]
        assert len(classes) == 1
        assert classes[0].name == "MyClass"

    def test_parses_methods(self, sample_file: Path, sample_graph: CodeGraph) -> None:
        parser = PythonParser(sample_file.parent)
        parser.parse_file(sample_file, sample_graph)

        methods = [s for s in sample_graph.symbols.values() if s.kind == "method"]
        names = {m.name for m in methods}
        assert "__init__" in names
        assert "greet" in names

    def test_parses_imports(self, sample_file: Path, sample_graph: CodeGraph) -> None:
        parser = PythonParser(sample_file.parent)
        parser.parse_file(sample_file, sample_graph)

        assert len(sample_graph.imports) == 2
        modules = {i.module for i in sample_graph.imports}
        assert "os" in modules
        assert "typing" in modules

    def test_parses_signatures(self, sample_file: Path, sample_graph: CodeGraph) -> None:
        parser = PythonParser(sample_file.parent)
        parser.parse_file(sample_file, sample_graph)

        func = next(s for s in sample_graph.symbols.values() if s.name == "standalone")
        assert "x: int" in func.signature
        assert "y: int" in func.signature
        assert "-> int" in func.signature

    def test_parses_docstrings(self, sample_file: Path, sample_graph: CodeGraph) -> None:
        parser = PythonParser(sample_file.parent)
        parser.parse_file(sample_file, sample_graph)

        cls = next(s for s in sample_graph.symbols.values() if s.kind == "class")
        assert "A sample class." in cls.docstring

    def test_detects_async(self, sample_file: Path, sample_graph: CodeGraph) -> None:
        parser = PythonParser(sample_file.parent)
        parser.parse_file(sample_file, sample_graph)

        async_func = next(s for s in sample_graph.symbols.values() if s.name == "async_func")
        assert async_func.is_async

    def test_detects_access_level(self, sample_file: Path, sample_graph: CodeGraph) -> None:
        parser = PythonParser(sample_file.parent)
        parser.parse_file(sample_file, sample_graph)

        # _private should be detected
        private = next((s for s in sample_graph.symbols.values() if s.name.startswith("_")), None)
        # __init__ is a dunder, so public
        init = next((s for s in sample_graph.symbols.values() if s.name == "__init__"), None)
        assert init is not None
        assert init.access == "public"  # dunders are public


# --- Test graph serialization ---

class TestGraphSerialization:
    def test_to_dict(self, sample_graph: CodeGraph) -> None:
        sym = Symbol(
            name="foo", kind="function", file="test.py", line=1, column=0,
            signature="def foo() -> None",
        )
        sample_graph.add_symbol(sym)
        d = sample_graph.to_dict()
        assert "metadata" in d
        assert "symbols" in d
        assert "test.py:1" in d["symbols"]
        assert d["symbols"]["test.py:1"]["name"] == "foo"

    def test_to_json(self, sample_graph: CodeGraph) -> None:
        json_str = sample_graph.to_json()
        data = json.loads(json_str)
        assert "metadata" in data

    def test_save(self, sample_graph: CodeGraph) -> None:
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name
        sample_graph.save(path)
        assert Path(path).exists()
        content = Path(path).read_text()
        data = json.loads(content)
        assert "metadata" in data


# --- Test output formatters ---

class TestOutputFormatters:
    def test_format_markdown(self, sample_graph: CodeGraph) -> None:
        output = format_markdown(sample_graph)
        assert "# CodeGraph Analysis" in output
        assert "## Summary" in output

    def test_format_stats(self, sample_graph: CodeGraph) -> None:
        output = format_stats(sample_graph)
        assert "CodeGraph Statistics" in output
        assert "Total symbols:" in output
