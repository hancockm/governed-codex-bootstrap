"""Bounded, non-destructive Git safety checks."""

from __future__ import annotations

import subprocess
from pathlib import Path


def git(root: Path, *args: str) -> tuple[int, str]:
    """Run a bounded Git query without shell interpolation."""
    completed = subprocess.run(["git", *args], cwd=root, text=True, capture_output=True, check=False)
    return completed.returncode, (completed.stdout + completed.stderr).strip()


def inspect(root: Path) -> dict[str, str | bool]:
    """Return repository state without changing it."""
    _, status = git(root, "status", "--short")
    code, branch = git(root, "branch", "--show-current")
    return {"repository": code == 0, "branch": branch, "clean": not bool(status), "status": status}


def sync_main_safe(root: Path, branch: str = "master") -> list[str]:
    """Verify a clean primary checkout is already synchronized; never mutate Git."""
    report = inspect(root)
    errors: list[str] = []
    if not report["repository"]:
        errors.append("not a Git repository")
    if report["branch"] != branch:
        errors.append(f"not on primary branch {branch}")
    if not report["clean"]:
        errors.append("worktree is not clean")
    local_code, local = git(root, "rev-parse", branch)
    remote_code, remote = git(root, "rev-parse", f"origin/{branch}")
    if local_code != 0 or remote_code != 0:
        errors.append("origin primary branch is unavailable")
    elif local != remote:
        errors.append("local primary branch is not synchronized with origin")
    return errors
