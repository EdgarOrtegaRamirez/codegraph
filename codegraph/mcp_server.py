"""MCP Server for CodeGraph.

Exposes the code knowledge graph via the Model Context Protocol,
allowing AI coding agents to search, explore, and query codebases
through standard MCP tools.

Usage:
    python -m codegraph.mcp_server
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import anyio

import mcp.server.stdio
from mcp.server import Server
from mcp.types import (
    Tool,
    TextContent,
    ImageContent,
    EmbeddedResource,
)

from codegraph.indexer import Indexer
from codegraph.incremental import IncrementalIndexer
from codegraph.resolve import GraphQuery
from codegraph.output import format_markdown, format_stats


class CodeGraphServer:
    """MCP server that exposes CodeGraph as tools."""

    def __init__(self, name: str = "codegraph", cache_dir: str | None = None):
        self.server = Server(name)
        self.cache_dir = cache_dir
        self._register_tools()

    def _register_tools(self) -> None:
        """Register all MCP tools."""

        @self.server.list_tools()
        async def list_tools() -> list[Tool]:
            return [
                Tool(
                    name="codegraph_index",
                    description=(
                        "Index a codebase into a knowledge graph. "
                        "Scans all supported source files (Python, JS/TS, Go, Rust), "
                        "extracts functions, classes, imports, and call edges. "
                        "Returns graph summary statistics."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "path": {
                                "type": "string",
                                "description": "Path to the codebase to index.",
                            },
                            "include": {
                                "type": "string",
                                "description": (
                                    "Comma-separated file extensions to include "
                                    "(e.g., '*.py,*.ts')"
                                ),
                            },
                            "incremental": {
                                "type": "boolean",
                                "description": (
                                    "Use incremental indexing with cache. "
                                    "Defaults to full index."
                                ),
                            },
                        },
                        "required": ["path"],
                    },
                ),
                Tool(
                    name="codegraph_search",
                    description=(
                        "Search codebase symbols by name or docstring. "
                        "Returns matching functions, classes, methods, etc. "
                        "Useful for finding specific code elements."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "path": {
                                "type": "string",
                                "description": "Path to the indexed codebase.",
                            },
                            "query": {
                                "type": "string",
                                "description": "Search term (matches name and docstring).",
                            },
                            "kind": {
                                "type": "string",
                                "enum": [
                                    "function",
                                    "method",
                                    "class",
                                    "variable",
                                    "module",
                                ],
                                "description": "Filter by symbol kind.",
                            },
                        },
                        "required": ["path", "query"],
                    },
                ),
                Tool(
                    name="codegraph_get_symbol",
                    description=(
                        "Get a specific symbol by file path and line number. "
                        "Returns full symbol details including signature, "
                        "docstring, parameters, and return type."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "path": {
                                "type": "string",
                                "description": "Path to the codebase.",
                            },
                            "file": {
                                "type": "string",
                                "description": (
                                    "Relative file path within the codebase."
                                ),
                            },
                            "line": {
                                "type": "integer",
                                "description": "Line number (1-indexed).",
                            },
                        },
                        "required": ["path", "file", "line"],
                    },
                ),
                Tool(
                    name="codegraph_get_functions",
                    description=(
                        "List all functions and methods in the codebase. "
                        "Optionally filter by file path."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "path": {
                                "type": "string",
                                "description": "Path to the codebase.",
                            },
                            "file": {
                                "type": "string",
                                "description": ("Optional file path to filter by."),
                            },
                        },
                        "required": ["path"],
                    },
                ),
                Tool(
                    name="codegraph_get_classes",
                    description=(
                        "List all classes, structs, and interfaces. "
                        "Optionally filter by file path."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "path": {
                                "type": "string",
                                "description": "Path to the codebase.",
                            },
                            "file": {
                                "type": "string",
                                "description": ("Optional file path to filter by."),
                            },
                        },
                        "required": ["path"],
                    },
                ),
                Tool(
                    name="codegraph_get_imports",
                    description=(
                        "Get all import statements for a specific file. "
                        "Shows which modules are imported and on which lines."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "path": {
                                "type": "string",
                                "description": "Path to the codebase.",
                            },
                            "file": {
                                "type": "string",
                                "description": ("Relative file path to query."),
                            },
                        },
                        "required": ["path", "file"],
                    },
                ),
                Tool(
                    name="codegraph_get_call_graph",
                    description=(
                        "Get the call graph for a symbol at a given location. "
                        "Shows what functions/methods this symbol calls, "
                        "recursively to a given depth. "
                        "Symbol key format: 'file.py:line' (e.g., 'main.py:42')."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "path": {
                                "type": "string",
                                "description": "Path to the codebase.",
                            },
                            "symbol_key": {
                                "type": "string",
                                "description": (
                                    "Symbol key in format 'file.py:line' "
                                    "(e.g., 'main.py:42')."
                                ),
                            },
                            "depth": {
                                "type": "integer",
                                "description": (
                                    "How many levels deep to traverse (default: 2)."
                                ),
                                "default": 2,
                            },
                        },
                        "required": ["path", "symbol_key"],
                    },
                ),
                Tool(
                    name="codegraph_get_dependencies",
                    description=(
                        "Get file-level dependencies and dependents. "
                        "Shows which files a given file imports, "
                        "and which files import it."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "path": {
                                "type": "string",
                                "description": "Path to the codebase.",
                            },
                            "file": {
                                "type": "string",
                                "description": ("Relative file path to analyze."),
                            },
                        },
                        "required": ["path", "file"],
                    },
                ),
                Tool(
                    name="codegraph_summary",
                    description=(
                        "Get a high-level summary of the codebase. "
                        "Returns counts of files, symbols, functions, "
                        "classes, imports, call edges, and language breakdown."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "path": {
                                "type": "string",
                                "description": "Path to the codebase.",
                            },
                        },
                        "required": ["path"],
                    },
                ),
                Tool(
                    name="codegraph_markdown_report",
                    description=(
                        "Generate a human-readable Markdown report "
                        "of the codebase structure. Includes all symbols, "
                        "imports, and call edges in a readable format."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "path": {
                                "type": "string",
                                "description": "Path to the codebase.",
                            },
                        },
                        "required": ["path"],
                    },
                ),
            ]

        @self.server.call_tool()
        async def handle_tool(
            name: str, arguments: dict[str, Any] | None
        ) -> list[TextContent | ImageContent | EmbeddedResource]:
            if arguments is None:
                arguments = {}

            handler_map = {
                "codegraph_index": self._handle_index,
                "codegraph_search": self._handle_search,
                "codegraph_get_symbol": self._handle_get_symbol,
                "codegraph_get_functions": self._handle_get_functions,
                "codegraph_get_classes": self._handle_get_classes,
                "codegraph_get_imports": self._handle_get_imports,
                "codegraph_get_call_graph": self._handle_get_call_graph,
                "codegraph_get_dependencies": self._handle_get_dependencies,
                "codegraph_summary": self._handle_summary,
                "codegraph_markdown_report": self._handle_markdown_report,
            }

            handler = handler_map.get(name)
            if handler is None:
                raise ValueError(f"Unknown tool: {name}")
            return handler(arguments)

    def _load_graph(self, path: str | Path) -> tuple[GraphQuery, Indexer]:
        """Load the graph and build query API."""
        target = Path(path).resolve()
        indexer = Indexer(target)
        graph = indexer.index()
        query_api = GraphQuery(graph)
        return query_api, indexer

    def _load_incremental(
        self, path: str | Path
    ) -> tuple[GraphQuery, IncrementalIndexer]:
        """Load graph with incremental indexing."""
        target = Path(path).resolve()
        indexer = IncrementalIndexer(target, cache_dir=self.cache_dir)
        graph = indexer.index()
        query_api = GraphQuery(graph)
        return query_api, indexer

    def _handle_index(self, args: dict) -> list[TextContent]:
        path = args.get("path", ".")
        include = args.get("include")
        incremental = args.get("incremental", False)

        extensions = None
        if include:
            extensions = set(include.split(","))

        if incremental:
            query_api, _ = self._load_incremental(path)
        elif extensions:
            target = Path(path).resolve()
            idx = Indexer(target, extensions=extensions)
            graph = idx.index()
            query_api = GraphQuery(graph)
        else:
            query_api, _ = self._load_graph(path)

        return [
            TextContent(
                type="text",
                text=f"Indexed codebase at {path}:\n{format_stats(query_api.graph)}",
            )
        ]

    def _handle_search(self, args: dict) -> list[TextContent]:
        path = args["path"]
        query = args["query"]
        kind = args.get("kind")

        query_api, _ = self._load_graph(path)
        results = query_api.search(query, kind=kind)

        if not results:
            return [
                TextContent(
                    type="text",
                    text=f"No symbols found matching '{query}'",
                )
            ]

        output_lines = [f"Found {len(results)} results for '{query}':"]
        for r in results:
            output_lines.append(
                f"  - {r['name']} ({r['kind']}) in {r['file']}:{r['line']}"
            )
            if r.get("signature"):
                output_lines.append(f"    Signature: {r['signature']}")
            if r.get("docstring"):
                output_lines.append(f"    Doc: {r['docstring'][:200]}")

        return [TextContent(type="text", text="\n".join(output_lines))]

    def _handle_get_symbol(self, args: dict) -> list[TextContent]:
        path = args["path"]
        file_path = args["file"]
        line = args["line"]

        query_api, _ = self._load_graph(path)
        symbol = query_api.get_symbol(file_path, line)

        if symbol is None:
            return [
                TextContent(
                    type="text",
                    text=f"No symbol found at {file_path}:{line}",
                )
            ]

        lines = [
            f"Symbol: {symbol['name']}",
            f"  Kind: {symbol['kind']}",
            f"  Location: {file_path}:{line}",
        ]
        if symbol.get("signature"):
            lines.append(f"  Signature: {symbol['signature']}")
        if symbol.get("docstring"):
            lines.append(f"  Docstring: {symbol['docstring']}")
        if symbol.get("parameters"):
            lines.append(f"  Parameters: {', '.join(symbol['parameters'])}")
        if symbol.get("return_type"):
            lines.append(f"  Return type: {symbol['return_type']}")
        if symbol.get("decorators"):
            lines.append(f"  Decorators: {', '.join(symbol['decorators'])}")
        if symbol.get("access") != "public":
            lines.append(f"  Access: {symbol['access']}")

        return [TextContent(type="text", text="\n".join(lines))]

    def _handle_get_functions(self, args: dict) -> list[TextContent]:
        path = args["path"]
        file_filter = args.get("file")

        query_api, _ = self._load_graph(path)
        functions = query_api.get_functions(file_filter)

        if not functions:
            return [
                TextContent(
                    type="text",
                    text="No functions found.",
                )
            ]

        output_lines = [f"Found {len(functions)} functions:"]
        for f in functions:
            output_lines.append(
                f"  - {f['name']} ({f['kind']}) in {f['file']}:{f['line']}"
            )

        return [TextContent(type="text", text="\n".join(output_lines))]

    def _handle_get_classes(self, args: dict) -> list[TextContent]:
        path = args["path"]
        file_filter = args.get("file")

        query_api, _ = self._load_graph(path)
        classes = query_api.get_classes(file_filter)

        if not classes:
            return [
                TextContent(
                    type="text",
                    text="No classes found.",
                )
            ]

        output_lines = [f"Found {len(classes)} classes/structs:"]
        for c in classes:
            output_lines.append(f"  - {c['name']} in {c['file']}:{c['line']}")

        return [TextContent(type="text", text="\n".join(output_lines))]

    def _handle_get_imports(self, args: dict) -> list[TextContent]:
        path = args["path"]
        file_path = args["file"]

        query_api, _ = self._load_graph(path)
        imports = query_api.get_imports(file_path)

        if not imports:
            return [
                TextContent(
                    type="text",
                    text=f"No imports found in {file_path}",
                )
            ]

        output_lines = [f"Imports in {file_path} ({len(imports)} total):"]
        for imp in imports:
            names = ", ".join(imp.get("names", []))
            if names:
                output_lines.append(
                    f"  - from {imp['module']} import {names} (line {imp['line']})"
                )
            else:
                output_lines.append(f"  - import {imp['module']} (line {imp['line']})")

        return [TextContent(type="text", text="\n".join(output_lines))]

    def _handle_get_call_graph(self, args: dict) -> list[TextContent]:
        path = args["path"]
        symbol_key = args["symbol_key"]
        depth = args.get("depth", 2)

        query_api, _ = self._load_graph(path)
        call_graph = query_api.get_call_graph(symbol_key, depth=depth)

        output_lines = [f"Call graph for {symbol_key} (depth {depth}):"]
        _format_call_graph_recursive(call_graph, output_lines, indent=2)

        return [TextContent(type="text", text="\n".join(output_lines))]

    def _handle_get_dependencies(self, args: dict) -> list[TextContent]:
        path = args["path"]
        file_path = args["file"]

        query_api, _ = self._load_graph(path)

        dependencies = query_api.resolver.get_dependencies(file_path)
        dependents = query_api.resolver.get_dependents(file_path)

        output_lines = [f"Dependencies for {file_path}:"]
        if dependencies:
            output_lines.append("  Imports:")
            for dep in dependencies:
                output_lines.append(f"    - {dep}")
        else:
            output_lines.append("  Imports: (none)")

        output_lines.append("  Imported by:")
        if dependents:
            for dep in dependents:
                output_lines.append(f"    - {dep}")
        else:
            output_lines.append("    - (none)")

        return [TextContent(type="text", text="\n".join(output_lines))]

    def _handle_summary(self, args: dict) -> list[TextContent]:
        path = args["path"]

        query_api, _ = self._load_graph(path)
        summary = query_api.get_summary()

        output_lines = [f"Codebase summary for {path}:"]
        for key, value in summary.items():
            if isinstance(value, int):
                output_lines.append(f"  {key}: {value}")
            elif isinstance(value, dict) and value:
                output_lines.append("  Languages:")
                for lang, count in value.items():
                    output_lines.append(f"    {lang}: {count}")
            else:
                output_lines.append(f"  {key}: {value}")

        return [TextContent(type="text", text="\n".join(output_lines))]

    def _handle_markdown_report(self, args: dict) -> list[TextContent]:
        path = args["path"]

        query_api, _ = self._load_graph(path)
        markdown = format_markdown(query_api.graph)

        return [
            TextContent(
                type="text",
                text=markdown[:10000],  # Limit output size
            )
        ]


def _format_call_graph_recursive(
    node: dict,
    lines: list[str],
    indent: int,
) -> None:
    """Recursively format call graph output."""
    prefix = "  " * indent
    lines.append(f"{prefix}{node.get('key', 'unknown')}")
    for callee in node.get("callees", []):
        lines.append(
            f"{prefix}  └── {callee.get('callee', '?')} "
            f"({callee.get('call_type', 'direct')})"
        )
        _format_call_graph_recursive(callee, lines, indent + 2)


def create_server(name: str = "codegraph") -> CodeGraphServer:
    """Create a new CodeGraph MCP server instance."""
    return CodeGraphServer(name=name)


async def serve(cache_dir: str | None = None) -> None:
    """Run the MCP server with stdio transport."""
    server = create_server()

    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        init_opts = server.server.create_initialization_options()
        await server.server.run(read_stream, write_stream, init_opts)


def main() -> None:
    """CLI entry point for the MCP server."""
    import argparse

    parser = argparse.ArgumentParser(
        description="CodeGraph MCP Server — exposes code knowledge graphs via MCP."
    )
    parser.add_argument(
        "--cache-dir",
        help="Directory for incremental indexing cache.",
    )
    args = parser.parse_args()

    anyio.run(serve, cache_dir=args.cache_dir)


if __name__ == "__main__":
    main()
