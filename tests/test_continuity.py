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
    assert "hidden" not in destination.read_text(encoding="utf-8")
    assert "secret" not in destination.read_text(encoding="utf-8")
