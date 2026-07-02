"""Go parser using regex-based extraction.

Extracts functions, methods, structs, interfaces, and their
relationships from Go source files. Uses regex patterns for
parsing — no external dependencies.
"""

from __future__ import annotations

import re
from pathlib import Path

from codegraph.graph import CallEdge, CodeGraph, ImportInfo, Symbol
from codegraph.utils import rel_path


class GoParser:
    """Parse Go source files into a CodeGraph.

    Uses regex-based extraction — no external dependencies.
    """

    def __init__(self, root: Path):
        self.root = root

    def parse_file(self, filepath: Path, graph: CodeGraph) -> None:
        """Parse a single Go file and add its symbols to the graph."""
        source = filepath.read_text(encoding="utf-8", errors="replace")
        rel = rel_path(filepath, self.root)

        self._extract_functions(source, rel, graph)
        self._extract_methods(source, rel, graph)
        self._extract_structs(source, rel, graph)
        self._extract_interfaces(source, rel, graph)
        self._extract_imports(source, rel, graph)
        self._extract_call_edges(source, rel, graph)
        self._extract_variables(source, rel, graph)

    def _extract_functions(self, source: str, rel: str, graph: CodeGraph) -> None:
        """Extract function declarations."""
        # func Name(params) (returns) { body }
        func_pattern = re.compile(
            r"^func\s+(?:\(\s*\w+\s+\*?\w+\s*\)\s+)?"  # receiver (method)
            r"(\w+)\s*\(([^)]*)\)"  # name and params
            r"(?:\s*\(([^)]*)\))?"  # return types
            r"\s*\{?",
            re.MULTILINE,
        )
        for m in func_pattern.finditer(source):
            name = m.group(1)
            params_str = m.group(2).strip()
            returns_str = m.group(3) or ""

            params = self._parse_go_params(params_str)
            ret_type = returns_str.strip() if returns_str else ""
            line_num = source[: m.start()].count("\n") + 1

            sig = self._build_signature(name, params, ret_type, False)

            graph.add_symbol(
                Symbol(
                    name=name,
                    kind="function",
                    file=rel,
                    line=line_num,
                    column=0,
                    signature=sig,
                    parameters=params,
                    return_type=ret_type,
                    access="public" if name[0].isupper() else "private",
                    lines_spanned=1,
                )
            )

    def _extract_methods(self, source: str, rel: str, graph: CodeGraph) -> None:
        """Extract method declarations (func (receiver) name(...))."""
        method_pattern = re.compile(
            r"^func\s*\(\s*\w+\s+\*?\w+\s*\)\s+(\w+)\s*\(([^)]*)\)"
            r"(?:\s*\(([^)]*)\))?"
            r"\s*\{?",
            re.MULTILINE,
        )
        for m in method_pattern.finditer(source):
            name = m.group(1)
            params_str = m.group(2).strip()
            returns_str = m.group(3) or ""

            params = self._parse_go_params(params_str)
            ret_type = returns_str.strip() if returns_str else ""
            line_num = source[: m.start()].count("\n") + 1

            sig = self._build_signature(name, params, ret_type, False)

            graph.add_symbol(
                Symbol(
                    name=name,
                    kind="method",
                    file=rel,
                    line=line_num,
                    column=0,
                    signature=sig,
                    parameters=params,
                    return_type=ret_type,
                    access="public" if name[0].isupper() else "private",
                    lines_spanned=1,
                )
            )

    def _extract_structs(self, source: str, rel: str, graph: CodeGraph) -> None:
        """Extract struct declarations."""
        struct_pattern = re.compile(r"^type\s+(\w+)\s+struct\s*\{", re.MULTILINE)
        for m in struct_pattern.finditer(source):
            name = m.group(1)
            line_num = source[: m.start()].count("\n") + 1

            graph.add_symbol(
                Symbol(
                    name=name,
                    kind="class",
                    file=rel,
                    line=line_num,
                    column=0,
                    access="public" if name[0].isupper() else "private",
                    lines_spanned=1,
                )
            )

    def _extract_interfaces(self, source: str, rel: str, graph: CodeGraph) -> None:
        """Extract interface declarations."""
        iface_pattern = re.compile(r"^type\s+(\w+)\s+interface\s*\{", re.MULTILINE)
        for m in iface_pattern.finditer(source):
            name = m.group(1)
            line_num = source[: m.start()].count("\n") + 1

            graph.add_symbol(
                Symbol(
                    name=name,
                    kind="class",
                    file=rel,
                    line=line_num,
                    column=0,
                    access="public" if name[0].isupper() else "private",
                    lines_spanned=1,
                )
            )

    def _extract_imports(self, source: str, rel: str, graph: CodeGraph) -> None:
        """Extract import statements."""
        # Single imports: import "fmt"
        single_imports = re.findall(r'^import\s+"([^"]+)"', source, re.MULTILINE)
        for module in single_imports:
            graph.imports.append(
                ImportInfo(
                    source_file=rel,
                    module=module,
                    names=[],
                    is_relative=module.startswith("./") or module.startswith("../"),
                    line=source[: source.find(f'import "{module}"')].count("\n") + 1,
                    kind="import",
                )
            )

        # Block imports: import ( "fmt" "os" )
        block_pattern = re.compile(r"import\s*\(([^)]+)\)", re.MULTILINE | re.DOTALL)
        for m in block_pattern.finditer(source):
            block = m.group(1)
            for line in block.strip().split("\n"):
                line = line.strip().strip('"')
                if line and not line.startswith("//"):
                    graph.imports.append(
                        ImportInfo(
                            source_file=rel,
                            module=line,
                            names=[],
                            is_relative=line.startswith("./") or line.startswith("../"),
                            line=source[: m.start()].count("\n") + 1,
                            kind="import",
                        )
                    )

    def _extract_call_edges(self, source: str, rel: str, graph: CodeGraph) -> None:
        """Extract function/method call patterns."""
        call_pattern = re.compile(r"(\w+(?:\.\w+)*)\s*\(")
        keywords = {
            "if",
            "else",
            "for",
            "switch",
            "case",
            "return",
            "defer",
            "go",
            "select",
            "chan",
            "map",
            "make",
            "new",
            "append",
            "len",
            "cap",
            "close",
            "delete",
            "copy",
            "panic",
            "recover",
            "range",
        }
        for m in call_pattern.finditer(source):
            caller_key = f"{rel}:{source[: m.start()].count(chr(10)) + 1}"
            callee = m.group(1)
            if callee in keywords:
                continue
            graph.add_edge(
                CallEdge(
                    caller=caller_key,
                    callee=callee,
                    call_type="direct",
                    line=source[: m.start()].count("\n") + 1,
                )
            )

    def _extract_variables(self, source: str, rel: str, graph: CodeGraph) -> None:
        """Extract variable declarations."""
        var_patterns = [
            re.compile(r"^var\s+(\w+)\s+", re.MULTILINE),
            re.compile(r"^\s*(\w+)\s+(:=)\s+", re.MULTILINE),
        ]
        for pattern in var_patterns:
            for m in pattern.finditer(source):
                name = m.group(1)
                line_num = source[: m.start()].count("\n") + 1
                graph.add_symbol(
                    Symbol(
                        name=name,
                        kind="variable",
                        file=rel,
                        line=line_num,
                        column=0,
                        access="public" if name[0].isupper() else "private",
                    )
                )

    def _parse_go_params(self, params_str: str) -> list[str]:
        """Parse Go function parameters."""
        params = []
        if not params_str.strip():
            return params
        # Go params: name type, name type, ...
        for part in params_str.split(","):
            part = part.strip()
            if not part:
                continue
            parts = part.split()
            if parts:
                params.append(parts[0])
        return params

    def _build_signature(
        self, name: str, params: list[str], ret_type: str, is_async: bool
    ) -> str:
        """Build a human-readable function signature."""
        return f"{name}({', '.join(params)}{f' -> {ret_type}' if ret_type else ''})"
