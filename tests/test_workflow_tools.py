from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _run(root: Path, tool: str, *args: str) -> subprocess.CompletedProcess[str]:
    """Run one repository tool without assuming successful output."""

    return subprocess.run(
        [sys.executable, f"tools/{tool}", *args],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )


def test_plan_handoff_dry_run_writes_nothing(tmp_path: Path) -> None:
    plan = tmp_path / "plan.md"
    plan.write_text("Research evidence is pending Core review.\n", encoding="utf-8")
    before = subprocess.run(
        ["git", "status", "--porcelain=v1", "--untracked-files=all"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    ).stdout
    result = _run(ROOT, "agent_to_agent_plan_handoff.py", "--topic", "cold start", "--plan-file", str(plan))
    assert result.returncode == 0, result.stderr + result.stdout
    payload = json.loads(result.stdout)
    assert payload["applied"] is False
    assert payload["canonical_promotion"] == "requires_owner_disposition"
    after = subprocess.run(
        ["git", "status", "--porcelain=v1", "--untracked-files=all"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=True,
    ).stdout
    assert after == before


def test_coordination_apply_is_content_addressed_and_idempotent(tmp_path: Path) -> None:
    sample = tmp_path / "sample"
    shutil.copytree(ROOT, sample, ignore=shutil.ignore_patterns(".git", "tmp", "__pycache__"))
    subprocess.run(["git", "init", "-q"], cwd=sample, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=sample, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=sample, check=True)
    subprocess.run(["git", "add", "."], cwd=sample, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "fixture"], cwd=sample, check=True)
    plan = sample / "plan.md"
    plan.write_text("source-only plan\n", encoding="utf-8")
    first = _run(sample, "agent_to_agent_plan_handoff.py", "--topic", "test", "--plan-file", str(plan), "--apply")
    assert first.returncode == 0, first.stderr + first.stdout
    first_payload = json.loads(first.stdout)
    record = sample / first_payload["record"]
    active = sample / "Project_Obsidian_Vault/40_Coordination/Generated/Active Records.md"
    updates = sample / "Project_Obsidian_Vault/40_Coordination/Generated/Critique Update Log.md"
    original = record.read_bytes()
    record_ref = record.relative_to(sample / "Project_Obsidian_Vault").with_suffix("").as_posix()
    assert record_ref in active.read_text(encoding="utf-8")
    assert first_payload["identity_sha256"] in updates.read_text(encoding="utf-8")
    discovery = _run(sample, "check_agent_discussion_updates.py")
    assert discovery.returncode == 0, discovery.stderr + discovery.stdout
    context = json.loads(discovery.stdout)["hookSpecificOutput"]["additionalContext"]
    assert first_payload["identity_sha256"] in context
    assert "test" in context
    second = _run(sample, "agent_to_agent_plan_handoff.py", "--topic", "test", "--plan-file", str(plan), "--apply")
    assert second.returncode == 0, second.stderr + second.stdout
    second_payload = json.loads(second.stdout)
    assert second_payload["record"] == first_payload["record"]
    assert record.read_bytes() == original


def test_owner_and_capability_surfaces_are_noninvoking_checks() -> None:
    owner = _run(ROOT, "owner_scoped_orchestration.py", "check-owner", "--owner", "core", "--active")
    capability = _run(ROOT, "capability_status.py", "check")
    assert owner.returncode == 0, owner.stderr + owner.stdout
    assert capability.returncode == 0, capability.stderr + capability.stdout
