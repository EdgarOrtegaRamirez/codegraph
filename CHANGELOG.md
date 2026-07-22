# Changelog

## [0.1.0] - 2026-06-25

### Added
- Initial release
- Multi-language support: Python (AST), JavaScript/TypeScript, Go, Rust
- Core indexing engine with semantic code graph
- Incremental/delta indexing with file-level cache
- Cross-reference resolution: callers, callees, dependencies, dependents
- CLI with three commands: `index`, `query`, `resolve`
- MCP server with 10 tools for AI agent integration
- Graph query API: search, get_symbol, get_functions, get_classes, get_imports, get_call_graph, summary
- Output formatters: JSON, Markdown, Stats
- File discovery with configurable include/exclude patterns
- 90 passing tests covering all modules

## [0.1.1] - 2026-07-22

### Changed
- Maintenance: CI workflow, dependency verification
- Updated anyio and ruff dev dependencies
