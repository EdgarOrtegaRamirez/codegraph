"""Integration tests for CodeGraph: multi-language, end-to-end, incremental."""

import json
import subprocess
import tempfile
from pathlib import Path

import pytest

from codegraph.graph import CodeGraph, Symbol, ImportInfo, CallEdge
from codegraph.indexer import Indexer
from codegraph.incremental import IncrementalIndexer, CacheManager
from codegraph.resolve import GraphQuery
from codegraph.parsers.rust import RustParser


# --- Multi-language integration sample ---

MULTI_LANGUAGE_PROJECT = {
    "main.py": '''
"""Main application module."""

import os
from utils import helper

class Application:
    """The main application class."""

    def __init__(self, name: str):
        """Initialize the application."""
        self.name = name

    def run(self) -> None:
        """Run the application."""
        print(f"Running {self.name}")

def main():
    """Entry point."""
    app = Application("MyApp")
    app.run()

if __name__ == "__main__":
    main()
''',
    "utils.py": '''
"""Utility functions."""

import json

def helper(x: int) -> int:
    """Helper function."""
    return x * 2

def format_data(data: dict) -> str:
    """Format data as JSON string."""
    return json.dumps(data)
''',
    "app.js": '''
/**
 * Express application entry point.
 */

import express from "express";
import { Router } from "express";

const PORT = 3000;

class UserService {
    constructor(db) {
        this.db = db;
    }

    async getUser(id) {
        return this.db.findById(id);
    }
}

async function main() {
    const app = express();
    const service = new UserService();
    const user = await service.getUser(1);
    console.log(user);
}

export const helper = (x) => x + 1;

export default main;
''',
    "main.go": '''
package main

import (
    "fmt"
    "net/http"
)

// Config holds application configuration
type Config struct {
    Port int
}

// Handler processes HTTP requests
type Handler struct {
    config *Config
}

func NewHandler(config *Config) *Handler {
    return &Handler{config: config}
}

func (h *Handler) ServeHTTP(w http.ResponseWriter, r *http.Request) {
    fmt.Fprintf(w, "Hello!")
}

func main() {
    config := &Config{Port: 8080}
    handler := NewHandler(config)
    fmt.Println("Starting...")
    http.ListenAndServe(fmt.Sprintf(":%d", config.Port), handler)
}
''',
    "lib.rs": '''
use std::collections::HashMap;

/// Main application struct
pub struct App {
    name: String,
}

impl App {
    /// Create a new App
    pub fn new(name: &str) -> Self {
        Self { name: name.to_string() }
    }

    /// Run the application
    pub fn run(&self) {
        println!("Running {}", self.name);
    }
}

/// Main entry point
fn main() {
    let app = App::new("MyApp");
    app.run();
}
''',
}


@pytest.fixture
def multi_lang_project(tmp_path: Path) -> Path:
    """Create a multi-language project directory."""
    for name, content in MULTI_LANGUAGE_PROJECT.items():
        (tmp_path / name).write_text(content)
    return tmp_path


# --- Multi-language integration tests ---

class TestMultiLanguageIntegration:
    """Test that the indexer correctly handles multi-language projects."""

    def test_indexes_all_languages(self, multi_lang_project: Path) -> None:
        indexer = Indexer(multi_lang_project)
        graph = indexer.index()

        # Should have symbols from all 5 files
        files = set(s.file for s in graph.symbols.values())
        assert len(files) == 5

        # Should have functions from all languages
        funcs = [s for s in graph.symbols.values() if s.kind in ("function", "method")]
        assert len(funcs) >= 15  # At least 15 functions/methods across all files

    def test_python_symbols(self, multi_lang_project: Path) -> None:
        indexer = Indexer(multi_lang_project)
        graph = indexer.index()

        py_symbols = [s for s in graph.symbols.values() if s.file == "main.py"]
        names = {s.name for s in py_symbols}
        assert "Application" in names
        assert "main" in names
        assert "run" in names

    def test_javascript_symbols(self, multi_lang_project: Path) -> None:
        indexer = Indexer(multi_lang_project)
        graph = indexer.index()

        js_symbols = [s for s in graph.symbols.values() if s.file == "app.js"]
        names = {s.name for s in js_symbols}
        assert "UserService" in names
        assert "main" in names

    def test_go_symbols(self, multi_lang_project: Path) -> None:
        indexer = Indexer(multi_lang_project)
        graph = indexer.index()

        go_symbols = [s for s in graph.symbols.values() if s.file == "main.go"]
        names = {s.name for s in go_symbols}
        assert "Config" in names
        assert "Handler" in names
        assert "NewHandler" in names

    def test_rust_symbols(self, multi_lang_project: Path) -> None:
        indexer = Indexer(multi_lang_project)
        graph = indexer.index()

        rs_symbols = [s for s in graph.symbols.values() if s.file == "lib.rs"]
        names = {s.name for s in rs_symbols}
        assert "App" in names
        assert "main" in names

    def test_all_imports_collected(self, multi_lang_project: Path) -> None:
        indexer = Indexer(multi_lang_project)
        graph = indexer.index()

        assert len(graph.imports) >= 6  # Python, JS, Go, Rust all have imports

    def test_call_edges_across_languages(self, multi_lang_project: Path) -> None:
        indexer = Indexer(multi_lang_project)
        graph = indexer.index()

        # Each language should have call edges
        assert len(graph.edges) > 0


# --- Rust parser tests ---

SAMPLE_RUST = '''
use std::collections::HashMap;

/// A user struct
pub struct User {
    id: u64,
    name: String,
}

impl User {
    /// Create a new user
    pub fn new(id: u64, name: &str) -> Self {
        Self {
            id,
            name: name.to_string(),
        }
    }

    /// Get the user's name
    pub fn name(&self) -> &str {
        &self.name
    }
}

/// Process a list of users
fn process_users(users: Vec<User>) -> HashMap<u64, String> {
    let mut map = HashMap::new();
    for user in users {
        map.insert(user.id, user.name.clone());
    }
    map
}

fn main() {
    let user = User::new(1, "Alice");
    println!("{}", user.name());
}
'''


class TestRustParser:
    def test_parses_structs(self, tmp_path: Path) -> None:
        f = tmp_path / "lib.rs"
        f.write_text(SAMPLE_RUST)

        graph = CodeGraph(root_path=str(tmp_path))
        parser = RustParser(tmp_path)
        parser.parse_file(f, graph)

        structs = [s for s in graph.symbols.values() if s.kind == "class"]
        names = {s.name for s in structs}
        assert "User" in names

    def test_parses_functions(self, tmp_path: Path) -> None:
        f = tmp_path / "lib.rs"
        f.write_text(SAMPLE_RUST)

        graph = CodeGraph(root_path=str(tmp_path))
        parser = RustParser(tmp_path)
        parser.parse_file(f, graph)

        funcs = [s for s in graph.symbols.values() if s.kind == "function"]
        names = {s.name for s in funcs}
        assert "process_users" in names
        assert "main" in names

    def test_parses_methods(self, tmp_path: Path) -> None:
        f = tmp_path / "lib.rs"
        f.write_text(SAMPLE_RUST)

        graph = CodeGraph(root_path=str(tmp_path))
        parser = RustParser(tmp_path)
        parser.parse_file(f, graph)

        methods = [s for s in graph.symbols.values() if s.kind == "method"]
        names = {s.name for s in methods}
        assert "new" in names
        assert "name" in names

    def test_parses_imports(self, tmp_path: Path) -> None:
        f = tmp_path / "lib.rs"
        f.write_text(SAMPLE_RUST)

        graph = CodeGraph(root_path=str(tmp_path))
        parser = RustParser(tmp_path)
        parser.parse_file(f, graph)

        assert len(graph.imports) >= 1
        modules = {i.module for i in graph.imports}
        assert "std::collections::HashMap" in modules

    def test_detects_public_access(self, tmp_path: Path) -> None:
        f = tmp_path / "lib.rs"
        f.write_text(SAMPLE_RUST)

        graph = CodeGraph(root_path=str(tmp_path))
        parser = RustParser(tmp_path)
        parser.parse_file(f, graph)

        user_struct = next(s for s in graph.symbols.values() if s.name == "User")
        assert user_struct.access == "public"


# --- Incremental indexing tests ---

class TestIncrementalIndexing:
    def test_full_index(self, tmp_path: Path) -> None:
        """Test that full indexing works."""
        (tmp_path / "test.py").write_text(
            'def foo():\n    pass\n\nclass Bar:\n    pass\n'
        )

        indexer = IncrementalIndexer(tmp_path)
        graph = indexer.index()

        assert graph.summary.total_symbols >= 2
        assert graph.summary.total_functions >= 1

    def test_cache_persists(self, tmp_path: Path) -> None:
        """Test that cache is created and persisted."""
        (tmp_path / "test.py").write_text('def foo():\n    pass\n')

        cache_dir = tmp_path / ".cache"
        indexer = IncrementalIndexer(tmp_path, cache_dir=cache_dir)
        indexer.index()

        assert (cache_dir / "codegraph_cache.json").exists()

    def test_unchanged_files_skipped(self, tmp_path: Path) -> None:
        """Test that unchanged files are skipped on second run."""
        (tmp_path / "test.py").write_text('def foo():\n    pass\n')

        cache_dir = tmp_path / ".cache"
        indexer = IncrementalIndexer(tmp_path, cache_dir=cache_dir)
        indexer.index()

        # Second run should skip the unchanged file
        indexer2 = IncrementalIndexer(tmp_path, cache_dir=cache_dir)
        graph = indexer2.index()

        assert graph.summary.total_symbols == 1

    def test_changed_file_reindexed(self, tmp_path: Path) -> None:
        """Test that changed files are re-indexed."""
        (tmp_path / "test.py").write_text('def foo():\n    pass\n')

        cache_dir = tmp_path / ".cache"
        indexer = IncrementalIndexer(tmp_path, cache_dir=cache_dir)
        indexer.index()

        # Modify the file
        import time
        time.sleep(0.1)
        (tmp_path / "test.py").write_text('def foo():\n    pass\n\ndef bar():\n    pass\n')

        indexer2 = IncrementalIndexer(tmp_path, cache_dir=cache_dir)
        graph = indexer2.index()

        # Should now have 2 functions
        assert graph.summary.total_functions == 2

    def test_clear_cache(self, tmp_path: Path) -> None:
        """Test that cache can be cleared."""
        (tmp_path / "test.py").write_text('def foo():\n    pass\n')

        cache_dir = tmp_path / ".cache"
        indexer = IncrementalIndexer(tmp_path, cache_dir=cache_dir)
        indexer.index()
        assert (cache_dir / "codegraph_cache.json").exists()

        indexer.clear_cache()
        assert not (cache_dir / "codegraph_cache.json").exists()

    def test_cache_manager_load_save(self, tmp_path: Path) -> None:
        """Test CacheManager load/save cycle."""
        cache = CacheManager(tmp_path / "cache")
        data = {
            "files": {
                "test.py": {"mtime": 1234567890.0, "symbols": 5},
            },
            "version": "0.1.0",
        }
        cache.save(data)

        loaded = cache.load()
        assert loaded["files"]["test.py"]["mtime"] == 1234567890.0
        assert loaded["files"]["test.py"]["symbols"] == 5

    def test_cache_file_mtime_lookup(self, tmp_path: Path) -> None:
        """Test getting and setting file mtime in cache."""
        cache = CacheManager(tmp_path / "cache")
        cache.set_file_mtime("test.py", 999.0)

        assert cache.get_file_mtime("test.py") == 999.0
        assert cache.get_file_mtime("missing.py") is None


# --- CLI integration tests ---

class TestCLIIntegration:
    def test_index_command(self, multi_lang_project: Path, tmp_path: Path) -> None:
        """Test the CLI index command produces valid JSON."""
        output_file = tmp_path / "output.json"
        import subprocess
        result = subprocess.run(
            ["python", "-m", "codegraph", "index", str(multi_lang_project),
             "--output", str(output_file)],
            capture_output=True, text=True,
            cwd="/root/codegraph",
        )
        assert result.returncode == 0
        data = json.loads(output_file.read_text())
        assert "symbols" in data
        assert "edges" in data
        assert "imports" in data

    def test_query_command(self, multi_lang_project: Path, tmp_path: Path) -> None:
        """Test the CLI query command with search."""
        output_file = tmp_path / "query.json"
        result = subprocess.run(
            ["python", "-m", "codegraph", "query", str(multi_lang_project),
             "--search", "User", "--output", str(output_file)],
            capture_output=True, text=True,
            cwd="/root/codegraph",
        )
        assert result.returncode == 0
        data = json.loads(output_file.read_text())
        assert isinstance(data, list)
        # Should find User from JS and Rust
        names = [d["name"] for d in data]
        assert "UserService" in names or "User" in names

    def test_query_functions(self, multi_lang_project: Path, tmp_path: Path) -> None:
        """Test the CLI query --functions command."""
        output_file = tmp_path / "funcs.json"
        result = subprocess.run(
            ["python", "-m", "codegraph", "query", str(multi_lang_project),
             "--functions", "--output", str(output_file)],
            capture_output=True, text=True,
            cwd="/root/codegraph",
        )
        assert result.returncode == 0
        data = json.loads(output_file.read_text())
        assert isinstance(data, list)
        assert len(data) > 0

    def test_query_classes(self, multi_lang_project: Path, tmp_path: Path) -> None:
        """Test the CLI query --classes command."""
        output_file = tmp_path / "classes.json"
        result = subprocess.run(
            ["python", "-m", "codegraph", "query", str(multi_lang_project),
             "--classes", "--output", str(output_file)],
            capture_output=True, text=True,
            cwd="/root/codegraph",
        )
        assert result.returncode == 0
        data = json.loads(output_file.read_text())
        assert isinstance(data, list)
        assert len(data) > 0

    def test_stats_format(self, multi_lang_project: Path) -> None:
        """Test the CLI index --stats command."""
        result = subprocess.run(
            ["python", "-m", "codegraph", "index", str(multi_lang_project),
             "--format", "stats"],
            capture_output=True, text=True,
            cwd="/root/codegraph",
        )
        assert result.returncode == 0
        assert "Total symbols:" in result.stdout
        assert "Total files:" in result.stdout

    def test_markdown_format(self, multi_lang_project: Path) -> None:
        """Test the CLI index --format markdown command."""
        result = subprocess.run(
            ["python", "-m", "codegraph", "index", str(multi_lang_project),
             "--format", "markdown"],
            capture_output=True, text=True,
            cwd="/root/codegraph",
        )
        assert result.returncode == 0
        assert "# CodeGraph Analysis" in result.stdout

    def test_incremental_index_cli(self, multi_lang_project: Path, tmp_path: Path) -> None:
        """Test the CLI --cache flag."""
        cache_dir = tmp_path / ".codegraph-cache"
        output_file = tmp_path / "output.json"
        result = subprocess.run(
            ["python", "-m", "codegraph", "index", str(multi_lang_project),
             "--cache", str(cache_dir), "--output", str(output_file)],
            capture_output=True, text=True,
            cwd="/root/codegraph",
        )
        assert result.returncode == 0
        assert "Delta index:" in result.stderr or "files to index" in result.stderr
        assert (cache_dir / "codegraph_cache.json").exists()
