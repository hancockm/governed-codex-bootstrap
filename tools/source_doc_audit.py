"""Audit project-owned source for public docstring coverage.

Examples:
    python tools/source_doc_audit.py
    python tools/source_doc_audit.py governance_bootstrap tools
"""

from __future__ import annotations

import argparse
import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


DEFAULT_ROOTS = (Path("governance_bootstrap"), Path("tools"))
IGNORED_PARTS = {"__pycache__", ".git", ".mypy_cache", ".pytest_cache", ".venv", "venv"}
IGNORED_PUBLIC_DUNDERS = {"__repr__", "__str__", "__eq__", "__hash__"}
PUBLIC_DUNDERS = {"__init__", "__call__"}


@dataclass(frozen=True)
class MissingDocstring:
    """One missing public docstring found by the audit.

    Attributes:
        path: Python file path relative to the current working directory when
            available.
        kind: Public object kind, such as `module`, `function`, or `method`.
        name: Object name. Module rows use an empty name.
        line: One-based source line number.
    """

    path: Path
    kind: str
    name: str
    line: int

    def format(self) -> str:
        """Return a compact human-readable row."""

        label = self.kind if not self.name else f"{self.kind} {self.name}"
        return f"{self.path}:{self.line}: missing public docstring for {label}"


def find_missing_docstrings(paths: Iterable[Path]) -> list[MissingDocstring]:
    """Return missing docstrings for public modules and objects.

    Args:
        paths: Files or directories to scan recursively.

    Returns:
        Sorted missing-docstring records for project-owned Python files.

    Raises:
        SyntaxError: If a scanned Python file cannot be parsed.
    """

    missing: list[MissingDocstring] = []
    for path in _python_files(paths):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        if ast.get_docstring(tree) is None:
            missing.append(MissingDocstring(path=path, kind="module", name="", line=1))
        missing.extend(_public_top_level_missing(path, tree))
    return sorted(missing, key=lambda item: (str(item.path), item.line, item.kind, item.name))


def main(argv: list[str] | None = None) -> int:
    """Run the source documentation audit command."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "paths",
        nargs="*",
        default=[str(path) for path in DEFAULT_ROOTS],
        help="Python files or directories to scan. Defaults to governance_bootstrap and tools.",
    )
    args = parser.parse_args(argv)

    missing = find_missing_docstrings(Path(path) for path in args.paths)
    if missing:
        for item in missing:
            print(item.format())
        print(f"\n{len(missing)} public docstring gap(s) found.")
        return 1
    print("Source documentation audit passed.")
    return 0


def _python_files(paths: Iterable[Path]) -> list[Path]:
    files: list[Path] = []
    for path in paths:
        if path.is_file() and path.suffix == ".py" and not _ignored(path):
            files.append(path)
        elif path.is_dir():
            files.extend(candidate for candidate in path.rglob("*.py") if not _ignored(candidate))
    return sorted(files)


def _ignored(path: Path) -> bool:
    return any(part in IGNORED_PARTS for part in path.parts)


def _public_top_level_missing(path: Path, tree: ast.Module) -> list[MissingDocstring]:
    missing: list[MissingDocstring] = []
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and _is_public_name(node.name):
            if ast.get_docstring(node) is None:
                missing.append(MissingDocstring(path=path, kind="class", name=node.name, line=node.lineno))
            missing.extend(_public_method_missing(path, node))
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and _is_public_name(node.name):
            if ast.get_docstring(node) is None:
                missing.append(MissingDocstring(path=path, kind="function", name=node.name, line=node.lineno))
    return missing


def _public_method_missing(path: Path, node: ast.ClassDef) -> list[MissingDocstring]:
    missing: list[MissingDocstring] = []
    for child in node.body:
        if not isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if child.name in IGNORED_PUBLIC_DUNDERS:
            continue
        if not _is_public_name(child.name):
            continue
        if ast.get_docstring(child) is None:
            missing.append(MissingDocstring(path=path, kind=f"{node.name}.method", name=child.name, line=child.lineno))
    return missing


def _is_public_name(name: str) -> bool:
    return not name.startswith("_") or name in PUBLIC_DUNDERS


if __name__ == "__main__":
    raise SystemExit(main())
