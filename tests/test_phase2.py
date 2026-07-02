"""Tests for CodeGraph Phase 2: JS/TS parser, Go parser, resolve, and query."""

from pathlib import Path

import pytest

from codegraph.graph import CodeGraph, Symbol
from codegraph.parsers.go import GoParser
from codegraph.parsers.javascript import JavaScriptParser
from codegraph.resolve import CrossRefResolver, GraphQuery


# --- JS/TS Parser Tests ---

SAMPLE_JAVASCRIPT = """
/**
 * A sample JavaScript module.
 */

import express from "express";
import { Router, Request } from "express";

const PORT = 3000;
const HOST = "localhost";

class UserService {
    /**
     * Create a new user service.
     */
    constructor(db) {
        this.db = db;
    }

    async getUser(id) {
        return this.db.findById(id);
    }

    static create() {
        return new UserService();
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
"""

SAMPLE_TYPESCRIPT = """
interface User {
    id: number;
    name: string;
}

export class UserRepository {
    private db: any;

    constructor(db: any) {
        this.db = db;
    }

    async findById(id: number): Promise<User> {
        return this.db.find(id);
    }

    async findAll(): Promise<User[]> {
        return this.db.all();
    }
}

export function createUser(name: string): User {
    return { id: 1, name };
}
"""

SAMPLE_GO = """
package main

import (
    "fmt"
    "net/http"
)

// Config holds application configuration
type Config struct {
    Port    int
    Host    string
    Debug   bool
}

// Handler processes HTTP requests
type Handler struct {
    config *Config
}

// NewHandler creates a new Handler
func NewHandler(config *Config) *Handler {
    return &Handler{config: config}
}

// ServeHTTP handles an HTTP request
func (h *Handler) ServeHTTP(w http.ResponseWriter, r *http.Request) {
    fmt.Fprintf(w, "Hello, World!")
}

func main() {
    config := &Config{Port: 8080, Host: "localhost"}
    handler := NewHandler(config)
    fmt.Println("Starting server...")
    http.ListenAndServe(fmt.Sprintf("%s:%d", config.Host, config.Port), handler)
}
"""


@pytest.fixture
def js_file(tmp_path: Path) -> Path:
    f = tmp_path / "app.js"
    f.write_text(SAMPLE_JAVASCRIPT)
    return f


@pytest.fixture
def ts_file(tmp_path: Path) -> Path:
    f = tmp_path / "repo.ts"
    f.write_text(SAMPLE_TYPESCRIPT)
    return f


@pytest.fixture
def go_file(tmp_path: Path) -> Path:
    f = tmp_path / "main.go"
    f.write_text(SAMPLE_GO)
    return f


@pytest.fixture
def empty_graph() -> CodeGraph:
    return CodeGraph(root_path="/test")


# --- JavaScript Parser Tests ---


class TestJavaScriptParser:
    def test_parses_classes(self, js_file: Path, empty_graph: CodeGraph) -> None:
        parser = JavaScriptParser(js_file.parent)
        parser.parse_file(js_file, empty_graph)

        classes = [s for s in empty_graph.symbols.values() if s.kind == "class"]
        assert len(classes) >= 1
        names = {c.name for c in classes}
        assert "UserService" in names

    def test_parses_functions(self, js_file: Path, empty_graph: CodeGraph) -> None:
        parser = JavaScriptParser(js_file.parent)
        parser.parse_file(js_file, empty_graph)

        funcs = [s for s in empty_graph.symbols.values() if s.kind == "function"]
        names = {f.name for f in funcs}
        assert "main" in names

    def test_parses_arrow_functions(
        self, js_file: Path, empty_graph: CodeGraph
    ) -> None:
        parser = JavaScriptParser(js_file.parent)
        parser.parse_file(js_file, empty_graph)

        funcs = [s for s in empty_graph.symbols.values() if s.kind == "function"]
        names = {f.name for f in funcs}
        assert "helper" in names

    def test_parses_methods(self, js_file: Path, empty_graph: CodeGraph) -> None:
        parser = JavaScriptParser(js_file.parent)
        parser.parse_file(js_file, empty_graph)

        methods = [s for s in empty_graph.symbols.values() if s.kind == "method"]
        names = {m.name for m in methods}
        assert "constructor" in names
        assert "getUser" in names

    def test_parses_imports(self, js_file: Path, empty_graph: CodeGraph) -> None:
        parser = JavaScriptParser(js_file.parent)
        parser.parse_file(js_file, empty_graph)

        assert len(empty_graph.imports) >= 2
        modules = {i.module for i in empty_graph.imports}
        assert "express" in modules

    def test_parses_variables(self, js_file: Path, empty_graph: CodeGraph) -> None:
        parser = JavaScriptParser(js_file.parent)
        parser.parse_file(js_file, empty_graph)

        variables = [s for s in empty_graph.symbols.values() if s.kind == "variable"]
        names = {v.name for v in variables}
        assert "PORT" in names
        assert "HOST" in names

    def test_detects_async(self, js_file: Path, empty_graph: CodeGraph) -> None:
        parser = JavaScriptParser(js_file.parent)
        parser.parse_file(js_file, empty_graph)

        funcs = [s for s in empty_graph.symbols.values() if s.name == "main"]
        assert len(funcs) >= 1
        assert funcs[0].is_async

    def test_parses_typescript(self, ts_file: Path, empty_graph: CodeGraph) -> None:
        parser = JavaScriptParser(ts_file.parent)
        parser.parse_file(ts_file, empty_graph)

        classes = [s for s in empty_graph.symbols.values() if s.kind == "class"]
        names = {c.name for c in classes}
        assert "UserRepository" in names

    def test_parses_call_edges(self, js_file: Path, empty_graph: CodeGraph) -> None:
        parser = JavaScriptParser(js_file.parent)
        parser.parse_file(js_file, empty_graph)

        assert len(empty_graph.edges) > 0
        callees = {e.callee for e in empty_graph.edges}
        assert "express" in callees or "console" in callees


# --- Go Parser Tests ---


class TestGoParser:
    def test_parses_structs(self, go_file: Path, empty_graph: CodeGraph) -> None:
        parser = GoParser(go_file)
        parser.parse_file(go_file, empty_graph)

        structs = [s for s in empty_graph.symbols.values() if s.kind == "class"]
        names = {s.name for s in structs}
        assert "Config" in names
        assert "Handler" in names

    def test_parses_functions(self, go_file: Path, empty_graph: CodeGraph) -> None:
        parser = GoParser(go_file)
        parser.parse_file(go_file, empty_graph)

        funcs = [s for s in empty_graph.symbols.values() if s.kind == "function"]
        names = {f.name for f in funcs}
        assert "main" in names
        assert "NewHandler" in names

    def test_parses_methods(self, go_file: Path, empty_graph: CodeGraph) -> None:
        parser = GoParser(go_file)
        parser.parse_file(go_file, empty_graph)

        methods = [s for s in empty_graph.symbols.values() if s.kind == "method"]
        names = {m.name for m in methods}
        assert "ServeHTTP" in names

    def test_parses_imports(self, go_file: Path, empty_graph: CodeGraph) -> None:
        parser = GoParser(go_file)
        parser.parse_file(go_file, empty_graph)

        assert len(empty_graph.imports) >= 2
        modules = {i.module for i in empty_graph.imports}
        assert "fmt" in modules
        assert "net/http" in modules

    def test_parses_variables(self, go_file: Path, empty_graph: CodeGraph) -> None:
        parser = GoParser(go_file)
        parser.parse_file(go_file, empty_graph)

        variables = [s for s in empty_graph.symbols.values() if s.kind == "variable"]
        names = {v.name for v in variables}
        assert "config" in names
        assert "handler" in names

    def test_detects_access_level(self, go_file: Path, empty_graph: CodeGraph) -> None:
        parser = GoParser(go_file)
        parser.parse_file(go_file, empty_graph)

        # Capitalized names should be public (NewHandler)
        funcs = [s for s in empty_graph.symbols.values() if s.name == "NewHandler"]
        assert len(funcs) >= 1
        assert funcs[0].access == "public"


# --- Cross-Reference Resolver Tests ---


class TestCrossRefResolver:
    def test_resolves_imports(self, sample_graph: CodeGraph) -> None:
        sym = Symbol(
            name="foo",
            kind="function",
            file="a.py",
            line=1,
            column=0,
        )
        sample_graph.add_symbol(sym)
        sym2 = Symbol(
            name="foo",
            kind="function",
            file="b.py",
            line=5,
            column=0,
        )
        sample_graph.add_symbol(sym2)

        resolver = CrossRefResolver(sample_graph)
        resolver.resolve_all()

        # Both symbols should have reference counts updated
        assert sample_graph.symbols["a.py:1"].references >= 0
        assert sample_graph.symbols["b.py:5"].references >= 0

    def test_get_callers(self, sample_graph: CodeGraph) -> None:
        from codegraph.graph import CallEdge

        sample_graph.add_edge(
            CallEdge(
                caller="caller.py:10",
                callee="target.py:5",
                call_type="direct",
                line=10,
            )
        )
        sample_graph.add_edge(
            CallEdge(
                caller="caller.py:20",
                callee="target.py:5",
                call_type="direct",
                line=20,
            )
        )

        resolver = CrossRefResolver(sample_graph)
        callers = resolver.get_callers("target.py:5")
        assert len(callers) == 2
        assert "caller.py:10" in callers
        assert "caller.py:20" in callers

    def test_get_callees(self, sample_graph: CodeGraph) -> None:
        from codegraph.graph import CallEdge

        sample_graph.add_edge(
            CallEdge(
                caller="caller.py:5",
                callee="callee1.py:10",
                call_type="direct",
                line=5,
            )
        )
        sample_graph.add_edge(
            CallEdge(
                caller="caller.py:5",
                callee="callee2.py:20",
                call_type="direct",
                line=5,
            )
        )

        resolver = CrossRefResolver(sample_graph)
        callees = resolver.get_callees("caller.py:5")
        assert len(callees) == 2

    def test_get_dependencies(self, sample_graph: CodeGraph) -> None:
        from codegraph.graph import ImportInfo

        sample_graph.imports.append(
            ImportInfo(
                source_file="main.py",
                module="os",
                names=["path"],
                is_relative=False,
                line=1,
                kind="import",
            )
        )
        sample_graph.imports.append(
            ImportInfo(
                source_file="main.py",
                module="json",
                names=["loads"],
                is_relative=False,
                line=2,
                kind="import",
            )
        )

        resolver = CrossRefResolver(sample_graph)
        deps = resolver.get_dependencies("main.py")
        assert "os" in deps
        assert "json" in deps

    def test_get_dependents(self, sample_graph: CodeGraph) -> None:
        from codegraph.graph import ImportInfo

        sample_graph.imports.append(
            ImportInfo(
                source_file="a.py",
                module="shared.py",
                names=["helper"],
                is_relative=True,
                line=1,
                kind="from_import",
            )
        )
        sample_graph.imports.append(
            ImportInfo(
                source_file="b.py",
                module="shared.py",
                names=["helper"],
                is_relative=True,
                line=1,
                kind="from_import",
            )
        )

        resolver = CrossRefResolver(sample_graph)
        dependents = resolver.get_dependents("shared.py")
        assert "a.py" in dependents
        assert "b.py" in dependents


# --- GraphQuery Tests ---


@pytest.fixture
def sample_graph() -> CodeGraph:
    return CodeGraph(root_path="/test")


class TestGraphQuery:
    def test_search_by_name(self, sample_graph: CodeGraph) -> None:
        sample_graph.add_symbol(
            Symbol(
                name="UserModel",
                kind="class",
                file="models.py",
                line=1,
                column=0,
            )
        )
        sample_graph.add_symbol(
            Symbol(
                name="UserController",
                kind="class",
                file="controllers.py",
                line=5,
                column=0,
            )
        )
        sample_graph.add_symbol(
            Symbol(
                name="helper",
                kind="function",
                file="utils.py",
                line=10,
                column=0,
            )
        )

        query = GraphQuery(sample_graph)
        results = query.search("User")
        assert len(results) == 2
        names = {r["name"] for r in results}
        assert "UserModel" in names
        assert "UserController" in names

    def test_search_with_kind_filter(self, sample_graph: CodeGraph) -> None:
        sample_graph.add_symbol(
            Symbol(
                name="UserModel",
                kind="class",
                file="models.py",
                line=1,
                column=0,
            )
        )
        sample_graph.add_symbol(
            Symbol(
                name="UserService",
                kind="function",
                file="services.py",
                line=5,
                column=0,
            )
        )

        query = GraphQuery(sample_graph)
        results = query.search("User", kind="class")
        assert len(results) == 1
        assert results[0]["name"] == "UserModel"

    def test_search_by_docstring(self, sample_graph: CodeGraph) -> None:
        sample_graph.add_symbol(
            Symbol(
                name="getUser",
                kind="function",
                file="api.py",
                line=1,
                column=0,
                docstring="Get a user by ID",
            )
        )

        query = GraphQuery(sample_graph)
        results = query.search("user by ID")
        assert len(results) == 1
        assert results[0]["name"] == "getUser"

    def test_get_symbol(self, sample_graph: CodeGraph) -> None:
        sample_graph.add_symbol(
            Symbol(
                name="foo",
                kind="function",
                file="test.py",
                line=42,
                column=0,
                signature="def foo(x: int) -> str",
                docstring="A test function",
            )
        )

        query = GraphQuery(sample_graph)
        result = query.get_symbol("test.py", 42)
        assert result is not None
        assert result["name"] == "foo"
        assert result["signature"] == "def foo(x: int) -> str"

    def test_get_symbol_not_found(self, sample_graph: CodeGraph) -> None:
        query = GraphQuery(sample_graph)
        result = query.get_symbol("test.py", 999)
        assert result is None

    def test_get_functions(self, sample_graph: CodeGraph) -> None:
        sample_graph.add_symbol(
            Symbol(
                name="foo",
                kind="function",
                file="a.py",
                line=1,
                column=0,
            )
        )
        sample_graph.add_symbol(
            Symbol(
                name="bar",
                kind="function",
                file="b.py",
                line=1,
                column=0,
            )
        )
        sample_graph.add_symbol(
            Symbol(
                name="baz",
                kind="method",
                file="a.py",
                line=10,
                column=4,
            )
        )

        query = GraphQuery(sample_graph)
        all_funcs = query.get_functions()
        assert len(all_funcs) == 3

        a_funcs = query.get_functions("a.py")
        assert len(a_funcs) == 2

    def test_get_classes(self, sample_graph: CodeGraph) -> None:
        sample_graph.add_symbol(
            Symbol(
                name="MyClass",
                kind="class",
                file="a.py",
                line=1,
                column=0,
            )
        )
        sample_graph.add_symbol(
            Symbol(
                name="OtherClass",
                kind="class",
                file="b.py",
                line=5,
                column=0,
            )
        )

        query = GraphQuery(sample_graph)
        classes = query.get_classes()
        assert len(classes) == 2
        names = {c["name"] for c in classes}
        assert "MyClass" in names

    def test_get_imports(self, sample_graph: CodeGraph) -> None:
        from codegraph.graph import ImportInfo

        sample_graph.imports.append(
            ImportInfo(
                source_file="main.py",
                module="os",
                names=["path"],
                is_relative=False,
                line=1,
                kind="import",
            )
        )

        query = GraphQuery(sample_graph)
        imports = query.get_imports("main.py")
        assert len(imports) == 1
        assert imports[0]["module"] == "os"

    def test_get_call_graph(self, sample_graph: CodeGraph) -> None:
        from codegraph.graph import CallEdge

        sample_graph.add_edge(
            CallEdge(
                caller="main.py:10",
                callee="helper.py:5",
                call_type="direct",
                line=10,
            )
        )

        query = GraphQuery(sample_graph)
        graph = query.get_call_graph("main.py:10")
        assert graph["key"] == "main.py:10"
        assert len(graph["callees"]) == 1
        assert graph["callees"][0]["callee"] == "helper.py:5"

    def test_get_summary(self, sample_graph: CodeGraph) -> None:
        sample_graph.add_symbol(
            Symbol(
                name="foo",
                kind="function",
                file="a.py",
                line=1,
                column=0,
            )
        )
        sample_graph.add_symbol(
            Symbol(
                name="Bar",
                kind="class",
                file="b.py",
                line=5,
                column=0,
            )
        )

        query = GraphQuery(sample_graph)
        summary = query.get_summary()
        assert summary["total_symbols"] >= 2
        assert summary["total_functions"] >= 1
        assert summary["total_classes"] >= 1
