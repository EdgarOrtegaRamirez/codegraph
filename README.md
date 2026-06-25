# CodeGraph

Lightweight local code knowledge graph for AI coding agents.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Tests](https://img.shields.io/badge/tests-90_passed-brightgreen.svg)](tests/)

## What it does

CodeGraph indexes your codebase into a semantic knowledge graph containing:

- **Function & method definitions** with signatures, parameters, and return types
- **Class hierarchies** with inheritance relationships
- **Import graphs** showing module dependencies
- **Call edges** tracking function calls across files
- **Cross-reference resolution** — callers, callees, dependencies, dependents
- **Incremental indexing** with file-level cache for fast re-indexing
- **MCP server** — expose the graph to AI agents via Model Context Protocol

Designed for AI coding agents to quickly understand codebase structure without loading everything into context.

## Quick Start

```bash
# Install
pip install codegraph

# Index a codebase
codegraph index ./myproject --output graph.json

# View as markdown report
codegraph index ./myproject --format markdown

# View stats
codegraph index ./myproject --stats

# Query: search by name
codegraph query ./myproject --search "User" --kind function

# Query: list all functions
codegraph query ./myproject --functions

# Query: show call graph for a symbol
codegraph query ./myproject --call-graph "src/main.py:42"

# Resolve cross-file dependencies
codegraph resolve ./myproject

# Incremental indexing
codegraph index ./myproject --cache .codegraph-cache
```

## Multi-Language Support

| Language | Parser | Status |
|----------|--------|--------|
| Python | AST-based | ✅ Full |
| JavaScript/TypeScript | Regex-based | ✅ Full |
| Go | Regex-based | ✅ Full |
| Rust | Regex-based | ✅ Full |

## MCP Server

CodeGraph includes a full MCP server for AI agent integration:

```bash
# Start the MCP server (stdio mode)
python -m codegraph.mcp_server

# Or use the CLI
codegraph mcp --index ./myproject
```

The server exposes 10 tools: `index`, `search`, `get_symbol`, `get_functions`, `get_classes`, `get_imports`, `get_call_graph`, `get_dependencies`, `summary`, `markdown_report`.

## Example Output

```json
{
  "metadata": {
    "version": "0.1.0",
    "root": "/path/to/project"
  },
  "summary": {
    "total_symbols": 15,
    "total_files": 2,
    "total_functions": 5,
    "total_classes": 1,
    "total_imports": 4,
    "total_edges": 8
  },
  "symbols": {
    "main.py:30": {
      "name": "DatabaseConnection",
      "kind": "class",
      "file": "main.py",
      "line": 30,
      "signature": "",
      "docstring": "A sample database connection class.",
      "access": "public"
    },
    "main.py:42": {
      "name": "connect",
      "kind": "method",
      "file": "main.py",
      "line": 42,
      "signature": "def connect(self) -> bool",
      "docstring": "Establish a database connection.",
      "access": "public",
      "parameters": ["self"],
      "return_type": "bool"
    }
  }
}
```

## CLI Reference

```
codegraph <command> [options]

Commands:
  index    Index a codebase into a knowledge graph
  query    Query the indexed codebase
  resolve  Resolve cross-file references
  mcp      Start MCP server
```

### Index Command

```
codegraph index <path> [options]
  --output, -o FILE       Output file path (default: stdout)
  --format, -f FORMAT     Output format: json, markdown, stats (default: json)
  --include GLOB          Comma-separated file patterns to include
  --exclude DIR           Comma-separated directory patterns to exclude
  --cache DIR             Cache directory for incremental indexing
  --clear-cache           Clear cache before indexing
```

### Query Command

```
codegraph query <path> [options]
  --search, -s TEXT       Search term (matches name and docstring)
  --kind, -k KIND         Filter by kind: function, method, class, variable, module
  --file, -f PATH         Filter by file path
  --functions             List all functions/methods
  --classes               List all classes/structs/interfaces
  --imports PATH          List imports for a specific file
  --call-graph, -c KEY    Show call graph for a symbol key (file:line)
  --output, -o FILE       Output file path
```

### Resolve Command

```
codegraph resolve <path> [options]
  --file PATH             Show dependencies for a specific file
  --output, -o FILE       Output file path
```

## Architecture

```
codegraph/
├── cli.py              # CLI entry point (index, query, resolve, mcp)
├── indexer.py          # Main indexing orchestration
├── incremental.py      # Delta indexing with file-level cache
├── parsers/
│   ├── base.py         # Abstract parser interface
│   ├── python.py       # Python AST parser
│   ├── javascript.py   # JavaScript/TypeScript parser
│   ├── go.py           # Go parser
│   └── rust.py         # Rust parser
├── graph.py            # Knowledge graph data structures
├── output.py           # JSON/Markdown/Stats formatters
├── resolve.py          # Cross-reference resolution engine
├── mcp_server.py       # MCP server with 10 tools
└── utils.py            # File discovery, helpers
```

## Install from Source

```bash
git clone https://github.com/EdgarOrtegaRamirez/codegraph.git
cd codegraph
pip install -e .
# For MCP server support:
pip install -e ".[mcp]"
```

## Testing

```bash
pip install pytest
pytest tests/ -v
```

90 tests covering parsers, indexing, incremental caching, CLI, MCP server, and cross-reference resolution.

## License

MIT
