from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]


def _run(
    root: Path,
    tool: str,
    *args: str,
    environment: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    """Run one repository tool without assuming successful output."""

    return subprocess.run(
        [sys.executable, f"tools/{tool}", *args],
        cwd=root,
        env=environment,
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


def test_external_critique_loads_allowlisted_dotenv_and_records_safe_evidence(
    tmp_path: Path,
) -> None:
    sample = tmp_path / "sample"
    shutil.copytree(ROOT, sample, ignore=shutil.ignore_patterns(".git", "tmp", "__pycache__"))
    subprocess.run(["git", "init", "-q"], cwd=sample, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.invalid"], cwd=sample, check=True)
    subprocess.run(["git", "config", "user.name", "Test"], cwd=sample, check=True)
    subprocess.run(["git", "add", "."], cwd=sample, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "fixture"], cwd=sample, check=True)

    provider = tmp_path / "provider.py"
    provider.write_text(
        "import sys\n"
        "prompt = sys.argv[-1]\n"
        "assert 'Proposed plan:' in prompt\n"
        "preamble = "
        + repr(
            "Be critical of this input. You need to be analytical in your response.  "
            "Do not take this as the answer. Look at the weak points in the argument. "
            "Let's begin to list areas of common agreement. List areas of disagreement. "
            "The goal for each iteration is to reduce one disagreement. If each round, "
            "you eliminate one disagreement but add 2 disagreements you are going in the wrong direction.  "
            "We need to converge on a plan. List ALL remaining disagreements. "
            "Don't keep adding them after each round."
        )
        + "\n"
        "headings = ('## Common Agreement', '## All Remaining Disagreements', "
        "'## Critical Weak Points', '## Convergence Move', '## Decision Status')\n"
        "print(preamble + '\\n\\n' + '\\n\\n'.join(h + '\\n\\nReviewed.' for h in headings))\n",
        encoding="utf-8",
    )
    (sample / ".env").write_text(
        f"PROJECT_CLAUDE_COMMAND={sys.executable} {provider}\n"
        "PROJECT_CLAUDE_INPUT_MODE=argument\n"
        "PROJECT_CLAUDE_MODEL_ID=claude-test-exact\n"
        "PROJECT_CLAUDE_API_KEY=must_be_ignored\n",
        encoding="utf-8",
    )
    plan = sample / "plan.md"
    plan.write_text("bounded source plan\n", encoding="utf-8")
    clean_environment = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith("PROJECT_CLAUDE_")
    }
    result = _run(
        sample,
        "agent_to_agent_plan_handoff.py",
        "--topic",
        "external review",
        "--plan-file",
        str(plan),
        "--invoke",
        "claude",
        "--apply",
        environment=clean_environment,
    )
    assert result.returncode == 0, result.stderr + result.stdout
    payload = json.loads(result.stdout)
    record = (sample / payload["record"]).read_text(encoding="utf-8")
    assert '"provider": "claude"' in record
    assert '"model_id": "claude-test-exact"' in record
    assert '"input_mode": "argument"' in record
    assert '"command_sha256": "' in record
    assert str(provider) not in record
    assert "must_be_ignored" not in record
    runtime_directories = list((sample / "tmp/agent_handoff_logs").glob("runtime-*"))
    assert runtime_directories == []


def test_external_critique_process_environment_overrides_dotenv(tmp_path: Path) -> None:
    import importlib.util

    module_path = ROOT / "tools/agent_to_agent_plan_handoff.py"
    spec = importlib.util.spec_from_file_location("project_handoff_test", module_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "PROJECT_GEMINI_COMMAND=from-file\n"
        "PROJECT_GEMINI_INPUT_MODE=argument\n"
        "PROJECT_GEMINI_MODEL_ID=gemini-test-exact\n"
        "UNRELATED_SECRET=ignored\n",
        encoding="utf-8",
    )
    settings = module.load_local_provider_settings(
        env_file,
        environment={"PROJECT_GEMINI_COMMAND": "from-process"},
    )
    assert settings == {
        "PROJECT_GEMINI_COMMAND": "from-process",
        "PROJECT_GEMINI_INPUT_MODE": "argument",
        "PROJECT_GEMINI_MODEL_ID": "gemini-test-exact",
    }


def test_external_critique_rejects_missing_model_identity() -> None:
    import importlib.util

    module_path = ROOT / "tools/agent_to_agent_plan_handoff.py"
    spec = importlib.util.spec_from_file_location("project_handoff_model_test", module_path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.load_local_provider_settings = lambda: {
        "PROJECT_MMX_COMMAND": sys.executable,
        "PROJECT_MMX_INPUT_MODE": "stdin",
    }
    with pytest.raises(module.HandoffError, match="MODEL_ID is required"):
        module._invoke_external("mmx", "bounded prompt", identity="1" * 64)


def test_owner_and_capability_surfaces_are_noninvoking_checks() -> None:
    owner = _run(ROOT, "owner_scoped_orchestration.py", "check-owner", "--owner", "core", "--active")
    capability = _run(ROOT, "capability_status.py", "check")
    assert owner.returncode == 0, owner.stderr + owner.stdout
    assert capability.returncode == 0, capability.stderr + capability.stdout
