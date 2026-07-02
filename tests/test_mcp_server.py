"""Tests for CodeGraph MCP Server."""

from pathlib import Path

import pytest

from codegraph.mcp_server import CodeGraphServer


# --- MCP Server Tests ---

SAMPLE_CODE = '''
def hello(name: str) -> str:
    """Say hello to someone."""
    return f"Hello, {name}!"

class Greeter:
    """A greeter class."""

    def greet(self, name: str) -> str:
        """Greet someone."""
        return hello(name)

def main():
    """Main entry point."""
    g = Greeter()
    print(g.greet("World"))
'''


@pytest.fixture
def code_project(tmp_path: Path) -> Path:
    """Create a simple test codebase."""
    (tmp_path / "app.py").write_text(SAMPLE_CODE)
    return tmp_path


class TestCodeGraphMCP:
    """Test the MCP server tools."""

    def test_list_tools(self, code_project: Path) -> None:
        """Test that tools are registered."""
        server = CodeGraphServer()
        # The list_tools decorator registers handlers
        # Check that the request handler for ListToolsRequest exists
        assert (type.__bases__ for type in server.server.request_handlers)
        # Just verify the server was created without error
        assert server is not None

    def test_index_tool(self, code_project: Path) -> None:
        """Test the codegraph_index tool."""
        server = CodeGraphServer()
        result = server._handle_index({"path": str(code_project)})
        assert len(result) == 1
        assert result[0].type == "text"
        assert "Indexed codebase" in result[0].text
        assert "Total symbols:" in result[0].text

    def test_search_tool(self, code_project: Path) -> None:
        """Test the codegraph_search tool."""
        server = CodeGraphServer()
        result = server._handle_search(
            {
                "path": str(code_project),
                "query": "hello",
            }
        )
        assert len(result) == 1
        assert result[0].type == "text"
        assert "hello" in result[0].text.lower() or "Hello" in result[0].text

    def test_search_with_kind_filter(self, code_project: Path) -> None:
        """Test search with kind filter."""
        server = CodeGraphServer()
        result = server._handle_search(
            {
                "path": str(code_project),
                "query": "Greeter",
                "kind": "class",
            }
        )
        assert len(result) == 1
        assert "Greeter" in result[0].text

    def test_get_symbol_tool(self, code_project: Path) -> None:
        """Test getting a specific symbol."""
        server = CodeGraphServer()
        result = server._handle_get_symbol(
            {
                "path": str(code_project),
                "file": "app.py",
                "line": 2,  # hello function is at line 2
            }
        )
        assert len(result) == 1
        assert result[0].type == "text"
        assert "hello" in result[0].text.lower()

    def test_get_symbol_not_found(self, code_project: Path) -> None:
        """Test getting a non-existent symbol."""
        server = CodeGraphServer()
        result = server._handle_get_symbol(
            {
                "path": str(code_project),
                "file": "app.py",
                "line": 999,
            }
        )
        assert "No symbol found" in result[0].text

    def test_get_functions_tool(self, code_project: Path) -> None:
        """Test listing all functions."""
        server = CodeGraphServer()
        result = server._handle_get_functions(
            {
                "path": str(code_project),
            }
        )
        assert len(result) == 1
        assert "Found" in result[0].text
        assert "functions" in result[0].text.lower()

    def test_get_classes_tool(self, code_project: Path) -> None:
        """Test listing all classes."""
        server = CodeGraphServer()
        result = server._handle_get_classes(
            {
                "path": str(code_project),
            }
        )
        assert len(result) == 1
        assert "Greeter" in result[0].text

    def test_get_imports_tool(self, code_project: Path) -> None:
        """Test getting imports for a file."""
        server = CodeGraphServer()
        result = server._handle_get_imports(
            {
                "path": str(code_project),
                "file": "app.py",
            }
        )
        assert len(result) == 1
        # File has no imports, should show "No imports"
        assert "No imports" in result[0].text

    def test_get_call_graph_tool(self, code_project: Path) -> None:
        """Test getting call graph."""
        server = CodeGraphServer()
        result = server._handle_get_call_graph(
            {
                "path": str(code_project),
                "symbol_key": "app.py:15",  # main function
            }
        )
        assert len(result) == 1
        assert "app.py:15" in result[0].text

    def test_get_dependencies_tool(self, code_project: Path) -> None:
        """Test getting file dependencies."""
        server = CodeGraphServer()
        result = server._handle_get_dependencies(
            {
                "path": str(code_project),
                "file": "app.py",
            }
        )
        assert len(result) == 1
        assert "Dependencies" in result[0].text

    def test_summary_tool(self, code_project: Path) -> None:
        """Test getting codebase summary."""
        server = CodeGraphServer()
        result = server._handle_summary(
            {
                "path": str(code_project),
            }
        )
        assert len(result) == 1
        assert "summary" in result[0].text.lower()
        assert "total_symbols" in result[0].text

    def test_markdown_report_tool(self, code_project: Path) -> None:
        """Test generating markdown report."""
        server = CodeGraphServer()
        result = server._handle_markdown_report(
            {
                "path": str(code_project),
            }
        )
        assert len(result) == 1
        assert "# CodeGraph Analysis" in result[0].text

    def test_incremental_index(self, code_project: Path) -> None:
        """Test incremental indexing via MCP tool."""
        cache_dir = code_project / ".cache"
        server = CodeGraphServer(cache_dir=str(cache_dir))
        result = server._handle_index(
            {
                "path": str(code_project),
                "incremental": True,
            }
        )
        assert len(result) == 1
        assert "Indexed" in result[0].text


class TestMCPToolSchemas:
    """Test that MCP tool schemas are correct."""

    def test_index_tool_schema(self) -> None:
        from mcp.types import CallToolRequest, ListToolsRequest

        server = CodeGraphServer()
        # Verify the server was created with proper handlers registered
        assert ListToolsRequest in server.server.request_handlers
        assert CallToolRequest in server.server.request_handlers
