"""Output formatters for CodeGraph."""

from __future__ import annotations


from codegraph.graph import CodeGraph


def format_markdown(graph: CodeGraph) -> str:
    """Format the graph as a human-readable Markdown document."""
    lines = []
    lines.append("# CodeGraph Analysis\n")
    lines.append(f"**Root:** `{graph.root_path}`\n")

    # Summary
    s = graph.summary
    lines.append("## Summary\n")
    lines.append("| Metric | Count |")
    lines.append("|--------|-------|")
    lines.append(f"| Total Symbols | {s.total_symbols} |")
    lines.append(f"| Total Files | {s.total_files} |")
    lines.append(f"| Functions | {s.total_functions} |")
    lines.append(f"| Classes | {s.total_classes} |")
    lines.append(f"| Imports | {s.total_imports} |")
    lines.append(f"| Call Edges | {s.total_edges} |")
    lines.append("")

    # Symbols by type
    symbols_by_kind: dict[str, list] = {}
    for sym in graph.symbols.values():
        symbols_by_kind.setdefault(sym.kind, []).append(sym)

    KIND_LABELS = {
        "class": "Classes",
        "function": "Functions",
        "method": "Methods",
        "module": "Modules",
        "import": "Imports",
        "variable": "Variables",
        "decorator": "Decorators",
    }
    for kind in ["class", "function", "method", "module", "import", "variable"]:
        items = symbols_by_kind.get(kind, [])
        if not items:
            continue
        lines.append(f"## {KIND_LABELS[kind]} ({len(items)})\n")
        for sym in sorted(items, key=lambda s: (s.file, s.line)):
            lines.append(f"### `{sym.name}` — `{sym.file}:{sym.line}`")
            if sym.signature:
                lines.append(f"```python\n{sym.signature}\n```")
            if sym.docstring:
                lines.append(f"\n{sym.docstring[:200]}")
            if sym.decorators:
                lines.append(f"\n**Decorators:** {', '.join(sym.decorators)}")
            if sym.parameters:
                lines.append(f"\n**Parameters:** {', '.join(sym.parameters)}")
            if sym.return_type:
                lines.append(f"\n**Returns:** `{sym.return_type}`")
            if sym.access != "public":
                lines.append(f"\n**Access:** {sym.access}")
            if sym.parents:
                lines.append(f"\n**Scope:** {' -> '.join(sym.parents)}")
            lines.append("")

    # Imports
    if graph.imports:
        lines.append("## Imports\n")
        for imp in sorted(graph.imports, key=lambda i: (i.source_file, i.line)):
            names = ", ".join(imp.names)
            if imp.kind == "import":
                lines.append(f"- `{imp.source_file}:{imp.line}`: `import {imp.module}`")
            else:
                lines.append(f"- `{imp.source_file}:{imp.line}`: `from {imp.module} import {names}`")
        lines.append("")

    # Call edges
    if graph.edges:
        lines.append("## Call Edges\n")
        lines.append("| Caller | Callee | Type |")
        lines.append("|--------|--------|------|")
        for edge in graph.edges[:100]:  # Limit output
            lines.append(f"| `{edge.caller}` | `{edge.callee}` | {edge.call_type} |")
        if len(graph.edges) > 100:
            lines.append(f"\n*... and {len(graph.edges) - 100} more edges*")
        lines.append("")

    return "\n".join(lines)


def format_stats(graph: CodeGraph) -> str:
    """Format a simple stats output."""
    s = graph.summary
    lines = [
        "CodeGraph Statistics",
        f"{'=' * 40}",
        f"Root: {graph.root_path}",
        "",
        f"Total files:    {s.total_files}",
        f"Total symbols:  {s.total_symbols}",
        f"Functions:      {s.total_functions}",
        f"Classes:        {s.total_classes}",
        f"Imports:        {s.total_imports}",
        f"Call edges:     {s.total_edges}",
        "",
    ]
    if s.languages:
        lines.append("Languages:")
        for lang, count in sorted(s.languages.items()):
            lines.append(f"  {lang}: {count} files")
        lines.append("")
    return "\n".join(lines)
