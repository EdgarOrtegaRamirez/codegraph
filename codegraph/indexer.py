"""Main indexer for CodeGraph."""

from __future__ import annotations

import time
from pathlib import Path

from codegraph.graph import CodeGraph
from codegraph.parsers.base import BaseParser
from codegraph.parsers.go import GoParser
from codegraph.parsers.javascript import JavaScriptParser
from codegraph.parsers.python import PythonParser
from codegraph.parsers.rust import RustParser
from codegraph.utils import detect_language, discover_files


class Indexer:
    """Orchestrates the indexing of a codebase into a CodeGraph."""

    # Registry of parsers by language
    _parsers: dict[str, type[BaseParser]] = {
        "python": PythonParser,
        "javascript": JavaScriptParser,
        "go": GoParser,
        "rust": RustParser,
    }

    def __init__(self, root: str | Path, extensions: set[str] | None = None):
        self.root = Path(root).resolve()
        self.extensions = extensions or None

    def register_parser(self, language: str, parser_class: type[BaseParser]) -> None:
        """Register a custom parser for a language."""
        self._parsers[language] = parser_class

    def index(self) -> CodeGraph:
        """Index the entire codebase and return the graph.

        Returns:
            A populated CodeGraph.
        """
        graph = CodeGraph(root_path=str(self.root))
        start = time.time()

        files = list(discover_files(self.root, self.extensions))
        total = len(files)
        print(f"Discovered {total} files to index in {self.root}")

        for filepath in files:
            lang = detect_language(filepath)
            if lang is None:
                continue

            parser_cls = self._parsers.get(lang)
            if parser_cls is None:
                continue

            parser = parser_cls(self.root)
            try:
                parser.parse_file(filepath, graph)
            except Exception as e:
                print(f"  Warning: Failed to parse {filepath}: {e}")

        # Finalize summary
        graph.summary.total_files = len(set(s.file for s in graph.symbols.values()))
        graph.summary.total_symbols = len(graph.symbols)
        graph.summary.total_imports = len(graph.imports)
        graph.summary.total_edges = len(graph.edges)

        elapsed = time.time() - start
        print(f"Indexed {graph.summary.total_symbols} symbols in {elapsed:.2f}s")
        print(f"  Functions: {graph.summary.total_functions}")
        print(f"  Classes: {graph.summary.total_classes}")
        print(f"  Imports: {graph.summary.total_imports}")
        print(f"  Call edges: {graph.summary.total_edges}")

        return graph
