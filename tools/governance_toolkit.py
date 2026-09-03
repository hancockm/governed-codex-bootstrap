"""Validate public governance-toolkit bundle data without network access."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = Path("toolkit/agent_governance/component_manifest_v1.json")
DEPENDENCY_PROFILE_PATH = Path("toolkit/agent_governance/dependency_profile_v1.json")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
ABSOLUTE_PATH = re.compile(r"(?:^[A-Za-z]:[\\/]|(?:^|[\s\"'])/(?:home|users|var|tmp)/)", re.IGNORECASE)
PROHIBITED_DEFAULT_TOOLS = frozenset({"jscpd", "pylint", "similar"})


class GovernanceToolkitError(RuntimeError):
    """Raised when public toolkit data is missing or invalid."""


def _load_json(path: Path) -> dict[str, Any]:
    """Load one JSON object from a repository-relative file."""

    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise GovernanceToolkitError(f"cannot load toolkit data: {path.as_posix()}") from exc
    if not isinstance(value, dict):
        raise GovernanceToolkitError("toolkit data must be a JSON object")
    return value


def _require_exact_keys(value: dict[str, Any], keys: set[str], label: str) -> None:
    """Require one object to use its complete declared key set."""

    if set(value) != keys:
        raise GovernanceToolkitError(f"{label} has missing or forbidden fields")


def _validate_tool_record(value: Any, label: str) -> None:
    """Validate one exact development-tool artifact record."""

    if not isinstance(value, dict):
        raise GovernanceToolkitError(f"{label} must be an object")
    _require_exact_keys(value, {"package", "version", "artifact", "sha256", "license"}, label)
    if any(not isinstance(value[field], str) or not value[field] for field in value):
        raise GovernanceToolkitError(f"{label} requires non-empty string fields")
    if not HEX64.fullmatch(value["sha256"]):
        raise GovernanceToolkitError(f"{label} requires a SHA-256 digest")
    if ABSOLUTE_PATH.search(" ".join(value.values())):
        raise GovernanceToolkitError(f"{label} cannot contain an absolute path")


def validate_bundle(root: Path = ROOT) -> dict[str, Any]:
    """Validate the public agent-governance bundle and return a report."""

    manifest = _load_json(root / MANIFEST_PATH)
    profile = _load_json(root / DEPENDENCY_PROFILE_PATH)
    _require_exact_keys(
        manifest,
        {"schema_version", "bundle", "dependency_profile", "verifier", "development_only", "network_egress"},
        "component manifest",
    )
    if manifest["schema_version"] != "agent_governance_component_manifest_v1":
        raise GovernanceToolkitError("component manifest schema is invalid")
    if manifest["bundle"] != "agent_governance":
        raise GovernanceToolkitError("component manifest bundle is invalid")
    if manifest["dependency_profile"] != DEPENDENCY_PROFILE_PATH.as_posix():
        raise GovernanceToolkitError("component manifest dependency profile is invalid")
    if manifest["verifier"] != "tools/governance_toolkit.py":
        raise GovernanceToolkitError("component manifest verifier is invalid")
    if manifest["development_only"] is not True or manifest["network_egress"] is not False:
        raise GovernanceToolkitError("component manifest execution posture is invalid")
    _require_exact_keys(
        profile,
        {"schema_version", "development_only", "network_egress", "required_default_tools", "optional_audit_trials"},
        "dependency profile",
    )
    if profile["schema_version"] != "agent_governance_dependency_profile_v1":
        raise GovernanceToolkitError("dependency profile schema is invalid")
    if profile["development_only"] is not True or profile["network_egress"] is not False:
        raise GovernanceToolkitError("dependency profile execution posture is invalid")
    default_tools = profile["required_default_tools"]
    trials = profile["optional_audit_trials"]
    if not isinstance(default_tools, list) or not default_tools:
        raise GovernanceToolkitError("dependency profile requires default tools")
    if not isinstance(trials, list):
        raise GovernanceToolkitError("dependency profile optional audit trials must be a list")
    names: set[str] = set()
    for label, records in (("required_default_tools", default_tools), ("optional_audit_trials", trials)):
        for index, record in enumerate(records):
            _validate_tool_record(record, f"{label}[{index}]")
            name = record["package"].lower()
            if name in names:
                raise GovernanceToolkitError("dependency profile package names must be unique")
            names.add(name)
    if PROHIBITED_DEFAULT_TOOLS & {record["package"].lower() for record in default_tools}:
        raise GovernanceToolkitError("dependency profile includes a prohibited default tool")
    return {
        "schema_version": "agent_governance_bundle_report_v1",
        "bundle": manifest["bundle"],
        "required_default_tool_count": len(default_tools),
        "optional_audit_trial_count": len(trials),
        "valid": True,
    }


def main(argv: list[str] | None = None) -> int:
    """Validate the toolkit bundle and print one deterministic JSON report."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args(argv)
    try:
        report = validate_bundle(args.root.resolve())
    except GovernanceToolkitError as exc:
        print(json.dumps({"valid": False, "errors": [str(exc)]}, sort_keys=True))
        return 1
    print(json.dumps(report, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
