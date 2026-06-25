"""JavaScript/TypeScript parser using regex-based extraction.

Extracts functions, classes, methods, exports, imports, and their
relationships from JS/TS source files. Uses regex patterns for
parsing — no external dependencies.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from codegraph.graph import CallEdge, CodeGraph, ImportInfo, Symbol
from codegraph.utils import rel_path


@dataclass
class _Scope:
    """Tracks the current nesting scope for parent resolution."""
    name: str
    kind: str  # module, class, function, block


class JavaScriptParser:
    """Parse JavaScript/TypeScript source files into a CodeGraph.

    Uses regex-based extraction — no external dependencies.
    Supports .js, .mjs, .cjs, .ts, .tsx, .mts, .cts files.
    """

    def __init__(self, root: Path):
        self.root = root

    def parse_file(self, filepath: Path, graph: CodeGraph) -> None:
        """Parse a single JS/TS file and add its symbols to the graph.

        Args:
            filepath: Path to the file (absolute).
            graph: The CodeGraph to populate.
        """
        source = filepath.read_text(encoding="utf-8", errors="replace")
        rel = rel_path(filepath, self.root)

        # Extract all symbols
        self._extract_functions(source, rel, graph)
        self._extract_classes(source, rel, graph)
        self._extract_exports(source, rel, graph)
        self._extract_imports(source, rel, graph)
        self._extract_call_edges(source, rel, graph)
        # Variables last so arrow functions are not overwritten
        self._extract_variables(source, rel, graph)

    def _extract_functions(
        self, source: str, rel: str, graph: CodeGraph
    ) -> None:
        """Extract function declarations, arrow functions, and methods."""
        lines = source.split("\n")

        # Function declarations: function name(...)
        func_pattern = re.compile(
            r'^(?:export\s+)?(?:async\s+)?function\s+(\w+)\s*\(([^)]*)\)'
            r'(?:\s*:\s*[\w<>\[\],\s|&?]+)?\s*\{?',
            re.MULTILINE
        )
        for m in func_pattern.finditer(source):
            name = m.group(1)
            params_str = m.group(2).strip()
            line_num = source[:m.start()].count("\n") + 1
            params = [p.strip().split(":")[0].split("=")[0].strip()
                      for p in params_str.split(",") if p.strip()]
            ret_type = ""
            # Try to find return type annotation
            ret_match = re.search(
                rf'function\s+{re.escape(name)}\s*\([^)]*\)\s*:\s*([\w<>\[\],\s|&?]+)\s*\{{?',
                source[m.start():]
            )
            if ret_match:
                ret_type = ret_match.group(1).strip()

            is_async = "async" in source[m.start():m.start()+50].split("function")[0]
            sig = self._build_signature(name, params, ret_type, is_async)

            graph.add_symbol(Symbol(
                name=name,
                kind="function",
                file=rel,
                line=line_num,
                column=0,
                signature=sig,
                parameters=params,
                return_type=ret_type,
                is_async=is_async,
                access="public",
                lines_spanned=1,
            ))

        # Arrow functions: const/let/var name = (...) => or name = async (...) =>
        arrow_pattern = re.compile(
            r'^(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=\s*'
            r'(?:async\s+)?(?:\(([^)]*)\)|(\w+))\s*=>',
            re.MULTILINE | re.UNICODE
        )
        for m in arrow_pattern.finditer(source):
            name = m.group(1)
            params_str = m.group(2) or m.group(3) or ""
            line_num = source[:m.start()].count("\n") + 1
            params = [p.strip().split(":")[0].split("=")[0].strip()
                      for p in params_str.split(",") if p.strip()]
            is_async = "async" in source[m.start():m.start()+60]

            # Check for return type
            ret_type = ""
            ret_match = re.search(
                rf'{re.escape(name)}\s*=\s*async\s*\([^)]*\)\s*:\s*([\w<>\[\],\s|&?]+)\s*=>',
                source[m.start():]
            )
            if not ret_match:
                ret_match = re.search(
                    rf'{re.escape(name)}\s*=\s*\([^)]*\)\s*:\s*([\w<>\[\],\s|&?]+)\s*=>',
                    source[m.start():]
                )
            if ret_match:
                ret_type = ret_match.group(1).strip()

            sig = self._build_signature(name, params, ret_type, is_async)

            graph.add_symbol(Symbol(
                name=name,
                kind="function",
                file=rel,
                line=line_num,
                column=0,
                signature=sig,
                parameters=params,
                return_type=ret_type,
                is_async=is_async,
                access="public",
                lines_spanned=1,
            ))

    def _extract_classes(self, source: str, rel: str, graph: CodeGraph) -> None:
        """Extract class declarations and interfaces."""
        lines = source.split("\n")

        # Class declarations
        class_pattern = re.compile(
            r'^(?:export\s+)?(?:default\s+)?class\s+(\w+)'
            r'(?:\s+extends\s+(\w+))?'
            r'(?:\s+implements\s+([\w,\s]+))?'
            r'\s*\{?',
            re.MULTILINE
        )
        for m in class_pattern.finditer(source):
            name = m.group(1)
            extends = m.group(2) or ""
            implements = m.group(3) or ""
            bases = []
            if extends:
                bases.append(extends)
            if implements:
                bases.extend(implements.split(","))
            sig = ", ".join(bases) if bases else ""
            line_num = source[:m.start()].count("\n") + 1

            graph.add_symbol(Symbol(
                name=name,
                kind="class",
                file=rel,
                line=line_num,
                column=0,
                signature=sig,
                access="public",
                lines_spanned=1,
            ))

        # Methods inside classes
        method_pattern = re.compile(
            r'^\s*(?:static\s+)?(?:async\s+)?'
            r'(?:constructor|\w+)\s*\(([^)]*)\)',
            re.MULTILINE
        )
        for m in method_pattern.finditer(source):
            line_num = source[:m.start()].count("\n") + 1
            # Get actual line content from the match (skip leading whitespace/newline)
            match_text = m.group(0).lstrip("\n").lstrip()
            method_name_match = re.search(
                r'(?:static\s+)?(?:async\s+)?(\w+)\s*\(', match_text
            )
            if not method_name_match:
                continue
            method_name = method_name_match.group(1)

            params_str = m.group(1).strip()
            params = [p.strip().split(":")[0].split("=")[0].strip()
                      for p in params_str.split(",") if p.strip()]
            is_async = "async" in match_text
            is_static = "static" in match_text

            # Check for return type
            ret_type = ""
            ret_match = re.search(
                rf'{re.escape(method_name)}\s*\([^)]*\)\s*:\s*([\w<>\[\],\s|&?]+)\s*\{{?',
                match_text
            )
            if ret_match:
                ret_type = ret_match.group(1).strip()

            sig = self._build_signature(method_name, params, ret_type, is_async)

            graph.add_symbol(Symbol(
                name=method_name,
                kind="method",
                file=rel,
                line=line_num,
                column=0,
                signature=sig,
                parameters=params,
                return_type=ret_type,
                is_async=is_async,
                is_static=is_static,
                access="public",
                lines_spanned=1,
            ))

    def _extract_exports(self, source: str, rel: str, graph: CodeGraph) -> None:
        """Extract export statements."""
        # Named exports: export { name1, name2 }
        named_exports = re.findall(
            r'export\s+\{([^}]+)\}', source
        )
        for group in named_exports:
            for name in group.split(","):
                name = name.strip().split(" as ")[0].strip()
                if name:
                    line_num = source[:source.find(f"export {{")].count("\n") + 1
                    graph.add_symbol(Symbol(
                        name=name,
                        kind="function",
                        file=rel,
                        line=line_num,
                        column=0,
                        access="public",
                    ))

        # Default exports
        default_match = re.search(
            r'export\s+default\s+(?:class|function|const|let|var)\s+(\w+)',
            source
        )
        if default_match:
            name = default_match.group(1)
            line_num = source[:default_match.start()].count("\n") + 1
            graph.add_symbol(Symbol(
                name=f"default {name}",
                kind="function",
                file=rel,
                line=line_num,
                column=0,
                access="public",
            ))

    def _extract_imports(self, source: str, rel: str, graph: CodeGraph) -> None:
        """Extract import statements."""
        # import ... from '...'
        # Match: import default from 'mod'
        default_import_pattern = re.compile(
            r"import\s+(\w+)\s+from\s+['\"]([^'\"]+)['\"]",
            re.MULTILINE
        )
        for m in default_import_pattern.finditer(source):
            default_import = m.group(1)
            module = m.group(2)
            graph.imports.append(ImportInfo(
                source_file=rel,
                module=module,
                names=[default_import],
                alias={},
                is_relative=module.startswith("."),
                line=source[:m.start()].count("\n") + 1,
                kind="from_import",
            ))

        # Match: import { named1, named2 } from 'mod'
        named_import_pattern = re.compile(
            r"import\s*\{([^}]+)\}\s+from\s+['\"]([^'\"]+)['\"]",
            re.MULTILINE
        )
        for m in named_import_pattern.finditer(source):
            named_imports_str = m.group(1)
            module = m.group(2)

            names = []
            alias = {}
            for imp in named_imports_str.split(","):
                imp = imp.strip()
                if " as " in imp:
                    orig, as_name = imp.split(" as ")
                    alias[orig.strip()] = as_name.strip()
                    names.append(as_name.strip())
                elif imp:
                    names.append(imp)

            graph.imports.append(ImportInfo(
                source_file=rel,
                module=module,
                names=names,
                alias=alias,
                is_relative=module.startswith("."),
                line=source[:m.start()].count("\n") + 1,
                kind="from_import",
            ))

        # import 'module' (side-effect imports)
        side_effect = re.findall(
            r"import\s+['\"]([^'\"]+)['\"]", source
        )
        for module in side_effect:
            line_num = source[:source.find(f"import '{module}'")].count("\n") + 1
            graph.imports.append(ImportInfo(
                source_file=rel,
                module=module,
                names=[],
                is_relative=module.startswith("."),
                line=line_num,
                kind="import",
            ))

    def _extract_call_edges(self, source: str, rel: str, graph: CodeGraph) -> None:
        """Extract function/method call patterns."""
        lines = source.split("\n")
        # Find all function calls: identifier(...)
        call_pattern = re.compile(r'(\w+(?:\.\w+)*)\s*\(')
        for m in call_pattern.finditer(source):
            caller_key = f"{rel}:{source[:m.start()].count(chr(10)) + 1}"
            callee = m.group(1)
            # Skip keywords and common non-function identifiers
            if callee in ("if", "else", "for", "while", "switch", "catch",
                          "return", "new", "typeof", "instanceof", "delete",
                          "void", "await", "import", "export", "require"):
                continue
            graph.add_edge(CallEdge(
                caller=caller_key,
                callee=callee,
                call_type="direct",
                line=source[:m.start()].count("\n") + 1,
            ))

    def _extract_variables(self, source: str, rel: str, graph: CodeGraph) -> None:
        """Extract variable declarations.

        Skips lines that already have a function/arrow-function symbol
        so that `const fn = () => {}` is classified as a function, not a variable.
        """
        # Collect existing symbol line keys to avoid overwriting
        existing_lines = {
            (sym.file, sym.line) for sym in graph.symbols.values()
        }

        var_pattern = re.compile(
            r'^(?:export\s+)?(?:const|let|var)\s+(\w+)\s*=',
            re.MULTILINE
        )
        for m in var_pattern.finditer(source):
            name = m.group(1)
            line_num = source[:m.start()].count("\n") + 1
            key = (rel, line_num)
            if key in existing_lines:
                continue
            graph.add_symbol(Symbol(
                name=name,
                kind="variable",
                file=rel,
                line=line_num,
                column=0,
                access="public",
            ))

    def _build_signature(
        self, name: str, params: list[str],
        ret_type: str, is_async: bool
    ) -> str:
        """Build a human-readable function signature."""
        parts = []
        if is_async:
            parts.append("async ")
        parts.append(name)
        parts.append("(")
        parts.append(", ".join(params))
        parts.append(")")
        if ret_type:
            parts.append(f" -> {ret_type}")
        return "".join(parts)
