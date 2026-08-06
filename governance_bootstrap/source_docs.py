"""AST-based public source-documentation audit for the project package."""

from __future__ import annotations

import ast
from pathlib import Path


def audit_package(package_root: Path) -> list[str]:
    """Return missing public docstring or annotation diagnostics deterministically."""
    findings: list[str] = []
    for path in sorted(package_root.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and not node.name.startswith("_"):
                label = f"{path.name}:{node.name}"
                if not ast.get_docstring(node):
                    findings.append(f"missing docstring: {label}")
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    arguments = [*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs]
                    if any(argument.annotation is None for argument in arguments) or node.returns is None:
                        findings.append(f"missing annotation: {label}")
    return findings
