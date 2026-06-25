"""Base parser interface for CodeGraph."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from codegraph.graph import CodeGraph


class BaseParser(ABC):
    """Abstract base class for language parsers."""

    @abstractmethod
    def parse_file(self, filepath: Path, graph: CodeGraph) -> None:
        """Parse a single file and add its symbols to the graph.

        Args:
            filepath: Absolute path to the file.
            graph: The CodeGraph to populate.
        """
        ...

    @property
    @abstractmethod
    def supported_extensions(self) -> set[str]:
        """Set of file extensions this parser handles."""
        ...

    @property
    @abstractmethod
    def language(self) -> str:
        """Language name this parser handles."""
        ...
