"""Python parser using the standard library AST module.

Extracts functions, classes, methods, imports, decorators, and their
relationships from Python source files.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from pathlib import Path

from codegraph.graph import CallEdge, CodeGraph, ImportInfo, Symbol
from codegraph.utils import rel_path


@dataclass
class _Scope:
    """Tracks the current nesting scope for parent resolution."""
    name: str
    kind: str  # module, class, function
    parents: list[str] = field(default_factory=list)


class PythonParser:
    """Parse Python source files into a CodeGraph.

    Uses Python's built-in `ast` module — no external dependencies.
    """

    def __init__(self, root: Path):
        self.root = root

    def parse_file(self, filepath: Path, graph: CodeGraph) -> None:
        """Parse a single Python file and add its symbols to the graph.

        Args:
            filepath: Path to the Python file (absolute).
            graph: The CodeGraph to populate.
        """
        source = filepath.read_text(encoding="utf-8", errors="replace")
        try:
            tree = ast.parse(source, filename=str(filepath))
        except SyntaxError:
            return  # Skip files with syntax errors

        rel = rel_path(filepath, self.root)

        # Use a visitor that respects nesting order
        collector = _PythonSymbolCollector(rel, graph)
        collector.visit(tree)

        # Summary update
        self._update_summary(tree, graph)

    def _update_summary(self, tree: ast.Module, graph: CodeGraph) -> None:
        """Update summary counters for this file."""
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                graph.summary.total_functions += 1
            elif isinstance(node, ast.ClassDef):
                graph.summary.total_classes += 1
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                graph.summary.total_imports += 1


class _PythonSymbolCollector(ast.NodeVisitor):
    """AST visitor that collects symbols while respecting nesting scope."""

    def __init__(self, rel: str, graph: CodeGraph):
        self.rel = rel
        self.graph = graph
        self.scope_stack: list[_Scope] = [_Scope("<module>", "module", [])]

    # --- Module docstring ---
    def visit_Module(self, node: ast.Module) -> None:
        docstring = ast.get_docstring(node) or ""
        if docstring:
            self.graph.add_symbol(Symbol(
                name=Path(self.rel).stem,
                kind="module",
                file=self.rel,
                line=1,
                column=0,
                docstring=docstring,
                lines_spanned=1,
            ))
        self.generic_visit(node)

    # --- Classes ---
    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        parent_scope = self.scope_stack[-1]
        parents = list(parent_scope.parents)
        if parent_scope.kind == "class":
            parents.append(parent_scope.name)

        # Base classes
        bases = []
        for base in node.bases:
            try:
                bases.append(ast.unparse(base))
            except Exception:
                bases.append("?")

        sig = ", ".join(bases) if bases else ""
        docstring = ast.get_docstring(node) or ""
        end_line = getattr(node, "end_lineno", node.lineno) or node.lineno

        self.graph.add_symbol(Symbol(
            name=node.name,
            kind="class",
            file=self.rel,
            line=node.lineno,
            column=getattr(node, "col_offset", 0),
            signature=sig,
            docstring=docstring,
            access="public" if not node.name.startswith("_") else "private",
            parents=parents,
            lines_spanned=end_line - node.lineno + 1,
        ))

        # Push class scope before visiting children
        self.scope_stack.append(_Scope(node.name, "class", parents))
        self.generic_visit(node)
        self.scope_stack.pop()

    # --- Functions / Methods ---
    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._handle_function(node, is_async=False)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._handle_function(node, is_async=True)

    def _handle_function(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        is_async: bool,
    ) -> None:
        parent_scope = self.scope_stack[-1]
        parents = list(parent_scope.parents)
        if parent_scope.kind == "class":
            parents.append(parent_scope.name)

        is_method = parent_scope.kind == "class"
        is_static = any(
            isinstance(d, ast.Name) and d.id == "staticmethod"
            for d in node.decorator_list
        )
        is_property = any(
            isinstance(d, ast.Name) and d.id == "property"
            for d in node.decorator_list
        )

        # Determine access
        access = "public"
        if node.name.startswith("__") and node.name.endswith("__"):
            pass  # dunder = public
        elif node.name.startswith("__"):
            access = "private"
        elif node.name.startswith("_"):
            access = "protected"

        sig = self._build_signature(node, is_async)
        docstring = ast.get_docstring(node) or ""
        params = self._extract_params(node)
        ret_type = ast.unparse(node.returns) if node.returns else ""

        decorators = []
        for d in node.decorator_list:
            try:
                decorators.append(ast.unparse(d))
            except Exception:
                decorators.append("?")

        end_line = getattr(node, "end_lineno", node.lineno) or node.lineno

        self.graph.add_symbol(Symbol(
            name=node.name,
            kind="method" if is_method else "function",
            file=self.rel,
            line=node.lineno,
            column=getattr(node, "col_offset", 0),
            signature=sig,
            docstring=docstring,
            access=access,
            decorators=decorators,
            parents=parents,
            parameters=params,
            return_type=ret_type,
            is_async=is_async,
            is_static=is_static,
            is_property=is_property,
            lines_spanned=end_line - node.lineno + 1,
        ))

        # Push function scope before visiting children
        self.scope_stack.append(_Scope(node.name, "function", parents))
        self.generic_visit(node)
        self.scope_stack.pop()

    # --- Imports ---
    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self.graph.imports.append(ImportInfo(
                source_file=self.rel,
                module=alias.name,
                names=[alias.asname or alias.name],
                alias={alias.name: alias.asname} if alias.asname else {},
                is_relative=False,
                line=node.lineno,
                kind="import",
            ))
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        module = node.module or ""
        names = []
        alias = {}
        for alias_node in node.names:
            names.append(alias_node.asname or alias_node.name)
            if alias_node.asname:
                alias[alias_node.name] = alias_node.asname

        self.graph.imports.append(ImportInfo(
            source_file=self.rel,
            module=module,
            names=names,
            alias=alias,
            is_relative=node.level > 0,
            line=node.lineno,
            kind="from_import",
        ))
        self.generic_visit(node)

    # --- Call edges ---
    def visit_Call(self, node: ast.Call) -> None:
        caller_key = f"{self.rel}:{getattr(node, 'lineno', 0)}"
        callee_str = self._resolve_call_target(node.func)
        if callee_str:
            self.graph.add_edge(CallEdge(
                caller=caller_key,
                callee=callee_str,
                call_type="direct",
                line=getattr(node, "lineno", 0),
            ))
        self.generic_visit(node)

    # --- Variables (assignments) ---
    def visit_Assign(self, node: ast.Assign) -> None:
        for target in node.targets:
            if isinstance(target, ast.Name):
                doc = ""
                if isinstance(node.value, ast.Expr):
                    doc = ast.get_docstring(node.value) or ""
                self.graph.add_symbol(Symbol(
                    name=target.id,
                    kind="variable",
                    file=self.rel,
                    line=node.lineno,
                    column=getattr(node, "col_offset", 0),
                    docstring=doc,
                ))
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        if isinstance(node.target, ast.Name):
            self.graph.add_symbol(Symbol(
                name=node.target.id,
                kind="variable",
                file=self.rel,
                line=node.lineno,
                column=getattr(node, "col_offset", 0),
            ))
        self.generic_visit(node)

    # --- Decorators ---
    def visit_Decimal(self, node: ast.Expression) -> None:
        # Decorators at class/function level (already collected in
        # the FunctionDef/ClassDef handlers)
        self.generic_visit(node)

    # --- General expressions (catch all) ---
    def generic_visit(self, node: ast.AST) -> None:
        super().generic_visit(node)

    def _resolve_call_target(self, node: ast.expr) -> str | None:
        """Resolve a call expression to a string representation."""
        try:
            return ast.unparse(node)
        except Exception:
            return None

    def _build_signature(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        is_async: bool,
    ) -> str:
        """Build a human-readable function signature."""
        parts = []
        if is_async:
            parts.append("async ")

        parts.append(node.name)
        parts.append("(")

        args = node.args
        params = []

        # Positional-only args
        if hasattr(args, "posonlyargs"):
            for a in args.posonlyargs:
                params.append(self._format_param(a))

        # Regular args
        regular = list(args.args)

        for a in regular:
            params.append(self._format_param(a))

        # *args
        if args.vararg:
            params.append(f"*{self._format_param(args.vararg)}")

        # Keyword-only args
        for a in args.kwonlyargs:
            params.append(self._format_param(a))

        # **kwargs
        if args.kwarg:
            params.append(f"**{self._format_param(args.kwarg)}")

        parts.append(", ".join(params))
        parts.append(")")

        if node.returns:
            parts.append(f" -> {ast.unparse(node.returns)}")

        return "".join(parts)

    def _format_param(self, arg: ast.arg) -> str:
        """Format a single parameter."""
        s = arg.arg
        if arg.annotation:
            s += f": {ast.unparse(arg.annotation)}"
        return s

    def _extract_params(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[str]:
        """Extract parameter names for the symbol."""
        params = []
        args = node.args
        for a in args.posonlyargs if hasattr(args, "posonlyargs") else []:
            params.append(a.arg)
        for a in args.args:
            params.append(a.arg)
        if args.vararg:
            params.append(f"*{args.vararg.arg}")
        for a in args.kwonlyargs:
            params.append(a.arg)
        if args.kwarg:
            params.append(f"**{args.kwarg.arg}")
        return params
