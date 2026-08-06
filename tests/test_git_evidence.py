from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from governance_bootstrap.git_safety import inspect, patch_equivalence


def git(root: Path, *args: str) -> str:
    """Run Git in an isolated fixture repository."""
    result = subprocess.run(["git", *args], cwd=root, text=True, capture_output=True, check=False)
    assert result.returncode == 0, result.stderr
    return result.stdout.strip()


def repository(tmp_path: Path) -> Path:
    """Create a configured clone with a bare origin/master."""
    bare = tmp_path / "origin.git"
    subprocess.run(["git", "init", "--bare", str(bare)], check=True, capture_output=True)
    root = tmp_path / "work"
    subprocess.run(["git", "clone", str(bare), str(root)], check=True, capture_output=True)
    git(root, "config", "user.email", "test@example.invalid")
    git(root, "config", "user.name", "Test")
    (root / "base.txt").write_text("base\n", encoding="utf-8")
    git(root, "add", ".")
    git(root, "commit", "-m", "base")
    git(root, "push", "-u", "origin", "master")
    return root


def commit(root: Path, name: str, text: str) -> str:
    """Create one nonempty file commit."""
    (root / name).write_text(text, encoding="utf-8")
    git(root, "add", name)
    git(root, "commit", "-m", name)
    return git(root, "rev-parse", "HEAD")


def test_patch_equivalence_exact_and_cherry_picked_mapping(tmp_path: Path) -> None:
    root = repository(tmp_path)
    git(root, "checkout", "-b", "feature")
    original = commit(root, "feature.txt", "feature\n")
    git(root, "checkout", "master")
    commit(root, "marker.txt", "marker\n")
    git(root, "cherry-pick", original)
    git(root, "push", "origin", "master")
    evidence = patch_equivalence(root, "feature")
    assert evidence["ok"] is True, evidence
    assert evidence["mappings"][0]["original"] == original


def test_patch_equivalence_rejects_unmappable_and_merge_commits(tmp_path: Path) -> None:
    root = repository(tmp_path)
    git(root, "checkout", "-b", "unmapped")
    commit(root, "unmapped.txt", "unmapped\n")
    assert patch_equivalence(root, "unmapped")["ok"] is False
    git(root, "checkout", "master")
    git(root, "checkout", "-b", "left")
    commit(root, "left.txt", "left\n")
    git(root, "checkout", "master")
    git(root, "checkout", "-b", "merge-branch")
    commit(root, "merge.txt", "merge\n")
    git(root, "merge", "--no-ff", "left", "-m", "merge left")
    assert any("merge commit" in item for item in patch_equivalence(root, "merge-branch")["unresolved"])


def test_patch_equivalence_rejects_ambiguous_patch_matches(tmp_path: Path) -> None:
    root = repository(tmp_path)
    git(root, "checkout", "-b", "feature")
    original = commit(root, "same.txt", "same\n")
    git(root, "checkout", "master")
    commit(root, "marker.txt", "marker\n")
    git(root, "cherry-pick", original)
    git(root, "revert", "HEAD", "--no-edit")
    git(root, "cherry-pick", original)
    git(root, "push", "origin", "master")
    evidence = patch_equivalence(root, "feature")
    assert evidence["ok"] is False
    assert any("ambiguous" in item for item in evidence["unresolved"])


def test_registered_missing_worktree_is_inspection_failure(tmp_path: Path) -> None:
    root = repository(tmp_path)
    sibling = tmp_path / "registered-worktree"
    git(root, "worktree", "add", "-b", "worktree-branch", str(sibling))
    shutil.rmtree(sibling)
    report = inspect(root)
    assert report["inspection_failed"] is True
    assert report["clean"] is False
