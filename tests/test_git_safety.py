from __future__ import annotations

from pathlib import Path

from governance_bootstrap.git_safety import inspect, sync_main_safe


def test_inspection_is_bounded_and_sync_refuses_missing_remote(tmp_path: Path) -> None:
    assert inspect(tmp_path)["repository"] is False
    assert "not a Git repository" in sync_main_safe(tmp_path)
