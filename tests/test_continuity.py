from __future__ import annotations

import json
from pathlib import Path

from governance_bootstrap.continuity import export_bounded


def test_bounded_export_keeps_only_user_visible_safe_response_records(tmp_path: Path) -> None:
    source = tmp_path / "source.jsonl"
    source.write_text("\n".join([json.dumps({"type": "response_item", "role": "user", "content": "question"}), json.dumps({"type": "response_item", "role": "assistant", "content": "answer"}), json.dumps({"type": "tool_call", "name": "hidden"}), json.dumps({"type": "response_item", "role": "assistant", "content": "secret", "token": "x"})]) + "\n", encoding="utf-8")
    destination = tmp_path / "export.jsonl"
    result = export_bounded(source, destination, 4)
    assert result["selected_records"] == 2
    assert result["source_prefix"]["line_count"] == 4
    assert len(result["source_prefix"]["sha256"]) == 64
    assert len(result["selected_record_hashes"]) == 2
    assert "hidden" not in destination.read_text(encoding="utf-8")
    assert "secret" not in destination.read_text(encoding="utf-8")
    assert export_bounded(source, destination, 4) == result


def test_export_rejects_unfinished_source_line_prefix(tmp_path: Path) -> None:
    source = tmp_path / "source.jsonl"
    source.write_text(json.dumps({"type": "response_item", "role": "user", "content": "unfinished"}), encoding="utf-8")
    try:
        export_bounded(source, tmp_path / "export.jsonl", 1)
    except ValueError as error:
        assert "full-line" in str(error)
    else:
        raise AssertionError("partial line was accepted")
