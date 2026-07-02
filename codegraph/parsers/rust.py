"""Rust parser using regex-based extraction.

Extracts functions, methods, structs, enums, traits, and their
relationships from Rust source files. Uses regex patterns for
parsing — no external dependencies.
"""

from __future__ import annotations

import re
from pathlib import Path

from codegraph.graph import CallEdge, CodeGraph, ImportInfo, Symbol
from codegraph.utils import rel_path


class RustParser:
    """Parse Rust source files into a CodeGraph.

    Uses regex-based extraction — no external dependencies.
    """

    def __init__(self, root: Path):
        self.root = root

    def parse_file(self, filepath: Path, graph: CodeGraph) -> None:
        """Parse a single Rust file and add its symbols to the graph."""
        source = filepath.read_text(encoding="utf-8", errors="replace")
        rel = rel_path(filepath, self.root)

        self._extract_functions(source, rel, graph)
        self._extract_methods(source, rel, graph)
        self._extract_structs(source, rel, graph)
        self._extract_enums(source, rel, graph)
        self._extract_traits(source, rel, graph)
        self._extract_imports(source, rel, graph)
        self._extract_call_edges(source, rel, graph)
        self._extract_variables(source, rel, graph)

    def _extract_functions(self, source: str, rel: str, graph: CodeGraph) -> None:
        """Extract free function declarations."""
        func_pattern = re.compile(
            r"^\s*(pub\s+)?(?:async\s+)?fn\s+(?:<[^>]*>\s+)?(\w+)\s*\(([^)]*)\)"
            r"(?:\s*->\s*([^\{]+))?\s*\{?",
            re.MULTILINE,
        )
        for m in func_pattern.finditer(source):
            is_pub = m.group(1) is not None
            name = m.group(2)
            params_str = m.group(3).strip()
            ret_type = m.group(4).strip() if m.group(4) else ""

            params = self._parse_rust_params(params_str)
            line_num = source[: m.start()].count("\n") + 1

            # Skip main if it has no params (it's a convention, not a real function)
            sig = f"{name}({', '.join(params)}{f' -> {ret_type}' if ret_type else ''})"

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
                    access="public" if is_pub else "private",
                    lines_spanned=1,
                )
            )

    def _extract_methods(self, source: str, rel: str, graph: CodeGraph) -> None:
        """Extract method declarations (impl blocks)."""
        lines = source.split("\n")
        in_impl = False
        brace_depth = 0
        impl_start_line = 0

        for i, line in enumerate(lines):
            stripped = line.strip()
            # Detect impl block start
            if not in_impl and re.match(r"^impl\s+", stripped):
                in_impl = True
                brace_depth = stripped.count("{") - stripped.count("}")
                impl_start_line = i
                continue
            if in_impl:
                brace_depth += stripped.count("{") - stripped.count("}")

                # Check for fn inside impl body (not the impl line itself)
                if brace_depth > 0:
                    func_match = re.match(
                        r"^\s*(?:pub\s+)?(?:async\s+)?fn\s+(?:<[^>]*>\s+)?(\w+)\s*\(([^)]*)\)"
                        r"(?:\s*->\s*([^\{]+))?\s*\{?",
                        line,
                    )
                    if func_match:
                        name = func_match.group(1)
                        params_str = func_match.group(2).strip()
                        ret_type = (
                            func_match.group(3).strip() if func_match.group(3) else ""
                        )

                        params = self._parse_rust_params(params_str)
                        line_num = i + 1

                        sig = f"{name}({', '.join(params)}{f' -> {ret_type}' if ret_type else ''})"

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
                                access="public",
                                lines_spanned=1,
                            )
                        )

                # End of impl block
                if brace_depth == 0 and i > impl_start_line:
                    in_impl = False

    def _extract_structs(self, source: str, rel: str, graph: CodeGraph) -> None:
        """Extract struct declarations."""
        struct_pattern = re.compile(
            r"^\s*(pub\s+)?struct\s+(\w+)(?:\s*<[^>]*>)?\s*\{", re.MULTILINE
        )
        for m in struct_pattern.finditer(source):
            name = m.group(2)
            is_pub = m.group(1) is not None
            line_num = source[: m.start()].count("\n") + 1

            graph.add_symbol(
                Symbol(
                    name=name,
                    kind="class",
                    file=rel,
                    line=line_num,
                    column=0,
                    access="public" if is_pub else "private",
                    lines_spanned=1,
                )
            )

    def _extract_enums(self, source: str, rel: str, graph: CodeGraph) -> None:
        """Extract enum declarations."""
        enum_pattern = re.compile(
            r"^\s*(pub\s+)?enum\s+(\w+)(?:\s*<[^>]*>)?\s*\{", re.MULTILINE
        )
        for m in enum_pattern.finditer(source):
            name = m.group(2)
            is_pub = m.group(1) is not None
            line_num = source[: m.start()].count("\n") + 1

            graph.add_symbol(
                Symbol(
                    name=name,
                    kind="class",
                    file=rel,
                    line=line_num,
                    column=0,
                    access="public" if is_pub else "private",
                    lines_spanned=1,
                )
            )

    def _extract_traits(self, source: str, rel: str, graph: CodeGraph) -> None:
        """Extract trait declarations."""
        trait_pattern = re.compile(
            r"^\s*(pub\s+)?trait\s+(\w+)(?:\s*<[^>]*>)?\s*\{", re.MULTILINE
        )
        for m in trait_pattern.finditer(source):
            name = m.group(2)
            is_pub = m.group(1) is not None
            line_num = source[: m.start()].count("\n") + 1

            graph.add_symbol(
                Symbol(
                    name=name,
                    kind="class",
                    file=rel,
                    line=line_num,
                    column=0,
                    access="public" if is_pub else "private",
                    lines_spanned=1,
                )
            )

    def _extract_imports(self, source: str, rel: str, graph: CodeGraph) -> None:
        """Extract use/import statements."""
        # use std::collections::HashMap;
        use_pattern = re.compile(r"^\s*use\s+([\w:\{\}\s,*]+)\s*;", re.MULTILINE)
        for m in use_pattern.finditer(source):
            path_str = m.group(1).strip()
            line_num = source[: m.start()].count("\n") + 1

            # Parse the import path
            if "{" in path_str:
                # Re-export style: use std::{collections::HashMap, io::Write};
                parts = path_str.split("{")[0].strip().rstrip(":")
                graph.imports.append(
                    ImportInfo(
                        source_file=rel,
                        module=parts,
                        names=[],
                        is_relative=False,
                        line=line_num,
                        kind="use",
                    )
                )
            else:
                parts = path_str.strip().rstrip(",").split("::")
                graph.imports.append(
                    ImportInfo(
                        source_file=rel,
                        module=path_str.strip(),
                        names=[],
                        is_relative=False,
                        line=line_num,
                        kind="use",
                    )
                )

        # #[path = "..."] and include! macro calls
        include_pattern = re.compile(r'include!\s*\(\s*"([^"]+)"\s*\)', re.MULTILINE)
        for m in include_pattern.finditer(source):
            module = m.group(1)
            line_num = source[: m.start()].count("\n") + 1
            graph.imports.append(
                ImportInfo(
                    source_file=rel,
                    module=module,
                    names=[],
                    is_relative=module.startswith("./") or module.startswith("../"),
                    line=line_num,
                    kind="include",
                )
            )

    def _extract_call_edges(self, source: str, rel: str, graph: CodeGraph) -> None:
        """Extract function/method call patterns."""
        call_pattern = re.compile(r"(\w+(?:\.\w+)*)\s*\(")
        keywords = {
            "if",
            "else",
            "for",
            "while",
            "loop",
            "match",
            "return",
            "ref",
            "let",
            "const",
            "static",
            "type",
            "impl",
            "trait",
            "struct",
            "enum",
            "fn",
            "use",
            "mod",
            "pub",
            "async",
            "await",
            "do",
            "dyn",
            "self",
            "super",
            "crate",
            "where",
            "unsafe",
            "mut",
            "move",
            "box",
            "break",
            "continue",
        }
        for m in call_pattern.finditer(source):
            caller_key = f"{rel}:{source[: m.start()].count(chr(10)) + 1}"
            callee = m.group(1)
            if callee in keywords or callee in (
                "Some",
                "None",
                "Ok",
                "Err",
                "Result",
                "Option",
            ):
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
            re.compile(r"^\s*let\s+(?:mut\s+)?(\w+)\s*=", re.MULTILINE),
            re.compile(r"^\s*const\s+(\w+)\s*:", re.MULTILINE),
            re.compile(r"^\s*static\s+(?:mut\s+)?(\w+)\s*:", re.MULTILINE),
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
                        access="public",
                    )
                )

    def _parse_rust_params(self, params_str: str) -> list[str]:
        """Parse Rust function parameters."""
        params = []
        if not params_str.strip():
            return params

        for part in params_str.split(","):
            part = part.strip()
            if not part:
                continue
            # Rust params: &self, mut x: Type, y: Type, etc.
            tokens = part.split()
            if tokens:
                # Skip self, &mut, & references
                name_tokens = []
                for t in tokens:
                    if t in ("self", "&", "&mut", "mut"):
                        continue
                    # If first token after removing self/refs, take it as name
                    name_tokens.append(t)
                    break
                if name_tokens:
                    params.append(name_tokens[0])

        return params
