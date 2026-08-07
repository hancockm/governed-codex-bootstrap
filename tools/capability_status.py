"""Validate and render the project's owner-maintained capability-status registry.

Examples:
    python tools/capability_status.py check
    python tools/capability_status.py render --check
    python tools/capability_status.py render --apply
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY = ROOT / "configs" / "capability_registry_v1.json"
DEFAULT_OUTPUT = ROOT / "Project_Obsidian_Vault" / "00_Canonical" / "Current State.md"

STATUSES = {
    "implemented",
    "partially_implemented",
    "specified_future",
    "proposed",
    "deferred",
    "superseded",
}
DELIVERY_SCOPES = {
    "runtime",
    "integration",
    "passive_contract",
    "fixture",
    "documentation",
    "tooling",
}
PUBLICATION_STATUSES = {"pending_owner_disposition", "definitive"}
ENTRY_KEYS = {
    "id",
    "name",
    "owner",
    "delivery_scope",
    "status",
    "summary",
    "dependencies",
    "canonical_evidence",
    "source_evidence",
    "test_evidence",
    "owner_disposition_ref",
    "superseded_by",
}


class CapabilityStatusError(ValueError):
    """Raised when registry structure, evidence, or publication state is invalid."""


def load_registry(path: Path) -> dict[str, Any]:
    """Load one JSON registry without searching for fallback locations.

    Args:
        path: Exact registry path.

    Returns:
        Parsed registry mapping.

    Raises:
        CapabilityStatusError: If the file is unreadable or not a JSON object.
    """

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CapabilityStatusError(f"registry could not be loaded: {path}") from exc
    if not isinstance(payload, dict):
        raise CapabilityStatusError("registry root must be a JSON object")
    return payload


def validate_registry(registry: dict[str, Any], *, root: Path = ROOT) -> None:
    """Validate registry structure, evidence, dependencies, and owner signoff.

    Args:
        registry: Parsed capability registry.
        root: Repository root used to resolve evidence paths.

    Raises:
        CapabilityStatusError: If any invariant is violated.
    """

    errors: list[str] = []
    expected_root_keys = {
        "schema_version",
        "publication_status",
        "owner_review_ref",
        "active_gate_id",
        "entries",
    }
    if set(registry) != expected_root_keys:
        errors.append("registry root keys do not match capability_status_v1")
    if registry.get("schema_version") != "capability_status_v1":
        errors.append("schema_version must be capability_status_v1")
    publication_status = registry.get("publication_status")
    if publication_status not in PUBLICATION_STATUSES:
        errors.append("publication_status is invalid")
    owner_review_ref = registry.get("owner_review_ref")
    if not isinstance(owner_review_ref, str) or not owner_review_ref:
        errors.append("owner_review_ref must be a non-empty repository path")
    else:
        _validate_path(owner_review_ref, "owner_review_ref", root, errors)
    entries = registry.get("entries")
    if not isinstance(entries, list) or not entries:
        errors.append("entries must be a non-empty list")
        entries = []

    entries_by_id: dict[str, dict[str, Any]] = {}
    for index, raw_entry in enumerate(entries):
        label = f"entries[{index}]"
        if not isinstance(raw_entry, dict):
            errors.append(f"{label} must be an object")
            continue
        if set(raw_entry) != ENTRY_KEYS:
            errors.append(f"{label} keys do not match the v1 entry schema")
            continue
        capability_id = raw_entry["id"]
        if not isinstance(capability_id, str) or not capability_id:
            errors.append(f"{label}.id must be non-empty")
            continue
        if capability_id in entries_by_id:
            errors.append(f"duplicate capability id: {capability_id}")
        entries_by_id[capability_id] = raw_entry
        _validate_entry(raw_entry, label, publication_status, root, errors)

    for capability_id, entry in entries_by_id.items():
        for dependency in entry["dependencies"]:
            if dependency not in entries_by_id:
                errors.append(f"{capability_id} has unknown dependency: {dependency}")
        replacement = entry["superseded_by"]
        if replacement and replacement not in entries_by_id:
            errors.append(f"{capability_id} has unknown replacement: {replacement}")
    _validate_acyclic(entries_by_id, errors)

    active_gate_id = registry.get("active_gate_id")
    active_gate = entries_by_id.get(active_gate_id)
    if active_gate is None:
        errors.append("active_gate_id must identify an existing entry")
    else:
        if active_gate["status"] not in {"partially_implemented", "specified_future"}:
            errors.append("active gate must be accepted and incomplete")
        for dependency in active_gate["dependencies"]:
            dependency_entry = entries_by_id.get(dependency)
            if dependency_entry is not None and dependency_entry["status"] != "implemented":
                errors.append(f"active gate dependency is not implemented: {dependency}")
    if errors:
        raise CapabilityStatusError("\n".join(errors))


def render_registry(registry: dict[str, Any], *, root: Path = ROOT) -> str:
    """Render a definitive registry as the canonical current-state projection.

    Args:
        registry: Validated definitive registry.
        root: Repository root used during validation.

    Returns:
        Complete generated Markdown document.

    Raises:
        CapabilityStatusError: If validation fails or owner disposition is pending.
    """

    validate_registry(registry, root=root)
    if registry["publication_status"] != "definitive":
        raise CapabilityStatusError(
            "registry publication is pending owner disposition; Current State.md cannot be generated"
        )
    entries_by_id = {entry["id"]: entry for entry in registry["entries"]}
    active_gate = entries_by_id[registry["active_gate_id"]]
    lines = [
        "# Current State",
        "",
        "<!-- generated:breadcrumbs:start -->",
        "<< Previous: [[00_Canonical/Capability Registry]] | Up: [[00_Canonical/Canonical MOC]] | Next: none >>",
        "<!-- generated:breadcrumbs:end -->",
        "",
        "<!-- Generated by tools/capability_status.py from configs/capability_registry_v1.json. -->",
        "",
        f"Active gate: `{active_gate['id']}` — {active_gate['name']}.",
        "",
        "| Capability | Owner | Delivery scope | Status | Evidence-backed reading |",
        "| --- | --- | --- | --- | --- |",
    ]
    for entry in registry["entries"]:
        summary = entry["summary"].replace("|", "\\|").replace("\n", " ")
        lines.append(
            f"| `{entry['id']}` — {entry['name']} | {entry['owner']} | "
            f"`{entry['delivery_scope']}` | `{entry['status']}` | {summary} |"
        )
    lines.extend(("", f"Owner disposition record: `{registry['owner_review_ref']}`", ""))
    return "\n".join(lines)


def _validate_entry(
    entry: dict[str, Any],
    label: str,
    publication_status: object,
    root: Path,
    errors: list[str],
) -> None:
    for field_name in ("name", "owner", "summary"):
        if not isinstance(entry[field_name], str) or not entry[field_name].strip():
            errors.append(f"{label}.{field_name} must be non-empty")
    if entry["delivery_scope"] not in DELIVERY_SCOPES:
        errors.append(f"{label}.delivery_scope is invalid")
    if entry["status"] not in STATUSES:
        errors.append(f"{label}.status is invalid")
    for field_name in (
        "dependencies",
        "canonical_evidence",
        "source_evidence",
        "test_evidence",
    ):
        values = entry[field_name]
        if not isinstance(values, list) or not all(isinstance(value, str) and value for value in values):
            errors.append(f"{label}.{field_name} must be a list of non-empty strings")
            continue
        if len(values) != len(set(values)):
            errors.append(f"{label}.{field_name} contains duplicates")
        if field_name.endswith("_evidence"):
            for value in values:
                _validate_path(value, f"{label}.{field_name}", root, errors)
    status = entry["status"]
    if status in {"specified_future", "proposed", "deferred"} and not entry["canonical_evidence"]:
        errors.append(f"{label} future/proposed/deferred status requires canonical evidence")
    if status in {"implemented", "partially_implemented"} and entry["delivery_scope"] in {
        "runtime",
        "integration",
    }:
        if not entry["source_evidence"] or not entry["test_evidence"]:
            errors.append(f"{label} runtime/integration maturity requires source and test evidence")
    replacement = entry["superseded_by"]
    if not isinstance(replacement, str):
        errors.append(f"{label}.superseded_by must be a string")
    elif (status == "superseded") != bool(replacement):
        errors.append(f"{label} superseded status and replacement must be paired")
    disposition_ref = entry["owner_disposition_ref"]
    if not isinstance(disposition_ref, str):
        errors.append(f"{label}.owner_disposition_ref must be a string")
    elif disposition_ref:
        _validate_path(disposition_ref, f"{label}.owner_disposition_ref", root, errors)
    elif publication_status == "definitive" and entry["owner"] != "Core":
        errors.append(f"{label} requires non-Core owner disposition before definitive publication")


def _validate_path(value: str, label: str, root: Path, errors: list[str]) -> None:
    relative = Path(value)
    if relative.is_absolute() or ".." in relative.parts:
        errors.append(f"{label} must stay inside the repository: {value}")
        return
    root_resolved = root.resolve()
    candidate = (root_resolved / relative).resolve()
    try:
        candidate.relative_to(root_resolved)
    except ValueError:
        errors.append(f"{label} escapes the repository: {value}")
        return
    if not candidate.exists():
        errors.append(f"{label} does not exist: {value}")


def _validate_acyclic(entries: dict[str, dict[str, Any]], errors: list[str]) -> None:
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(capability_id: str) -> None:
        if capability_id in visiting:
            errors.append(f"capability dependency cycle includes: {capability_id}")
            return
        if capability_id in visited:
            return
        visiting.add(capability_id)
        for dependency in entries[capability_id]["dependencies"]:
            if dependency in entries:
                visit(dependency)
        visiting.remove(capability_id)
        visited.add(capability_id)

    for capability_id in entries:
        visit(capability_id)


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("check", help="validate registry structure and evidence")
    render = subparsers.add_parser("render", help="render the definitive Current State projection")
    render.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    action = render.add_mutually_exclusive_group(required=True)
    action.add_argument("--check", action="store_true")
    action.add_argument("--apply", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run registry validation or definitive projection rendering."""

    args = _build_parser().parse_args(argv)
    try:
        registry = load_registry(args.registry)
        validate_registry(registry)
        if args.command == "check":
            print(f"Capability registry valid ({registry['publication_status']}).")
            return 0
        rendered = render_registry(registry)
        if args.check:
            try:
                current = args.output.read_text(encoding="utf-8")
            except OSError as exc:
                raise CapabilityStatusError(f"generated output could not be read: {args.output}") from exc
            if current != rendered:
                raise CapabilityStatusError("generated Current State projection is stale")
            print("Capability Current State projection is current.")
            return 0
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
        print(f"Wrote {args.output}")
        return 0
    except CapabilityStatusError as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
