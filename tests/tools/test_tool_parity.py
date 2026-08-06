from __future__ import annotations

import ast
import copy
import json
from pathlib import Path

from tools import tool_parity


ROOT = Path(__file__).resolve().parents[2]


def _manifest() -> dict:
    return json.loads((ROOT / "configs/tool_parity_v1.json").read_text(encoding="utf-8"))


def test_repository_tool_manifest_is_complete() -> None:
    report = tool_parity.validate_manifest(_manifest())
    assert report["valid"], report["errors"]
    assert report["counts"]["full_generic_equivalent"] >= 8
    assert report["counts"]["project_specific_excluded"] >= 1


def test_unclassified_tool_fails_closed(tmp_path: Path) -> None:
    (tmp_path / "tools").mkdir()
    (tmp_path / "tools/unlisted.py").write_text("def main(): pass\n", encoding="utf-8")
    manifest = {
        "schema_version": "governance_tool_parity_v1",
        "tools": [],
    }
    report = tool_parity.validate_manifest(manifest, root=tmp_path)
    assert not report["valid"]


def test_missing_required_callable_is_reported(tmp_path: Path) -> None:
    (tmp_path / "tools").mkdir()
    (tmp_path / "tools/example.py").write_text("def present(): pass\n", encoding="utf-8")
    manifest = {
        "schema_version": "governance_tool_parity_v1",
        "tools": [{
            "reference": "tools/example.py",
            "bootstrap": "tools/example.py",
            "classification": "full_generic_equivalent",
            "required_symbols": ["missing"],
            "rationale": "test",
        }],
    }
    report = tool_parity.validate_manifest(manifest, root=tmp_path)
    assert not report["valid"]
    assert "missing symbols" in " ".join(report["errors"])


def test_parity_tool_has_no_repository_write_calls() -> None:
    tree = ast.parse((ROOT / "tools/tool_parity.py").read_text(encoding="utf-8"))
    forbidden = {"write_text", "write_bytes", "mkdir", "unlink", "rename", "replace"}
    assert not {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
        and node.func.attr in forbidden
    }
