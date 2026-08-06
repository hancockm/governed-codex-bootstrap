"""Validate source-only agent work-selection audit records.

Examples:
    python tools/agent_work_selection_audit.py section-hash --path note.md \
        --heading-line "## Current State" --commit HEAD
    python tools/agent_work_selection_audit.py check --audit path/to/audit.md
    python tools/agent_work_selection_audit.py pilot-check \
        --manifest configs/work_selection_audit_v1.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Any


ROOT = Path(__file__).resolve().parents[1]

PREAMBLE = (
    "Be critical of this input. You need to be analytical in your response.  "
    "Do not take this as the answer. Look at the weak points in the argument. "
    "Let's begin to list areas of common agreement. List areas of disagreement. "
    "The goal for each iteration is to reduce one disagreement. If each round, "
    "you eliminate one disagreement but add 2 disagreements you are going in the wrong direction.  "
    "We need to converge on a plan. List ALL remaining disagreements. "
    "Don't keep adding them after each round."
)
REQUIRED_HEADINGS = (
    "## Common Agreement",
    "## All Remaining Disagreements",
    "## Critical Weak Points",
    "## Convergence Move",
    "## Decision Status",
)
AUDIT_START = "<!-- PROJECT_AGENT_WORK_SELECTION_AUDIT_V1:START -->"
AUDIT_END = "<!-- PROJECT_AGENT_WORK_SELECTION_AUDIT_V1:END -->"
AUDIT_SCHEMA_VERSION = "agent_work_selection_audit_v1"
PILOT_SCHEMA_VERSION = "agent_work_selection_pilot_v1"
VALIDATION_SCHEMA_VERSION = "agent_work_selection_audit_validation_v1"
PILOT_VALIDATION_SCHEMA_VERSION = "agent_work_selection_pilot_validation_v1"

ROOT_KEYS = {
    "schema_version",
    "authority",
    "audit_kind",
    "agent_role",
    "thread_id",
    "created_utc",
    "repository_commit",
    "candidate",
    "sources",
    "findings",
    "prerequisites",
    "selection",
    "supersedes_payload_sha256",
}
CANDIDATE_KEYS = {"candidate_id", "owner", "summary"}
SOURCE_KEYS = {
    "source_id",
    "path",
    "heading_line",
    "section_sha256",
    "atoms",
}
ATOM_KEYS = {"atom_id", "excerpt"}
FINDING_KEYS = {
    "atom_id",
    "relation",
    "resolution",
    "authority",
    "owner",
    "candidate_effect",
    "disposition_ref",
}
PREREQUISITE_KEYS = {
    "prerequisite_id",
    "owner",
    "required",
    "status",
    "evidence_atom_ids",
    "disposition_ref",
}
SELECTION_KEYS = {
    "status",
    "blocking_atom_ids",
    "blocking_prerequisite_ids",
    "rationale",
}
PILOT_KEYS = {
    "schema_version",
    "authority",
    "audit_directory",
    "required_roles",
    "bootstrap_fixtures",
}
FIXTURE_KEYS = {
    "fixture_id",
    "audit_path",
    "counts_toward_role_coverage",
    "expected_atom_ids",
    "evidence_commits",
}

AUDIT_KINDS = {"live", "retrospective_fixture"}
RELATIONS = {"supports", "contradicts", "silent", "irrelevant"}
RESOLUTIONS = {
    "verified",
    "invalidated",
    "unverified",
    "owner_disposition_required",
    "user_approval_required",
    "not_applicable",
}
AUTHORITIES = {
    "user_instruction",
    "canonical",
    "runtime",
    "test",
    "configuration",
    "accepted_a2a",
    "continuity",
    "historical",
}
CANDIDATE_EFFECTS = {"supports", "non_blocking", "blocks"}
PREREQUISITE_STATUSES = {
    "satisfied",
    "unsatisfied",
    "owner_disposition_required",
    "user_approval_required",
    "not_required",
}
SELECTION_STATUSES = {
    "selectable",
    "not_selectable",
    "owner_disposition_required",
    "user_approval_required",
}
HEX_40 = re.compile(r"^[0-9a-f]{40}$")
HEX_64 = re.compile(r"^[0-9a-f]{64}$")
ATX_HEADING = re.compile(r"^(?: {0,3})(#{1,6})(?:[ \t]+|$).*$")
FENCE_OPEN = re.compile(r"^(?: {0,3})(`{3,}|~{3,})(.*)$")


class AuditValidationError(ValueError):
    """Raised when an audit source cannot be parsed or normalized."""


@dataclass(frozen=True)
class AuditValidationResult:
    """Complete structural validation result for one audit record."""

    audit_path: str
    payload: dict[str, Any] | None
    payload_sha256: str
    valid: bool
    candidate_status: str
    blocking_atom_ids: tuple[str, ...]
    blocking_prerequisite_ids: tuple[str, ...]
    errors: tuple[str, ...]

    def as_dict(self) -> dict[str, Any]:
        """Return the deterministic public validation report."""

        return {
            "schema_version": VALIDATION_SCHEMA_VERSION,
            "audit_path": self.audit_path,
            "payload_sha256": self.payload_sha256,
            "valid": self.valid,
            "candidate_status": self.candidate_status,
            "blocking_atom_ids": list(self.blocking_atom_ids),
            "blocking_prerequisite_ids": list(self.blocking_prerequisite_ids),
            "errors": list(self.errors),
        }


def _windows_long_path(path: Path) -> Path:
    """Return a Windows long-path capable absolute path when needed."""

    if os.name != "nt":
        return path
    if not path.is_absolute():
        return path
    value = str(path)
    if value.startswith("\\\\?\\"):
        return path
    if value.startswith("\\\\"):
        return Path("\\\\?\\UNC\\" + value.lstrip("\\"))
    return Path("\\\\?\\" + value)


def _path_exists(path: Path) -> bool:
    """Return whether path exists without failing on deep Windows worktrees."""

    return _windows_long_path(path).exists()


def _is_dir(path: Path) -> bool:
    """Return whether path is a directory in deep Windows worktrees."""

    return _windows_long_path(path).is_dir()


def _read_text(path: Path) -> str:
    """Read UTF-8 text from a path that may exceed Windows MAX_PATH."""

    return _windows_long_path(path).read_text(encoding="utf-8")


def normalize_text_bytes(raw: bytes) -> str:
    """Decode repository text and apply the pilot's newline normalization."""

    if raw.startswith(b"\xef\xbb\xbf"):
        raw = raw[3:]
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise AuditValidationError("source is not valid UTF-8") from exc
    return text.replace("\r\n", "\n").replace("\r", "\n")


def extract_atx_section(text: str, heading_line: str) -> str:
    """Extract one exact ATX section outside fenced Markdown blocks."""

    if "\n" in heading_line or "\r" in heading_line:
        raise AuditValidationError("heading_line must be one exact line")
    lines = text.splitlines(keepends=True)
    headings: list[tuple[int, int, str]] = []
    fence_character = ""
    fence_length = 0

    for index, line in enumerate(lines):
        content = line[:-1] if line.endswith("\n") else line
        fence_match = FENCE_OPEN.match(content)
        if fence_character:
            stripped = content.lstrip(" ")
            if (
                len(content) - len(stripped) <= 3
                and re.fullmatch(
                    rf"{re.escape(fence_character)}{{{fence_length},}}[ \t]*",
                    stripped,
                )
            ):
                fence_character = ""
                fence_length = 0
            continue
        if fence_match:
            marker = fence_match.group(1)
            fence_character = marker[0]
            fence_length = len(marker)
            continue
        heading_match = ATX_HEADING.match(content)
        if heading_match:
            headings.append((index, len(heading_match.group(1)), content))

    matches = [heading for heading in headings if heading[2] == heading_line]
    if not matches:
        raise AuditValidationError(f"heading not found: {heading_line}")
    if len(matches) != 1:
        raise AuditValidationError(f"heading is not unique: {heading_line}")

    selected_index, selected_level, _ = matches[0]
    end_index = len(lines)
    for index, level, _ in headings:
        if index > selected_index and level <= selected_level:
            end_index = index
            break
    return "".join(lines[selected_index + 1 : end_index])


def canonical_payload(payload: dict[str, Any]) -> tuple[bytes, dict[str, Any]]:
    """Return canonical bytes and normalized payload without mutating input."""

    normalized = _normalize_json_value(payload)
    encoded = json.dumps(
        normalized,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return encoded, normalized


def validate_audit(path: Path, *, root: Path = ROOT) -> AuditValidationResult:
    """Validate one content-addressed A2A audit record."""

    display_path = _display_path(path, root)
    try:
        payload = load_audit_payload(path)
    except AuditValidationError as exc:
        return AuditValidationResult(
            audit_path=display_path,
            payload=None,
            payload_sha256="",
            valid=False,
            candidate_status="invalid",
            blocking_atom_ids=(),
            blocking_prerequisite_ids=(),
            errors=(str(exc),),
        )

    encoded, normalized_payload = canonical_payload(payload)
    digest = hashlib.sha256(encoded).hexdigest()
    errors: list[str] = []
    blocking_atoms: tuple[str, ...] = ()
    blocking_prerequisites: tuple[str, ...] = ()
    candidate_status = "invalid"

    _validate_payload_shape(normalized_payload, root=root, errors=errors)
    if not path.stem.endswith(f"-{digest[:12]}"):
        errors.append(f"audit filename must end with payload hash: {digest[:12]}")

    if not errors:
        candidate_status, blocking_atoms, blocking_prerequisites = _derive_selection(
            normalized_payload
        )
        selection = normalized_payload["selection"]
        if selection["status"] != candidate_status:
            errors.append(
                "selection.status does not match derived candidate status: "
                f"{candidate_status}"
            )
        if tuple(selection["blocking_atom_ids"]) != blocking_atoms:
            errors.append("selection.blocking_atom_ids do not match derived blockers")
        if tuple(selection["blocking_prerequisite_ids"]) != blocking_prerequisites:
            errors.append(
                "selection.blocking_prerequisite_ids do not match derived blockers"
            )

    return AuditValidationResult(
        audit_path=display_path,
        payload=normalized_payload,
        payload_sha256=digest,
        valid=not errors,
        candidate_status=candidate_status if not errors else "invalid",
        blocking_atom_ids=blocking_atoms,
        blocking_prerequisite_ids=blocking_prerequisites,
        errors=tuple(errors),
    )


def load_audit_payload(path: Path) -> dict[str, Any]:
    """Load the sole marked JSON payload from one A2A Markdown record."""

    try:
        text = _read_text(path)
    except OSError as exc:
        raise AuditValidationError(f"audit could not be read: {path}") from exc
    if not text.startswith(PREAMBLE):
        raise AuditValidationError("audit record is missing the required A2A preamble")
    heading_cursor = 0
    for heading in REQUIRED_HEADINGS:
        found = text.find(heading, heading_cursor)
        if found < 0:
            raise AuditValidationError(f"audit record is missing required heading: {heading}")
        heading_cursor = found + len(heading)
    if text.count(AUDIT_START) != 1 or text.count(AUDIT_END) != 1:
        raise AuditValidationError("audit record must contain exactly one marked payload")
    start = text.index(AUDIT_START) + len(AUDIT_START)
    end = text.index(AUDIT_END, start)
    block = text[start:end].strip()
    if not block.startswith("```json\n") or not block.endswith("\n```"):
        raise AuditValidationError("audit payload must be one fenced JSON block")
    raw_json = block[len("```json\n") : -len("\n```")]
    try:
        payload = json.loads(raw_json)
    except json.JSONDecodeError as exc:
        raise AuditValidationError(f"audit payload is invalid JSON: {exc.msg}") from exc
    if not isinstance(payload, dict):
        raise AuditValidationError("audit payload root must be an object")
    return payload


def validate_pilot(
    manifest_path: Path,
    *,
    root: Path = ROOT,
    require_complete: bool = False,
) -> tuple[dict[str, Any], int]:
    """Validate the pilot manifest, bootstrap fixtures, corpus, and role coverage."""

    errors: list[str] = []
    try:
        manifest = json.loads(_read_text(manifest_path))
    except (OSError, json.JSONDecodeError) as exc:
        report = _pilot_report(errors=[f"pilot manifest could not be loaded: {exc}"])
        return report, 1
    if not isinstance(manifest, dict):
        report = _pilot_report(errors=["pilot manifest root must be an object"])
        return report, 1
    if set(manifest) != PILOT_KEYS:
        errors.append("pilot manifest keys do not match agent_work_selection_pilot_v1")
    if manifest.get("schema_version") != PILOT_SCHEMA_VERSION:
        errors.append(f"schema_version must be {PILOT_SCHEMA_VERSION}")
    if manifest.get("authority") != "source_only":
        errors.append("pilot manifest authority must be source_only")

    roles = manifest.get("required_roles")
    if not _is_unique_nonempty_strings(roles):
        errors.append("required_roles must be a unique non-empty string list")
        roles = []
    audit_directory = manifest.get("audit_directory")
    audit_root: Path | None = None
    if not isinstance(audit_directory, str):
        errors.append("audit_directory must be a repository-relative path")
    else:
        try:
            audit_root = _working_tree_path(root, audit_directory)
        except AuditValidationError as exc:
            errors.append(f"audit_directory: {exc}")
        else:
            if not _is_dir(audit_root):
                errors.append("audit_directory does not exist")

    results: list[AuditValidationResult] = []
    if audit_root is not None and _is_dir(audit_root):
        for path in sorted(audit_root.rglob("*.md")):
            try:
                text = _read_text(path)
            except OSError as exc:
                errors.append(f"audit corpus file could not be read: {path}: {exc}")
                continue
            if AUDIT_START in text or AUDIT_END in text:
                result = validate_audit(path, root=root)
                results.append(result)
                if not result.valid:
                    errors.extend(f"{result.audit_path}: {item}" for item in result.errors)

    hashes: dict[str, AuditValidationResult] = {}
    for result in results:
        if not result.valid:
            continue
        if result.payload_sha256 in hashes:
            errors.append(
                "duplicate canonical audit payload: "
                f"{hashes[result.payload_sha256].audit_path} and {result.audit_path}"
            )
        hashes[result.payload_sha256] = result

    superseded_hashes: set[str] = set()
    successor_by_prior: dict[str, str] = {}
    prior_by_successor: dict[str, str] = {}
    for result in results:
        if not result.valid or result.payload is None:
            continue
        prior = result.payload["supersedes_payload_sha256"]
        if prior:
            if prior == result.payload_sha256:
                errors.append(f"{result.audit_path}: audit cannot supersede itself")
            elif prior not in hashes:
                errors.append(f"{result.audit_path}: superseded audit hash is not in corpus")
            else:
                superseded_hashes.add(prior)
                if prior in successor_by_prior:
                    errors.append(
                        "multiple audits supersede the same payload: "
                        f"{prior}"
                    )
                successor_by_prior[prior] = result.payload_sha256
                prior_by_successor[result.payload_sha256] = prior

    for digest in prior_by_successor:
        seen: set[str] = set()
        cursor = digest
        while cursor in prior_by_successor:
            if cursor in seen:
                errors.append(f"audit supersession cycle includes payload: {cursor}")
                break
            seen.add(cursor)
            cursor = prior_by_successor[cursor]

    fixtures = manifest.get("bootstrap_fixtures")
    if not isinstance(fixtures, list) or not fixtures:
        errors.append("bootstrap_fixtures must be a non-empty list")
        fixtures = []
    fixture_ids: set[str] = set()
    fixture_paths: set[str] = set()
    for index, fixture in enumerate(fixtures):
        label = f"bootstrap_fixtures[{index}]"
        if not isinstance(fixture, dict) or set(fixture) != FIXTURE_KEYS:
            errors.append(f"{label} keys do not match the fixture schema")
            continue
        fixture_id = fixture["fixture_id"]
        if not _is_nonempty_string(fixture_id):
            errors.append(f"{label}.fixture_id must be non-empty")
        elif fixture_id in fixture_ids:
            errors.append(f"duplicate fixture_id: {fixture_id}")
        else:
            fixture_ids.add(fixture_id)
        if fixture["counts_toward_role_coverage"] is not False:
            errors.append(f"{label} must not count toward live role coverage")
        expected_atoms = fixture["expected_atom_ids"]
        if not _is_unique_nonempty_strings(expected_atoms):
            errors.append(f"{label}.expected_atom_ids must be unique and non-empty")
        evidence_commits = fixture["evidence_commits"]
        if not _is_unique_nonempty_strings(evidence_commits):
            errors.append(f"{label}.evidence_commits must be unique and non-empty")
        else:
            for commit in evidence_commits:
                if not _commit_exists(root, commit):
                    errors.append(f"{label}.evidence_commits has unknown commit: {commit}")
        audit_path = fixture["audit_path"]
        if not isinstance(audit_path, str):
            errors.append(f"{label}.audit_path must be a repository-relative path")
            continue
        try:
            resolved = _working_tree_path(root, audit_path)
        except AuditValidationError as exc:
            errors.append(f"{label}.audit_path: {exc}")
            continue
        normalized_audit_path = normalize_repo_path(audit_path)
        if normalized_audit_path in fixture_paths:
            errors.append(f"duplicate fixture audit_path: {normalized_audit_path}")
        fixture_paths.add(normalized_audit_path)
        matched = next((result for result in results if Path(result.audit_path) == Path(audit_path)), None)
        if matched is None:
            errors.append(f"{label}.audit_path is not in the audit corpus")
        elif matched.valid and matched.payload is not None:
            atom_ids = _declared_atom_ids(matched.payload)
            if atom_ids != tuple(expected_atoms):
                errors.append(f"{label} declared atom IDs do not match the pinned fixture")
            if matched.payload["audit_kind"] != "retrospective_fixture":
                errors.append(f"{label} must reference a retrospective_fixture audit")
        if not _path_exists(resolved):
            errors.append(f"{label}.audit_path does not exist")

    active_results = [
        result
        for result in results
        if result.valid
        and result.payload is not None
        and result.payload_sha256 not in superseded_hashes
    ]
    covered_roles = sorted(
        {
            result.payload["agent_role"]
            for result in active_results
            if result.payload["audit_kind"] == "live"
            and result.payload["agent_role"] in roles
        }
    )
    unknown_roles = sorted(
        {
            result.payload["agent_role"]
            for result in active_results
            if result.payload["audit_kind"] == "live"
            and result.payload["agent_role"] not in roles
        }
    )
    if unknown_roles:
        errors.append("live audits use roles outside the pilot manifest: " + ", ".join(unknown_roles))
    missing_roles = [role for role in roles if role not in covered_roles]
    complete = not missing_roles
    status = "eligible_for_disposition" if complete else "collecting"
    if require_complete and missing_roles:
        errors.append("pilot role coverage is incomplete")

    report = {
        "schema_version": PILOT_VALIDATION_SCHEMA_VERSION,
        "valid": not errors,
        "pilot_status": status,
        "required_role_count": len(roles),
        "covered_role_count": len(covered_roles),
        "covered_roles": covered_roles,
        "missing_roles": missing_roles,
        "audit_count": len(results),
        "active_audit_count": len(active_results),
        "errors": errors,
    }
    return report, 0 if not errors else 1


def _validate_payload_shape(
    payload: dict[str, Any],
    *,
    root: Path,
    errors: list[str],
) -> None:
    if set(payload) != ROOT_KEYS:
        errors.append("audit root keys do not match agent_work_selection_audit_v1")
        return
    if payload["schema_version"] != AUDIT_SCHEMA_VERSION:
        errors.append(f"schema_version must be {AUDIT_SCHEMA_VERSION}")
    if payload["authority"] != "source_only":
        errors.append("authority must be source_only")
    if payload["audit_kind"] not in AUDIT_KINDS:
        errors.append("audit_kind is invalid")
    for field in ("agent_role", "thread_id"):
        if not _is_single_line_string(payload[field]):
            errors.append(f"{field} must be a non-empty single-line string")
    if not _is_utc_timestamp(payload["created_utc"]):
        errors.append("created_utc must be a timezone-aware UTC timestamp")
    commit = payload["repository_commit"]
    if not isinstance(commit, str) or not HEX_40.fullmatch(commit):
        errors.append("repository_commit must be a full lowercase SHA-1")
    elif not _commit_exists(root, commit):
        errors.append(f"repository_commit does not exist: {commit}")
    supersedes = payload["supersedes_payload_sha256"]
    if not isinstance(supersedes, str) or (supersedes and not HEX_64.fullmatch(supersedes)):
        errors.append("supersedes_payload_sha256 must be empty or lowercase SHA-256")

    candidate = payload["candidate"]
    if not _has_exact_keys(candidate, CANDIDATE_KEYS):
        errors.append("candidate keys do not match the v1 schema")
    else:
        for field in CANDIDATE_KEYS:
            if not _is_single_line_string(candidate[field]):
                errors.append(f"candidate.{field} must be a non-empty single-line string")
    candidate_owner = candidate.get("owner", "") if isinstance(candidate, dict) else ""

    atom_ids: list[str] = []
    source_ids: list[str] = []
    sources = payload["sources"]
    if not isinstance(sources, list) or not sources:
        errors.append("sources must be a non-empty list")
        sources = []
    for index, source in enumerate(sources):
        label = f"sources[{index}]"
        if not _has_exact_keys(source, SOURCE_KEYS):
            errors.append(f"{label} keys do not match the v1 schema")
            continue
        source_id = source["source_id"]
        if not _is_single_line_string(source_id):
            errors.append(f"{label}.source_id must be non-empty")
        else:
            source_ids.append(source_id)
        path = source["path"]
        heading_line = source["heading_line"]
        section_hash = source["section_sha256"]
        if not _is_single_line_string(path):
            errors.append(f"{label}.path must be non-empty")
        if not _is_single_line_string(heading_line):
            errors.append(f"{label}.heading_line must be one non-empty line")
        if not isinstance(section_hash, str) or not HEX_64.fullmatch(section_hash):
            errors.append(f"{label}.section_sha256 must be lowercase SHA-256")
        atoms = source["atoms"]
        if not isinstance(atoms, list) or not atoms:
            errors.append(f"{label}.atoms must be a non-empty list")
            atoms = []
        for atom_index, atom in enumerate(atoms):
            atom_label = f"{label}.atoms[{atom_index}]"
            if not _has_exact_keys(atom, ATOM_KEYS):
                errors.append(f"{atom_label} keys do not match the v1 schema")
                continue
            if not _is_single_line_string(atom["atom_id"]):
                errors.append(f"{atom_label}.atom_id must be non-empty")
            else:
                atom_ids.append(atom["atom_id"])
            if not _is_nonempty_string(atom["excerpt"]):
                errors.append(f"{atom_label}.excerpt must be non-empty")

        if (
            isinstance(commit, str)
            and HEX_40.fullmatch(commit)
            and _is_single_line_string(path)
            and _is_single_line_string(heading_line)
        ):
            try:
                normalized_path = normalize_repo_path(path)
                raw = _git_blob(root, commit, normalized_path)
                section = extract_atx_section(normalize_text_bytes(raw), heading_line)
            except AuditValidationError as exc:
                errors.append(f"{label}: {exc}")
            else:
                actual_hash = hashlib.sha256(section.encode("utf-8")).hexdigest()
                if section_hash != actual_hash:
                    errors.append(f"{label}.section_sha256 does not match repository evidence")
                for atom_index, atom in enumerate(atoms):
                    if not _has_exact_keys(atom, ATOM_KEYS):
                        continue
                    excerpt = atom["excerpt"]
                    if isinstance(excerpt, str) and section.count(excerpt) != 1:
                        errors.append(
                            f"{label}.atoms[{atom_index}].excerpt must occur exactly once"
                        )

    if len(source_ids) != len(set(source_ids)):
        errors.append("source_id values must be unique")
    if len(atom_ids) != len(set(atom_ids)):
        errors.append("atom_id values must be globally unique")

    finding_ids: list[str] = []
    findings = payload["findings"]
    if not isinstance(findings, list):
        errors.append("findings must be a list")
        findings = []
    for index, finding in enumerate(findings):
        label = f"findings[{index}]"
        if not _has_exact_keys(finding, FINDING_KEYS):
            errors.append(f"{label} keys do not match the v1 schema")
            continue
        atom_id = finding["atom_id"]
        if not _is_single_line_string(atom_id):
            errors.append(f"{label}.atom_id must be non-empty")
        else:
            finding_ids.append(atom_id)
        if finding["relation"] not in RELATIONS:
            errors.append(f"{label}.relation is invalid")
        if finding["resolution"] not in RESOLUTIONS:
            errors.append(f"{label}.resolution is invalid")
        if finding["authority"] not in AUTHORITIES:
            errors.append(f"{label}.authority is invalid")
        if not _is_single_line_string(finding["owner"]):
            errors.append(f"{label}.owner must be non-empty")
        if finding["candidate_effect"] not in CANDIDATE_EFFECTS:
            errors.append(f"{label}.candidate_effect is invalid")
        if finding["relation"] in {"silent", "irrelevant"} and finding[
            "candidate_effect"
        ] != "non_blocking":
            errors.append(f"{label} silent or irrelevant evidence must be non_blocking")
        _validate_optional_repo_ref(
            finding["disposition_ref"],
            label=f"{label}.disposition_ref",
            root=root,
            errors=errors,
        )
        if finding["resolution"] == "owner_disposition_required" and not finding[
            "disposition_ref"
        ]:
            errors.append(f"{label}.disposition_ref is required for owner routing")
        if (
            candidate_owner
            and finding["owner"] != candidate_owner
            and finding["candidate_effect"] == "blocks"
            and finding["resolution"] != "owner_disposition_required"
        ):
            errors.append(
                f"{label} other-owner blocker must require owner disposition"
            )

    if len(finding_ids) != len(set(finding_ids)):
        errors.append("finding atom IDs must be unique")
    if tuple(finding_ids) != tuple(atom_ids):
        errors.append("findings must cover the declared atom IDs exactly and in order")

    prerequisite_ids: list[str] = []
    prerequisites = payload["prerequisites"]
    if not isinstance(prerequisites, list):
        errors.append("prerequisites must be a list")
        prerequisites = []
    for index, prerequisite in enumerate(prerequisites):
        label = f"prerequisites[{index}]"
        if not _has_exact_keys(prerequisite, PREREQUISITE_KEYS):
            errors.append(f"{label} keys do not match the v1 schema")
            continue
        prerequisite_id = prerequisite["prerequisite_id"]
        if not _is_single_line_string(prerequisite_id):
            errors.append(f"{label}.prerequisite_id must be non-empty")
        else:
            prerequisite_ids.append(prerequisite_id)
        if not _is_single_line_string(prerequisite["owner"]):
            errors.append(f"{label}.owner must be non-empty")
        if not isinstance(prerequisite["required"], bool):
            errors.append(f"{label}.required must be boolean")
        if prerequisite["status"] not in PREREQUISITE_STATUSES:
            errors.append(f"{label}.status is invalid")
        evidence_ids = prerequisite["evidence_atom_ids"]
        if not _is_unique_nonempty_strings(evidence_ids):
            errors.append(f"{label}.evidence_atom_ids must be unique and non-empty")
        elif any(atom_id not in atom_ids for atom_id in evidence_ids):
            errors.append(f"{label}.evidence_atom_ids contain unknown atoms")
        _validate_optional_repo_ref(
            prerequisite["disposition_ref"],
            label=f"{label}.disposition_ref",
            root=root,
            errors=errors,
        )
        if prerequisite["status"] == "owner_disposition_required" and not prerequisite[
            "disposition_ref"
        ]:
            errors.append(f"{label}.disposition_ref is required for owner routing")
        if (
            candidate_owner
            and prerequisite["owner"] != candidate_owner
            and prerequisite["required"]
            and prerequisite["status"] not in {
                "satisfied",
                "not_required",
                "owner_disposition_required",
                "user_approval_required",
            }
        ):
            errors.append(
                f"{label} other-owner prerequisite must require owner disposition"
            )
    if len(prerequisite_ids) != len(set(prerequisite_ids)):
        errors.append("prerequisite_id values must be unique")

    selection = payload["selection"]
    if not _has_exact_keys(selection, SELECTION_KEYS):
        errors.append("selection keys do not match the v1 schema")
    else:
        if selection["status"] not in SELECTION_STATUSES:
            errors.append("selection.status is invalid")
        if not _is_unique_nonempty_strings(selection["blocking_atom_ids"], allow_empty=True):
            errors.append("selection.blocking_atom_ids must be a unique string list")
        if not _is_unique_nonempty_strings(
            selection["blocking_prerequisite_ids"], allow_empty=True
        ):
            errors.append(
                "selection.blocking_prerequisite_ids must be a unique string list"
            )
        if not _is_nonempty_string(selection["rationale"]):
            errors.append("selection.rationale must be non-empty")


def _derive_selection(
    payload: dict[str, Any],
) -> tuple[str, tuple[str, ...], tuple[str, ...]]:
    blocking_findings = [
        finding
        for finding in payload["findings"]
        if finding["candidate_effect"] == "blocks"
        and finding["resolution"] not in {"invalidated", "not_applicable"}
    ]
    blocking_prerequisites = [
        prerequisite
        for prerequisite in payload["prerequisites"]
        if prerequisite["required"]
        and prerequisite["status"] not in {"satisfied", "not_required"}
    ]
    blocking_atom_ids = tuple(finding["atom_id"] for finding in blocking_findings)
    blocking_prerequisite_ids = tuple(
        prerequisite["prerequisite_id"] for prerequisite in blocking_prerequisites
    )
    resolutions = {finding["resolution"] for finding in blocking_findings}
    prerequisite_statuses = {
        prerequisite["status"] for prerequisite in blocking_prerequisites
    }
    if "user_approval_required" in resolutions | prerequisite_statuses:
        status = "user_approval_required"
    elif "owner_disposition_required" in resolutions | prerequisite_statuses:
        status = "owner_disposition_required"
    elif blocking_findings or blocking_prerequisites:
        status = "not_selectable"
    else:
        status = "selectable"
    return status, blocking_atom_ids, blocking_prerequisite_ids


def normalize_repo_path(value: str) -> str:
    """Normalize one schema-declared repository path to POSIX form."""

    if not isinstance(value, str) or not value:
        raise AuditValidationError("repository path must be non-empty")
    windows_path = PureWindowsPath(value)
    if windows_path.drive or windows_path.is_absolute() or value.startswith(("/", "\\")):
        raise AuditValidationError(f"repository path must be relative: {value}")
    normalized = value.replace("\\", "/")
    path = PurePosixPath(normalized)
    if any(part in {"", ".", ".."} for part in path.parts):
        raise AuditValidationError(f"repository path is unsafe: {value}")
    return path.as_posix()


def _normalize_json_value(value: Any, *, key: str = "") -> Any:
    if isinstance(value, dict):
        return {
            item_key: _normalize_json_value(item_value, key=item_key)
            for item_key, item_value in value.items()
        }
    if isinstance(value, list):
        return [_normalize_json_value(item, key=key) for item in value]
    if isinstance(value, str):
        normalized = value.replace("\r\n", "\n").replace("\r", "\n")
        if key == "path" or (key == "disposition_ref" and normalized):
            return normalize_repo_path(normalized)
        return normalized
    return value


def _git_blob(root: Path, commit: str, path: str) -> bytes:
    normalized_path = normalize_repo_path(path)
    result = subprocess.run(
        ["git", "show", f"{commit}:{normalized_path}"],
        cwd=root,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise AuditValidationError(
            f"repository source is unavailable at {commit}:{normalized_path}"
        )
    return result.stdout


def _commit_exists(root: Path, commit: str) -> bool:
    if not isinstance(commit, str) or not HEX_40.fullmatch(commit):
        return False
    result = subprocess.run(
        ["git", "cat-file", "-e", f"{commit}^{{commit}}"],
        cwd=root,
        capture_output=True,
        check=False,
    )
    return result.returncode == 0


def _working_tree_path(root: Path, value: str) -> Path:
    normalized = normalize_repo_path(value)
    root_resolved = root.resolve()
    candidate = (root_resolved / Path(*PurePosixPath(normalized).parts)).resolve()
    try:
        candidate.relative_to(root_resolved)
    except ValueError as exc:
        raise AuditValidationError(f"repository path escapes the root: {value}") from exc
    return candidate


def _validate_optional_repo_ref(
    value: Any,
    *,
    label: str,
    root: Path,
    errors: list[str],
) -> None:
    if not isinstance(value, str):
        errors.append(f"{label} must be a string")
        return
    if not value:
        return
    try:
        path = _working_tree_path(root, value)
    except AuditValidationError as exc:
        errors.append(f"{label}: {exc}")
        return
    if not _path_exists(path):
        errors.append(f"{label} does not exist: {value}")


def _declared_atom_ids(payload: dict[str, Any]) -> tuple[str, ...]:
    return tuple(
        atom["atom_id"]
        for source in payload["sources"]
        for atom in source["atoms"]
    )


def _has_exact_keys(value: Any, keys: set[str]) -> bool:
    return isinstance(value, dict) and set(value) == keys


def _is_nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_single_line_string(value: Any) -> bool:
    return _is_nonempty_string(value) and "\n" not in value and "\r" not in value


def _is_unique_nonempty_strings(value: Any, *, allow_empty: bool = False) -> bool:
    if not isinstance(value, list):
        return False
    if not value and not allow_empty:
        return False
    return all(_is_single_line_string(item) for item in value) and len(value) == len(
        set(value)
    )


def _is_utc_timestamp(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return False
    return parsed.tzinfo is not None and parsed.utcoffset() == timezone.utc.utcoffset(parsed)


def _display_path(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root.resolve()).as_posix()
    except ValueError:
        return str(path)


def _pilot_report(*, errors: list[str]) -> dict[str, Any]:
    return {
        "schema_version": PILOT_VALIDATION_SCHEMA_VERSION,
        "valid": False,
        "pilot_status": "invalid",
        "required_role_count": 0,
        "covered_role_count": 0,
        "covered_roles": [],
        "missing_roles": [],
        "audit_count": 0,
        "active_audit_count": 0,
        "errors": errors,
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    section_hash = subparsers.add_parser(
        "section-hash", help="hash one exact Markdown ATX section at a Git commit"
    )
    section_hash.add_argument("--path", required=True)
    section_hash.add_argument("--heading-line", required=True)
    section_hash.add_argument("--commit", required=True)

    check = subparsers.add_parser("check", help="validate one A2A audit record")
    check.add_argument("--audit", type=Path, required=True)

    pilot_check = subparsers.add_parser(
        "pilot-check", help="validate pilot fixtures, corpus, and role coverage"
    )
    pilot_check.add_argument("--manifest", type=Path, required=True)
    pilot_check.add_argument("--require-complete", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run one read-only work-selection audit command."""

    args = _build_parser().parse_args(argv)
    if args.command == "section-hash":
        try:
            path = normalize_repo_path(args.path)
            commit = _resolve_commit(ROOT, args.commit)
            section = extract_atx_section(
                normalize_text_bytes(_git_blob(ROOT, commit, path)),
                args.heading_line,
            )
        except AuditValidationError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        report = {
            "commit": commit,
            "path": path,
            "heading_line": args.heading_line,
            "section_bytes": len(section.encode("utf-8")),
            "section_sha256": hashlib.sha256(section.encode("utf-8")).hexdigest(),
        }
        print(json.dumps(report, ensure_ascii=True, sort_keys=True, indent=2))
        return 0
    if args.command == "check":
        result = validate_audit(args.audit, root=ROOT)
        print(json.dumps(result.as_dict(), ensure_ascii=True, sort_keys=True, indent=2))
        return 0 if result.valid else 1
    report, exit_code = validate_pilot(
        args.manifest,
        root=ROOT,
        require_complete=args.require_complete,
    )
    print(json.dumps(report, ensure_ascii=True, sort_keys=True, indent=2))
    return exit_code


def _resolve_commit(root: Path, value: str) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "--verify", f"{value}^{{commit}}"],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )
    commit = result.stdout.strip()
    if result.returncode != 0 or not HEX_40.fullmatch(commit):
        raise AuditValidationError(f"unknown Git commit: {value}")
    return commit


if __name__ == "__main__":
    raise SystemExit(main())
