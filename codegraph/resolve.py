"""Cross-reference resolution for CodeGraph.

Resolves import relationships between symbols across files,
building a more complete call graph and dependency map.
"""

from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

from codegraph.graph import CodeGraph, Symbol


class CrossRefResolver:
    """Resolves cross-file references in a CodeGraph.

    After parsing, imports are just text. This resolver connects
    import statements to actual symbol definitions, building
    a proper dependency graph.
    """

    def __init__(self, graph: CodeGraph):
        self.graph = graph
        # Build lookup indices
        self._symbols_by_name: dict[str, list[Symbol]] = defaultdict(list)
        self._symbols_by_file: dict[str, list[Symbol]] = defaultdict(list)
        self._build_indices()

    def _build_indices(self) -> None:
        """Build lookup indices for fast symbol resolution."""
        for key, sym in self.graph.symbols.items():
            self._symbols_by_name[sym.name].append(sym)
            self._symbols_by_file[sym.file].append(sym)

    def resolve_all(self) -> None:
        """Resolve all cross-file references.

        Updates symbol reference counts and enhances edges.
        """
        self._resolve_imports()
        self._update_reference_counts()

    def _resolve_imports(self) -> None:
        """Resolve import statements to actual symbols."""
        for imp in self.graph.imports:
            target_symbols = self._find_import_targets(imp)
            for sym in target_symbols:
                sym.references += 1

    def _find_import_targets(self, imp: Any) -> list[Symbol]:
        """Find symbols that match an import statement."""
        targets = []
        module = imp.module

        # For relative imports, resolve relative to source file
        if imp.is_relative:
            source_dir = str(Path(imp.source_file).parent)
            module_path = Path(source_dir) / module.lstrip(".")
            module_key = str(module_path).replace("/", ".")
        else:
            module_key = module

        # Try to find matching symbols
        for name in imp.names:
            # Look in same file first (local imports)
            for sym in self._symbols_by_name.get(name, []):
                if sym.file == imp.source_file:
                    continue
                targets.append(sym)

        return targets

    def _update_reference_counts(self) -> None:
        """Update reference counts for all symbols based on call edges."""
        for edge in self.graph.edges:
            # Extract the callee name
            callee_name = edge.callee.split(".")[-1] if "." in edge.callee else edge.callee
            for sym in self._symbols_by_name.get(callee_name, []):
                sym.references += 1

    def get_callers(self, symbol_key: str) -> list[str]:
        """Get all callers of a symbol."""
        callers = []
        for edge in self.graph.edges:
            if edge.callee == symbol_key or edge.callee.endswith("." + symbol_key):
                callers.append(edge.caller)
        return callers

    def get_callees(self, symbol_key: str) -> list[str]:
        """Get all callees of a symbol."""
        callees = []
        for edge in self.graph.edges:
            if edge.caller == symbol_key:
                callees.append(edge.callee)
        return callees

    def get_dependencies(self, file_path: str) -> list[str]:
        """Get all files that a given file depends on."""
        deps = set()
        for imp in self.graph.imports:
            if imp.source_file == file_path:
                deps.add(imp.module)
        return sorted(deps)

    def get_dependents(self, file_path: str) -> list[str]:
        """Get all files that depend on a given file."""
        dependents = set()
        for imp in self.graph.imports:
            if imp.module == file_path or file_path in imp.module:
                dependents.add(imp.source_file)
        return sorted(dependents)


class GraphQuery:
    """Query API for CodeGraph.

    Provides convenient methods for AI coding agents to
    search and explore the knowledge graph.
    """

    def __init__(self, graph: CodeGraph):
        self.graph = graph
        self.resolver = CrossRefResolver(graph)
        self.resolver.resolve_all()

    def search(self, query: str, kind: str | None = None) -> list[dict[str, Any]]:
        """Search symbols by name or docstring.

        Args:
            query: Search string (case-insensitive).
            kind: Optional filter by symbol kind.

        Returns:
            List of matching symbols as dicts.
        """
        results = []
        query_lower = query.lower()
        for sym in self.graph.symbols.values():
            if kind and sym.kind != kind:
                continue
            if (query_lower in sym.name.lower() or
                    query_lower in sym.docstring.lower()):
                results.append(self._symbol_to_dict(sym))
        return results

    def get_symbol(self, file_path: str, line: int) -> dict[str, Any] | None:
        """Get a symbol by file path and line number.

        Args:
            file_path: Relative file path.
            line: Line number (1-indexed).

        Returns:
            Symbol dict or None.
        """
        key = f"{file_path}:{line}"
        sym = self.graph.symbols.get(key)
        if sym:
            return self._symbol_to_dict(sym)
        return None

    def get_functions(self, file_path: str | None = None) -> list[dict[str, Any]]:
        """Get all function symbols, optionally filtered by file.

        Args:
            file_path: Optional file path to filter by.

        Returns:
            List of function dicts.
        """
        results = []
        for sym in self.graph.symbols.values():
            if sym.kind in ("function", "method") and (
                file_path is None or sym.file == file_path
            ):
                results.append(self._symbol_to_dict(sym))
        return results

    def get_classes(self, file_path: str | None = None) -> list[dict[str, Any]]:
        """Get all class/struct/interface symbols, optionally filtered by file.

        Args:
            file_path: Optional file path to filter by.

        Returns:
            List of class dicts.
        """
        results = []
        for sym in self.graph.symbols.values():
            if sym.kind == "class" and (
                file_path is None or sym.file == file_path
            ):
                results.append(self._symbol_to_dict(sym))
        return results

    def get_imports(self, file_path: str) -> list[dict[str, Any]]:
        """Get all imports for a specific file.

        Args:
            file_path: File path to query.

        Returns:
            List of import dicts.
        """
        results = []
        for imp in self.graph.imports:
            if imp.source_file == file_path:
                results.append({
                    "module": imp.module,
                    "names": imp.names,
                    "alias": imp.alias,
                    "is_relative": imp.is_relative,
                    "line": imp.line,
                    "kind": imp.kind,
                })
        return results

    def get_call_graph(self, symbol_key: str, depth: int = 2) -> dict[str, Any]:
        """Get the call graph centered on a symbol.

        Args:
            symbol_key: Symbol key (e.g., "file.py:42").
            depth: How many levels deep to traverse.

        Returns:
            Nested dict representing the call graph.
        """
        return self._traverse_calls(symbol_key, depth, set())

    def _traverse_calls(
        self, symbol_key: str, depth: int, visited: set[str]
    ) -> dict[str, Any]:
        """Recursively traverse call edges."""
        if depth <= 0 or symbol_key in visited:
            return {"key": symbol_key, "depth": 0}

        visited.add(symbol_key)
        callees = []
        for edge in self.graph.edges:
            if edge.caller == symbol_key:
                callee_info = self._traverse_calls(edge.callee, depth - 1, visited.copy())
                callee_info["call_type"] = edge.call_type
                callee_info["line"] = edge.line
                callee_info["callee"] = edge.callee
                callees.append(callee_info)

        return {
            "key": symbol_key,
            "callees": callees,
            "depth": depth,
        }

    def get_summary(self) -> dict[str, Any]:
        """Get a summary of the graph as a dict.

        Counts directly from symbols to stay accurate
        even when symbols are added after query init.
        """
        total_functions = sum(
            1 for s in self.graph.symbols.values()
            if s.kind in ("function", "method")
        )
        total_classes = sum(
            1 for s in self.graph.symbols.values()
            if s.kind == "class"
        )
        total_files = len(set(s.file for s in self.graph.symbols.values()))
        return {
            "total_symbols": len(self.graph.symbols),
            "total_files": total_files,
            "total_functions": total_functions,
            "total_classes": total_classes,
            "total_imports": len(self.graph.imports),
            "total_edges": len(self.graph.edges),
            "languages": self.graph.summary.languages,
        }

    @staticmethod
    def _symbol_to_dict(sym: Symbol) -> dict[str, Any]:
        """Convert a Symbol to a serializable dict."""
        return {
            "name": sym.name,
            "kind": sym.kind,
            "file": sym.file,
            "line": sym.line,
            "column": sym.column,
            "signature": sym.signature,
            "docstring": sym.docstring,
            "access": sym.access,
            "decorators": sym.decorators,
            "parents": sym.parents,
            "parameters": sym.parameters,
            "return_type": sym.return_type,
            "is_async": sym.is_async,
            "is_static": sym.is_static,
            "is_property": sym.is_property,
            "lines_spanned": sym.lines_spanned,
            "references": sym.references,
        }
