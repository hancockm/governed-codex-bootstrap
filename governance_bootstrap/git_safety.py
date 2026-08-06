"""Bounded Git inspection and fast-forward-only primary synchronization."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any


def git(root: Path, *args: str) -> tuple[int, str]:
    """Run a bounded Git command without shell interpolation."""
    completed = subprocess.run(["git", *args], cwd=root, text=True, capture_output=True, check=False)
    return completed.returncode, (completed.stdout + completed.stderr).strip()


def _git_dir(root: Path) -> Path | None:
    code, value = git(root, "rev-parse", "--git-dir")
    if code or not value:
        return None
    path = Path(value)
    return path if path.is_absolute() else root / path


def inspect(root: Path) -> dict[str, Any]:
    """Return state without calling a mutating Git command.

    Any query failure is an inspection failure and is explicitly never reported as
    clean. Untracked files are included because primary synchronization must not
    overwrite a local checkout's unowned state.
    """
    status_code, status = git(root, "status", "--porcelain=v1", "--untracked-files=all")
    branch_code, branch = git(root, "branch", "--show-current")
    git_dir = _git_dir(root)
    repository = status_code == 0 and branch_code == 0 and git_dir is not None
    operation_markers = ("MERGE_HEAD", "CHERRY_PICK_HEAD", "REVERT_HEAD", "BISECT_LOG", "rebase-apply", "rebase-merge")
    active_operation = bool(git_dir and any((git_dir / marker).exists() for marker in operation_markers))
    inspection_failed = not repository
    return {
        "repository": repository,
        "inspection_failed": inspection_failed,
        "branch": branch if branch_code == 0 else "",
        "clean": repository and not bool(status),
        "status": status,
        "active_operation": active_operation,
    }


def sync_main_safe(root: Path, agent: str, branch: str = "master", no_fetch: bool = False) -> list[str]:
    """Safely fast-forward the primary checkout, never switching or discarding state.

    Only Core may run this operation. It may fetch and perform one
    `merge --ff-only origin/<branch>` after inspection proves the primary checkout
    is clean and contains no local-only commits. It never resets, rebases, checks
    out another branch, or removes files.
    """
    report = inspect(root)
    errors: list[str] = []
    if agent != "core":
        errors.append("sync-main is Core-only")
    if report["inspection_failed"]:
        errors.append("Git inspection failed")
    if report["branch"] != branch:
        errors.append(f"not on primary branch {branch}")
    if not report["clean"]:
        errors.append("worktree is not clean")
    if report["active_operation"]:
        errors.append("a Git operation is active")
    if errors:
        return errors
    if not no_fetch:
        code, detail = git(root, "fetch", "--prune", "origin")
        if code:
            return [f"fetch failed: {detail}"]
    remote_code, remote = git(root, "rev-parse", f"origin/{branch}")
    local_code, local = git(root, "rev-parse", branch)
    if remote_code or local_code:
        return ["origin primary branch is unavailable"]
    count_code, counts = git(root, "rev-list", "--left-right", "--count", f"origin/{branch}...{branch}")
    if count_code:
        return ["cannot determine local-only commits"]
    try:
        _remote_only, local_only = (int(value) for value in counts.split())
    except ValueError:
        return ["cannot parse local-only commit count"]
    if local_only:
        return ["primary checkout has local-only commits"]
    if local != remote:
        code, detail = git(root, "merge", "--ff-only", f"origin/{branch}")
        if code:
            return [f"fast-forward merge failed: {detail}"]
    final = inspect(root)
    final_local_code, final_local = git(root, "rev-parse", branch)
    final_remote_code, final_remote = git(root, "rev-parse", f"origin/{branch}")
    if final["inspection_failed"] or not final["clean"]:
        return ["post-sync inspection failed or worktree is not clean"]
    if final_local_code or final_remote_code or final_local != final_remote:
        return ["local primary branch is not synchronized with origin"]
    return []
