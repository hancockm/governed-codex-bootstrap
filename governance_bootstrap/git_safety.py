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
    worktree_code, worktree_output = git(root, "worktree", "list", "--porcelain")
    registered_worktrees = [line.removeprefix("worktree ") for line in worktree_output.splitlines() if line.startswith("worktree ")]
    worktree_statuses = []
    worktree_failed = worktree_code != 0
    for location in registered_worktrees:
        status_code, worktree_status = git(Path(location), "status", "--porcelain=v1", "--untracked-files=all")
        worktree_statuses.append({"path": location, "clean": status_code == 0 and not bool(worktree_status), "status": worktree_status, "inspection_failed": status_code != 0})
        worktree_failed = worktree_failed or status_code != 0
    physical_root = root / ".worktrees"
    physical_worktrees = sorted(item.name for item in physical_root.iterdir() if item.is_dir()) if physical_root.is_dir() else []
    inspection_failed = not repository or worktree_failed
    return {
        "repository": repository,
        "inspection_failed": inspection_failed,
        "branch": branch if branch_code == 0 else "",
        "clean": repository and not bool(status),
        "status": status,
        "active_operation": active_operation,
        "registered_worktrees": registered_worktrees,
        "physical_worktrees": physical_worktrees,
        "worktree_statuses": worktree_statuses,
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


def patch_equivalence(root: Path, branch: str, base: str = "origin/master") -> dict[str, object]:
    """Map every non-merge branch-only commit to one stable patch-id replacement.

    Empty diffs, merge commits, missing patch IDs, and non-unique target matches are
    unresolved. The result is suitable for evidence reporting, never merge authority.
    """
    code, branch_output = git(root, "rev-list", "--no-merges", f"{base}..{branch}")
    if code:
        return {"ok": False, "mappings": [], "unresolved": ["cannot enumerate branch-only commits"]}
    branch_commits = [item for item in branch_output.splitlines() if item]
    merge_code, merges = git(root, "rev-list", "--merges", f"{base}..{branch}")
    if merge_code:
        return {"ok": False, "mappings": [], "unresolved": ["cannot enumerate merge commits"]}
    code, main_output = git(root, "rev-list", "--no-merges", base)
    if code:
        return {"ok": False, "mappings": [], "unresolved": ["cannot enumerate target commits"]}
    def patch_id(commit: str) -> str | None:
        show = subprocess.run(["git", "show", "--pretty=format:", "--no-ext-diff", commit], cwd=root, text=True, capture_output=True, check=False)
        if show.returncode or not show.stdout.strip():
            return None
        patched = subprocess.run(["git", "patch-id", "--stable"], cwd=root, text=True, input=show.stdout, capture_output=True, check=False)
        return patched.stdout.split()[0] if patched.returncode == 0 and patched.stdout.split() else None
    target_ids: dict[str, list[str]] = {}
    for commit in main_output.splitlines():
        identifier = patch_id(commit)
        if identifier:
            target_ids.setdefault(identifier, []).append(commit)
    mappings, unresolved = [], [f"merge commit: {commit}" for commit in merges.splitlines() if commit]
    for commit in branch_commits:
        identifier = patch_id(commit)
        matches = target_ids.get(identifier or "", [])
        if not identifier:
            unresolved.append(f"unmappable commit: {commit}")
        elif len(matches) != 1:
            unresolved.append(f"ambiguous or absent patch-id match: {commit}")
        else:
            mappings.append({"original": commit, "replacement": matches[0], "patch_id": identifier})
    return {"ok": bool(branch_commits) and not unresolved and len(mappings) == len(branch_commits), "mappings": mappings, "unresolved": unresolved}
