# CodeGraph: Lightweight Local Code Knowledge Graph

## Overview
A Python CLI tool that indexes any codebase into a semantic knowledge graph.
Outputs structured JSON with function definitions, class hierarchies, imports,
call graphs, and cross-references — designed for AI coding agents to quickly
understand codebase structure without loading everything into context.

## Design Principles
- **Lightweight**: No heavy LSP servers, no language servers needed
- **Multi-language**: Support Python, TypeScript, JavaScript, Go, Rust
- **Fast**: Process 100K+ line repos in under 30 seconds
- **Structured output**: Clean JSON for AI agent consumption
- **Incremental**: Re-index only changed files
- **No dependencies**: Use only stdlib + tree-sitter (or pure Python fallback)

## Architecture

```
codegraph/
├── cli.py              # CLI entry point (argparse)
├── indexer.py          # Main indexing orchestration
├── parsers/
│   ├── base.py         # Abstract parser interface
│   ├── python.py       # Python parser (AST-based)
│   ├── javascript.py   # JS/TS parser (tree-sitter or regex fallback)
│   ├── go.py           # Go parser
│   └── rust.py         # Rust parser (tree-sitter)
├── graph.py            # Knowledge graph data structures
├── output.py           # JSON/Markdown output formatters
├── incremental.py      # Delta indexing support
└── utils.py            # File discovery, path handling
```

## Data Model

```python
@dataclass
class Symbol:
    name: str
    kind: str  # function, class, method, variable, import, module
    file: str
    line: int
    column: int
    signature: str  # e.g., "def foo(x: int) -> str"
    docstring: str
    access: str  # public, private, protected
    decorators: list[str]
    parents: list[str]  # enclosing scopes

@dataclass
class CallEdge:
    caller: str  # "file.py:42"
    callee: str  # "module.Class.method"
    call_type: str  # direct, dynamic, import

@dataclass
class CodeGraph:
    symbols: dict[str, Symbol]
    edges: list[CallEdge]
    imports: dict[str, list[ImportInfo]]
    summary: GraphSummary
```

## CLI Interface

```bash
# Basic usage
codegraph index ./myproject --output graph.json

# With filtering
codegraph index ./myproject --include "*.py,*.ts" --exclude "test/,node_modules/"

# Incremental
codegraph index ./myproject --cache .codegraph-cache

# Output formats
codegraph index ./myproject --format json
codegraph index ./myproject --format markdown

# Search within graph
codegraph query ./myproject --search "find_users" --format json

# Stats
codegraph index ./myproject --stats
```

## Implementation Plan

### Phase 1: Core Python Parser (Current)
- [x] Project scaffolding
- [ ] Python AST parser (functions, classes, methods, imports, decorators)
- [ ] Basic graph data structures
- [ ] CLI entry point
- [ ] JSON output

### Phase 2: Multi-language Support
- [ ] JavaScript/TypeScript parser (AST via ast-types or tree-sitter)
- [ ] Go parser (go/ast)
- [ ] Rust parser (tree-sitter-rust)

### Phase 3: Advanced Features
- [ ] Call graph resolution (cross-file)
- [ ] Incremental/delta indexing
- [ ] Cache system
- [ ] Query/search interface
- [ ] Markdown output for human readability

### Phase 4: Polish
- [ ] Tests
- [ ] Documentation
- [ ] PyPI package
- [ ] Performance benchmarks
