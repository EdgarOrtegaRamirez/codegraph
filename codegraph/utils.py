"""Utility functions for CodeGraph."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Generator

# Language -> file extensions mapping
LANGUAGE_EXTENSIONS: dict[str, list[str]] = {
    "python": [".py"],
    "javascript": [".js", ".mjs", ".cjs"],
    "typescript": [".ts", ".tsx", ".mts", ".cts"],
    "go": [".go"],
    "rust": [".rs"],
}

# All supported extensions (flat)
ALL_EXTENSIONS: set[str] = {
    ext for exts in LANGUAGE_EXTENSIONS.values() for ext in exts
}

# Default ignore patterns
DEFAULT_IGNORE: list[str] = [
    "node_modules",
    ".git",
    ".hg",
    ".svn",
    "__pycache__",
    ".pyc",
    ".pyo",
    ".egg-info",
    "build",
    "dist",
    ".venv",
    "venv",
    "env",
    ".tox",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "site-packages",
    ".next",
    ".nuxt",
    ".output",
    "dist",
    "target",
    "build",
]


def discover_files(
    root: str | Path,
    extensions: set[str] | None = None,
    ignore: list[str] | None = None,
) -> Generator[Path, None, None]:
    """Recursively discover source files in a directory.

    Args:
        root: Root directory to scan.
        extensions: Set of file extensions to include (e.g., {".py", ".ts"}).
                    If None, use ALL_EXTENSIONS.
        ignore: List of directory/file name patterns to ignore.
                If None, use DEFAULT_IGNORE.

    Yields:
        Paths to source files.
    """
    root = Path(root).resolve()
    if extensions is None:
        extensions = ALL_EXTENSIONS
    if ignore is None:
        ignore = DEFAULT_IGNORE

    if not root.is_dir():
        return

    for dirpath, dirnames, filenames in os.walk(root):
        # Modify dirnames in-place to skip ignored directories
        dirnames[:] = [d for d in dirnames if d not in ignore and not d.startswith(".")]
        dirnames.sort()  # Ensure deterministic order

        for filename in sorted(filenames):
            if any(filename == pat for pat in ignore):
                continue
            filepath = Path(dirpath) / filename
            if filepath.suffix in extensions:
                yield filepath.resolve()


def detect_language(filepath: Path) -> str | None:
    """Detect the programming language from file extension.

    Args:
        filepath: Path to the file.

    Returns:
        Language name (e.g., "python", "javascript") or None.
    """
    ext = filepath.suffix.lower()
    for lang, exts in LANGUAGE_EXTENSIONS.items():
        if ext in exts:
            return lang
    return None


def get_language_for_ext(ext: str) -> str | None:
    """Get language name from a file extension."""
    ext = ext.lower()
    for lang, exts in LANGUAGE_EXTENSIONS.items():
        if ext in exts:
            return lang
    return None


def rel_path(filepath: Path, root: Path) -> str:
    """Get relative path from root, using forward slashes."""
    try:
        return str(filepath.relative_to(root)).replace(os.sep, "/")
    except ValueError:
        return str(filepath)
