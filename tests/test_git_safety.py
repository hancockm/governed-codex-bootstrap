from __future__ import annotations

from pathlib import Path

import governance_bootstrap.git_safety as git_safety
from governance_bootstrap.git_safety import inspect, sync_main_safe


def test_inspection_is_bounded_and_sync_refuses_missing_remote(tmp_path: Path) -> None:
    assert inspect(tmp_path)["repository"] is False
    assert "Git inspection failed" in sync_main_safe(tmp_path, agent="core")


def test_failed_status_inspection_is_never_clean(monkeypatch, tmp_path: Path) -> None:
    def failed_status(_root: Path, *args: str) -> tuple[int, str]:
        if args[:2] == ("status", "--porcelain=v1"):
            return 1, "status failed"
        return 0, ".git" if args == ("rev-parse", "--git-dir") else "master"

    monkeypatch.setattr(git_safety, "git", failed_status)
    report = git_safety.inspect(tmp_path)
    assert report["inspection_failed"] is True
    assert report["clean"] is False


def test_sync_main_is_core_only(tmp_path: Path) -> None:
    assert "sync-main is Core-only" in sync_main_safe(tmp_path, agent="terra")
