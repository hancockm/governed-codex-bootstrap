"""Validate the governed bootstrap's explicit reference-tool dispositions."""

from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "configs/tool_parity_v1.json"
CLASSIFICATIONS = {
    "full_generic_equivalent",
    "generic_adaptation",
    "project_specific_excluded",
    "bootstrap_native",
}


class ToolParityError(RuntimeError):
    """Raised when the tool-parity manifest is incomplete or inconsistent."""


def _symbols(path: Path) -> set[str]:
    """Return top-level function and class names declared by one Python file."""

    try:
        tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
    except (OSError, SyntaxError) as exc:
        raise ToolParityError(f"cannot inspect bootstrap tool: {path}") from exc
    return {
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    }


def validate_manifest(manifest: dict[str, Any], *, root: Path = ROOT) -> dict[str, Any]:
    """Validate classifications, file coverage, and required callable surfaces."""

    errors: list[str] = []
    if manifest.get("schema_version") != "governance_tool_parity_v1":
        errors.append("invalid schema_version")
    tools = manifest.get("tools")
    if not isinstance(tools, list) or not tools:
        errors.append("tools must be a non-empty list")
        tools = []
    reference_paths: set[str] = set()
    bootstrap_paths: set[str] = set()
    counts = {classification: 0 for classification in CLASSIFICATIONS}
    for index, item in enumerate(tools):
        label = f"tools[{index}]"
        if not isinstance(item, dict):
            errors.append(f"{label} must be an object")
            continue
        if set(item) != {
            "reference",
            "bootstrap",
            "classification",
            "required_symbols",
            "rationale",
        }:
            errors.append(f"{label} keys do not match the v1 schema")
            continue
        classification = item["classification"]
        if classification not in CLASSIFICATIONS:
            errors.append(f"{label} has an invalid classification")
            continue
        counts[classification] += 1
        reference = item["reference"]
        bootstrap = item["bootstrap"]
        symbols = item["required_symbols"]
        if not isinstance(item["rationale"], str) or not item["rationale"].strip():
            errors.append(f"{label} requires a rationale")
        if reference is not None:
            if not isinstance(reference, str) or reference in reference_paths:
                errors.append(f"{label} reference must be unique")
            else:
                reference_paths.add(reference)
        if classification == "project_specific_excluded":
            if bootstrap is not None or symbols != []:
                errors.append(f"{label} excluded tools cannot declare a bootstrap file")
            continue
        if not isinstance(bootstrap, str) or bootstrap in bootstrap_paths:
            errors.append(f"{label} bootstrap path must be unique")
            continue
        bootstrap_paths.add(bootstrap)
        path = (root / bootstrap).resolve()
        try:
            path.relative_to(root.resolve())
        except ValueError:
            errors.append(f"{label} bootstrap path escapes the repository")
            continue
        if not path.is_file():
            errors.append(f"{label} bootstrap tool is missing: {bootstrap}")
            continue
        if not isinstance(symbols, list) or not symbols or any(
            not isinstance(name, str) or not name for name in symbols
        ):
            errors.append(f"{label} requires symbol names")
            continue
        missing = sorted(set(symbols) - _symbols(path))
        if missing:
            errors.append(f"{label} is missing symbols: {', '.join(missing)}")

    actual = {
        path.relative_to(root).as_posix()
        for path in (root / "tools").glob("*.py")
        if path.name != "__init__.py"
    }
    unclassified = sorted(actual - bootstrap_paths)
    if unclassified:
        errors.append("unclassified bootstrap tools: " + ", ".join(unclassified))
    return {
        "schema_version": "governance_tool_parity_report_v1",
        "valid": not errors,
        "counts": counts,
        "classified_bootstrap_tools": len(bootstrap_paths),
        "errors": errors,
    }


def main(argv: list[str] | None = None) -> int:
    """Validate the configured parity manifest and print deterministic JSON."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    args = parser.parse_args(argv)
    try:
        manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
        report = validate_manifest(manifest)
    except (OSError, json.JSONDecodeError, ToolParityError) as exc:
        report = {
            "schema_version": "governance_tool_parity_report_v1",
            "valid": False,
            "counts": {},
            "classified_bootstrap_tools": 0,
            "errors": [str(exc)],
        }
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
