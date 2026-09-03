from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from tools import governance_toolkit


ROOT = Path(__file__).resolve().parents[2]


def test_public_agent_governance_bundle_is_complete() -> None:
    report = governance_toolkit.validate_bundle(ROOT)
    assert report == {
        "schema_version": "agent_governance_bundle_report_v1",
        "bundle": "agent_governance",
        "required_default_tool_count": 2,
        "optional_audit_trial_count": 0,
        "valid": True,
    }


def test_default_tool_profile_rejects_nondefault_audit_tool(tmp_path: Path) -> None:
    profile_root = tmp_path / "toolkit/agent_governance"
    profile_root.mkdir(parents=True)
    for relative in (
        "toolkit/agent_governance/component_manifest_v1.json",
        "toolkit/agent_governance/dependency_profile_v1.json",
    ):
        source = ROOT / relative
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    profile_path = tmp_path / "toolkit/agent_governance/dependency_profile_v1.json"
    profile = json.loads(profile_path.read_text(encoding="utf-8"))
    profile["required_default_tools"][0]["package"] = "pylint"
    profile_path.write_text(json.dumps(profile), encoding="utf-8")

    with pytest.raises(governance_toolkit.GovernanceToolkitError, match="prohibited default tool"):
        governance_toolkit.validate_bundle(tmp_path)


def test_bundle_data_validates_from_a_standalone_copy(tmp_path: Path) -> None:
    for relative in (
        "toolkit/agent_governance/component_manifest_v1.json",
        "toolkit/agent_governance/dependency_profile_v1.json",
    ):
        source = ROOT / relative
        target = tmp_path / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")

    assert governance_toolkit.validate_bundle(tmp_path)["valid"] is True


def test_public_bundle_files_do_not_contain_absolute_paths_or_external_identity() -> None:
    candidate_files = [
        ROOT / "toolkit/README.md",
        ROOT / "toolkit/agent_governance/README.md",
        ROOT / "toolkit/agent_governance/component_manifest_v1.json",
        ROOT / "toolkit/agent_governance/dependency_profile_v1.json",
        ROOT / "tools/governance_toolkit.py",
        ROOT / "tools/role_validation.py",
    ]
    absolute_path = re.compile(r"(?:^[A-Za-z]:[\\/]|(?:^|[\s\"'])/(?:home|users|var|tmp)/)", re.IGNORECASE)
    assert not [
        path.relative_to(ROOT).as_posix()
        for path in candidate_files
        if absolute_path.search(path.read_text(encoding="utf-8"))
    ]
