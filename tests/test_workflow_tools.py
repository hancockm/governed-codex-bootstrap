from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def run_tool(name: str, *args: str) -> dict:
    """Run one documented tool and decode its deterministic JSON response."""
    result = subprocess.run([sys.executable, f"tools/{name}", *args], cwd=ROOT, text=True, capture_output=True, check=False)
    assert result.returncode == 0, result.stderr + result.stdout
    return json.loads(result.stdout)


def test_research_first_dry_run_workflow_writes_nothing(tmp_path: Path) -> None:
    plan = tmp_path / "plan.md"
    plan.write_text("Research evidence is pending Core review.\n", encoding="utf-8")
    audit = tmp_path / "audit.json"
    audit.write_text(json.dumps({"candidates": ["first capability"], "prerequisites": ["research"], "owner_dispositions": ["core"], "assumptions": ["source-only"]}), encoding="utf-8")
    index = ROOT / "Project_Obsidian_Vault/40_Coordination/Generated/Active Records.md"
    before = index.read_text(encoding="utf-8")
    handoff = run_tool("agent_to_agent_plan_handoff.py", "--topic", "cold start", "--plan-file", str(plan))
    selection = run_tool("agent_work_selection_audit.py", "--input", str(audit))
    assert handoff["applied"] is False and handoff["canonical_promotion"] == "requires_owner_disposition"
    assert selection["applied"] is False and selection["status"] == "advisory_non_gating"
    assert index.read_text(encoding="utf-8") == before


def test_owner_and_capability_surfaces_are_noninvoking_checks(tmp_path: Path) -> None:
    change = tmp_path / "change.json"
    change.write_text('{"triggers": ["cross_owner"]}', encoding="utf-8")
    assert run_tool("owner_scoped_orchestration.py", "classify", "--change-file", str(change))["risk"] == "high"
    assert run_tool("capability_status.py", "check")["ok"] is True


def test_coordination_apply_is_immutable_and_stays_in_registered_vault_scope(tmp_path: Path) -> None:
    sample = tmp_path / "sample"
    shutil.copytree(ROOT, sample, ignore=shutil.ignore_patterns(".git", "tmp", "__pycache__"))
    plan = sample / "plan.md"
    plan.write_text("source-only plan\n", encoding="utf-8")
    audit = sample / "audit.json"
    audit.write_text(json.dumps({"candidates": ["x"], "prerequisites": ["research"], "owner_dispositions": ["core"], "assumptions": ["frozen"]}), encoding="utf-8")
    def invoke(tool: str, *args: str) -> dict:
        result = subprocess.run([sys.executable, f"tools/{tool}", *args], cwd=sample, text=True, capture_output=True, check=False)
        assert result.returncode == 0, result.stderr + result.stdout
        return json.loads(result.stdout)
    handoff = invoke("agent_to_agent_plan_handoff.py", "--topic", "test", "--plan-file", str(plan), "--apply")
    selection = invoke("agent_work_selection_audit.py", "--input", str(audit), "--apply")
    for relative in (handoff["record"], selection["record"]):
        assert relative.startswith("40_Coordination/Generated/")
        assert (sample / "Project_Obsidian_Vault" / relative).is_file()
    assert invoke("vault_maintainer.py", "check")["ok"] is True
    assert invoke("agent_to_agent_plan_handoff.py", "--topic", "test", "--plan-file", str(plan), "--apply")["record"] == handoff["record"]
