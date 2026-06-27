"""CLI entry point for CodeGraph."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from codegraph.indexer import Indexer
from codegraph.incremental import IncrementalIndexer
from codegraph.output import format_markdown, format_stats
from codegraph.resolve import GraphQuery


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser."""
    parser = argparse.ArgumentParser(
        prog="codegraph",
        description="Lightweight Local Code Knowledge Graph — index your codebase for AI coding agents.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
examples:
  codegraph index ./myproject
  codegraph index ./myproject --output graph.json
  codegraph index ./myproject --format markdown
  codegraph index ./myproject --stats
  codegraph index ./myproject --include "*.py,*.ts"
  codegraph query ./myproject --search "User" --kind function
  codegraph query ./myproject --file src/main.py --functions
  codegraph resolve ./myproject
""",
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # index subcommand
    index_parser = subparsers.add_parser(
        "index", help="Index a codebase into a knowledge graph"
    )
    index_parser.add_argument(
        "path",
        help="Path to the codebase to index",
    )
    index_parser.add_argument(
        "--output", "-o",
        help="Output file path (default: stdout)",
    )
    index_parser.add_argument(
        "--format", "-f",
        choices=["json", "markdown", "stats"],
        default="json",
        help="Output format (default: json)",
    )
    index_parser.add_argument(
        "--include",
        help="Comma-separated list of file extensions to include (e.g., '*.py,*.ts')",
    )
    index_parser.add_argument(
        "--exclude",
        help="Comma-separated list of directory patterns to exclude",
    )
    index_parser.add_argument(
        "--cache",
        help="Cache directory for incremental indexing (e.g., .codegraph-cache)",
    )
    index_parser.add_argument(
        "--clear-cache",
        action="store_true",
        help="Clear the cache before indexing",
    )
    index_parser.add_argument(
        "--stats",
        action="store_true",
        help="Shorthand for --format stats",
    )

    # query subcommand
    query_parser = subparsers.add_parser(
        "query", help="Query the indexed codebase"
    )
    query_parser.add_argument(
        "path",
        help="Path to the codebase to query",
    )
    query_parser.add_argument(
        "--search", "-s",
        help="Search term (matches name and docstring)",
    )
    query_parser.add_argument(
        "--kind", "-k",
        choices=["function", "method", "class", "variable", "module"],
        help="Filter by symbol kind",
    )
    query_parser.add_argument(
        "--file", "-f",
        help="Filter by file path",
    )
    query_parser.add_argument(
        "--functions",
        action="store_true",
        help="List all functions/methods",
    )
    query_parser.add_argument(
        "--classes",
        action="store_true",
        help="List all classes/structs/interfaces",
    )
    query_parser.add_argument(
        "--imports",
        help="List imports for a specific file",
    )
    query_parser.add_argument(
        "--call-graph", "-c",
        help="Show call graph for a symbol key (file:line)",
    )
    query_parser.add_argument(
        "--output", "-o",
        help="Output file path (default: stdout)",
    )

    # resolve subcommand
    resolve_parser = subparsers.add_parser(
        "resolve", help="Resolve cross-file references and print dependency info"
    )
    resolve_parser.add_argument(
        "path",
        help="Path to the codebase to resolve",
    )
    resolve_parser.add_argument(
        "--file",
        help="Show dependencies for a specific file",
    )
    resolve_parser.add_argument(
        "--output", "-o",
        help="Output file path (default: stdout)",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    """Main entry point."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 1

    if args.command == "index":
        return cmd_index(args)
    elif args.command == "query":
        return cmd_query(args)
    elif args.command == "resolve":
        return cmd_resolve(args)

    return 0


def cmd_index(args: argparse.Namespace) -> int:
    """Handle the 'index' command."""
    target = Path(args.path).resolve()

    if not target.exists():
        print(f"Error: {target} does not exist", file=sys.stderr)
        return 1

    if not target.is_dir():
        print(f"Error: {target} is not a directory", file=sys.stderr)
        return 1

    # Determine extensions
    extensions = None
    if args.include:
        extensions = set(args.include.split(","))

    # Check for incremental indexing
    if args.cache:
        print(f"Indexing {target} (incremental)...", file=sys.stderr)
        indexer = IncrementalIndexer(target, cache_dir=args.cache, extensions=extensions)
        if args.clear_cache:
            indexer.clear_cache()
    else:
        print(f"Indexing {target}...", file=sys.stderr)
        indexer = Indexer(target, extensions=extensions)

    # Index
    graph = indexer.index()

    # Format output
    if getattr(args, 'stats', False):
        output = format_stats(graph)
    elif args.format == "stats":
        output = format_stats(graph)
    elif args.format == "markdown":
        output = format_markdown(graph)
    else:
        output = graph.to_json(indent=2)

    # Write output
    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(output, encoding="utf-8")
        print(f"Written to {out_path}", file=sys.stderr)
    else:
        print(output)

    return 0


def cmd_query(args: argparse.Namespace) -> int:
    """Handle the 'query' command."""
    target = Path(args.path).resolve()

    if not target.exists():
        print(f"Error: {target} does not exist", file=sys.stderr)
        return 1

    if not target.is_dir():
        print(f"Error: {target} is not a directory", file=sys.stderr)
        return 1

    # Index first
    print(f"Indexing {target}...", file=sys.stderr)
    indexer = Indexer(target)
    graph = indexer.index()

    # Build query API
    query_api = GraphQuery(graph)

    # Dispatch query mode
    if args.call_graph:
        result = query_api.get_call_graph(args.call_graph)
        output = json.dumps(result, indent=2)
    elif args.functions:
        file_filter = args.file
        funcs = query_api.get_functions(file_filter)
        output = json.dumps(funcs, indent=2)
    elif args.classes:
        file_filter = args.file
        classes = query_api.get_classes(file_filter)
        output = json.dumps(classes, indent=2)
    elif args.imports:
        imp_list = query_api.get_imports(args.imports)
        output = json.dumps(imp_list, indent=2)
    elif args.search:
        results = query_api.search(args.search, kind=args.kind)
        output = json.dumps(results, indent=2)
    else:
        # Default: show summary
        summary = query_api.get_summary()
        output = json.dumps(summary, indent=2)

    # Write output
    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(output, encoding="utf-8")
        print(f"Written to {out_path}", file=sys.stderr)
    else:
        print(output)

    return 0


def cmd_resolve(args: argparse.Namespace) -> int:
    """Handle the 'resolve' command."""
    target = Path(args.path).resolve()

    if not target.exists():
        print(f"Error: {target} does not exist", file=sys.stderr)
        return 1

    if not target.is_dir():
        print(f"Error: {target} is not a directory", file=sys.stderr)
        return 1

    # Index first
    print(f"Indexing {target}...", file=sys.stderr)
    indexer = Indexer(target)
    graph = indexer.index()

    # Build query API (triggers cross-ref resolution)
    query_api = GraphQuery(graph)

    if args.file:
        # Show dependencies for a specific file
        file_path = args.file
        deps = query_api.resolver.get_dependencies(file_path)
        dependents = query_api.resolver.get_dependents(file_path)

        result = {
            "file": file_path,
            "dependencies": deps,
            "dependents": dependents,
        }
        output = json.dumps(result, indent=2)
    else:
        # Show all file-level dependency info
        result = {}
        for file_path in set(s.file for s in graph.symbols.values()):
            result[file_path] = {
                "dependencies": query_api.resolver.get_dependencies(file_path),
                "dependents": query_api.resolver.get_dependents(file_path),
            }
        output = json.dumps(result, indent=2)

    # Write output
    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(output, encoding="utf-8")
        print(f"Written to {out_path}", file=sys.stderr)
    else:
        print(output)

    return 0


if __name__ == "__main__":
    sys.exit(main())
