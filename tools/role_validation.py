"""Validate role-bound candidate evidence using public repository policy."""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from governance_bootstrap.common import canonical_json, sha256_canonical, validate_safe_diagnostic
from tools.owner_scoped_orchestration import OrchestrationError, validate_owner_path_authority


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_POLICY = Path("configs/role_validation_v1.json")
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
REQUEST_SCHEMA = "role_validation_request_v1"
RECEIPT_SCHEMA = "role_validation_receipt_v1"
REPORT_SCHEMA = "joined_candidate_validation_report_v1"


class RoleValidationError(RuntimeError):
    """Raised when role-bound candidate validation cannot prove consistency."""


@dataclass(frozen=True)
class RoleValidationRequestV1:
    """One role's declared checks for an exact candidate and path set."""

    role: str
    owner: str
    candidate_commit: str
    changed_paths: tuple[str, ...]
    checks: tuple[dict[str, str], ...]
    canonical_hash: str
    schema_version: str = REQUEST_SCHEMA

    def payload(self) -> dict[str, Any]:
        """Return the canonical JSON payload for this request."""

        return asdict(self)


@dataclass(frozen=True)
class RoleValidationReceiptV1:
    """One role's results for one validated candidate request."""

    role: str
    candidate_commit: str
    request_hash: str
    checks: tuple[dict[str, str], ...]
    residual_conditions: tuple[str, ...]
    outcome: str
    canonical_hash: str
    schema_version: str = RECEIPT_SCHEMA

    def payload(self) -> dict[str, Any]:
        """Return the canonical JSON payload for this receipt."""

        return asdict(self)


@dataclass(frozen=True)
class JoinedCandidateValidationReportV1:
    """Join exact role receipts for one candidate commit."""

    candidate_commit: str
    request_hashes: dict[str, str]
    receipt_hashes: dict[str, str]
    outcome: str
    canonical_hash: str
    schema_version: str = REPORT_SCHEMA

    def payload(self) -> dict[str, Any]:
        """Return the canonical JSON payload for this joined report."""

        return asdict(self)


def load_policy(root: Path = ROOT) -> dict[str, Any]:
    """Load the local role-validation policy without executing a command."""

    try:
        value = json.loads((root / DEFAULT_POLICY).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RoleValidationError("cannot load role-validation policy") from exc
    if set(value) != {"schema_version", "roles"} or value.get("schema_version") != "role_validation_policy_v1":
        raise RoleValidationError("role-validation policy has an invalid schema")
    roles = value["roles"]
    if not isinstance(roles, dict) or set(roles) != {"terra", "luna", "sol"}:
        raise RoleValidationError("role-validation policy roles are incomplete")
    for role, rule in roles.items():
        stages = rule.get("required_stages") if isinstance(rule, dict) and set(rule) == {"required_stages"} else None
        if not isinstance(stages, list) or not stages or any(not isinstance(item, str) or not item for item in stages):
            raise RoleValidationError(f"role-validation policy stages are invalid for {role}")
    return value


def _safe_paths(paths: Any) -> tuple[str, ...]:
    """Return conservative repository-relative changed paths."""

    if not isinstance(paths, list) or not paths:
        raise RoleValidationError("changed paths must be a non-empty list")
    normalized: list[str] = []
    for path in paths:
        if not isinstance(path, str) or not path or path.startswith(("/", "\\")) or ":" in path:
            raise RoleValidationError("changed paths must be repository-relative")
        value = path.replace("\\", "/")
        if value.startswith("../") or "/../" in value or value in normalized:
            raise RoleValidationError("changed paths must be unique normalized paths")
        normalized.append(value)
    return tuple(normalized)


def _checks(value: Any, expected_stages: Sequence[str], label: str) -> tuple[dict[str, str], ...]:
    """Validate ordered check descriptions against one role policy."""

    if not isinstance(value, list) or len(value) != len(expected_stages):
        raise RoleValidationError(f"{label} checks do not match the role policy")
    result: list[dict[str, str]] = []
    for item, stage in zip(value, expected_stages):
        if not isinstance(item, dict) or set(item) != {"stage", "command"}:
            raise RoleValidationError(f"{label} checks have an invalid shape")
        if item["stage"] != stage or not isinstance(item["command"], str) or not item["command"].strip():
            raise RoleValidationError(f"{label} checks do not match the role policy")
        validate_safe_diagnostic(f"{label} command", item["command"])
        result.append({"stage": stage, "command": item["command"]})
    return tuple(result)


def make_request(role: str, owner: str, candidate_commit: str, changed_paths: Sequence[str], checks: Sequence[Mapping[str, str]], *, root: Path = ROOT) -> RoleValidationRequestV1:
    """Build and validate one canonical role-validation request."""

    policy = load_policy(root)
    if role not in policy["roles"] or not isinstance(owner, str) or not owner:
        raise RoleValidationError("role and owner must be registered strings")
    if not HEX40.fullmatch(candidate_commit):
        raise RoleValidationError("candidate commit must be a 40-hex commit")
    paths = _safe_paths(list(changed_paths))
    try:
        validate_owner_path_authority(owner, paths, root)
    except OrchestrationError as exc:
        raise RoleValidationError("changed paths do not belong to the declared owner") from exc
    check_values = _checks(list(checks), policy["roles"][role]["required_stages"], "request")
    payload = {
        "schema_version": REQUEST_SCHEMA,
        "role": role,
        "owner": owner,
        "candidate_commit": candidate_commit,
        "changed_paths": list(paths),
        "checks": list(check_values),
    }
    return RoleValidationRequestV1(
        role=role,
        owner=owner,
        candidate_commit=candidate_commit,
        changed_paths=paths,
        checks=check_values,
        canonical_hash=sha256_canonical(payload),
    )


def request_from_payload(payload: Mapping[str, Any], *, root: Path = ROOT) -> RoleValidationRequestV1:
    """Load one exact, self-hashing role-validation request payload."""

    if set(payload) != {"schema_version", "role", "owner", "candidate_commit", "changed_paths", "checks", "canonical_hash"}:
        raise RoleValidationError("request has missing or forbidden fields")
    request = make_request(
        str(payload["role"]),
        str(payload["owner"]),
        str(payload["candidate_commit"]),
        payload["changed_paths"],
        payload["checks"],
        root=root,
    )
    if payload["schema_version"] != REQUEST_SCHEMA or payload["canonical_hash"] != request.canonical_hash:
        raise RoleValidationError("request canonical hash mismatch")
    return request


def make_receipt(request: RoleValidationRequestV1, checks: Sequence[Mapping[str, str]], residual_conditions: Sequence[str] = ()) -> RoleValidationReceiptV1:
    """Build a passed receipt for one request using explicit check results."""

    check_values: list[dict[str, str]] = []
    if len(checks) != len(request.checks):
        raise RoleValidationError("receipt checks do not match the request")
    for result, expected in zip(checks, request.checks):
        if not isinstance(result, Mapping) or set(result) != {"stage", "command", "outcome"}:
            raise RoleValidationError("receipt checks have an invalid shape")
        if result["stage"] != expected["stage"] or result["command"] != expected["command"] or result["outcome"] != "passed":
            raise RoleValidationError("receipt checks do not match the passed request")
        check_values.append({"stage": expected["stage"], "command": expected["command"], "outcome": "passed"})
    conditions = tuple(residual_conditions)
    if any(not isinstance(item, str) for item in conditions):
        raise RoleValidationError("residual conditions must be strings")
    for item in conditions:
        validate_safe_diagnostic("residual condition", item)
    payload = {
        "schema_version": RECEIPT_SCHEMA,
        "role": request.role,
        "candidate_commit": request.candidate_commit,
        "request_hash": request.canonical_hash,
        "checks": check_values,
        "residual_conditions": list(conditions),
        "outcome": "passed",
    }
    return RoleValidationReceiptV1(
        role=request.role,
        candidate_commit=request.candidate_commit,
        request_hash=request.canonical_hash,
        checks=tuple(check_values),
        residual_conditions=conditions,
        outcome="passed",
        canonical_hash=sha256_canonical(payload),
    )


def receipt_from_payload(payload: Mapping[str, Any], request: RoleValidationRequestV1) -> RoleValidationReceiptV1:
    """Load one exact, passed receipt bound to its request."""

    if set(payload) != {"schema_version", "role", "candidate_commit", "request_hash", "checks", "residual_conditions", "outcome", "canonical_hash"}:
        raise RoleValidationError("receipt has missing or forbidden fields")
    receipt = make_receipt(request, payload["checks"], payload["residual_conditions"])
    if (
        payload["schema_version"] != RECEIPT_SCHEMA
        or payload["role"] != request.role
        or payload["candidate_commit"] != request.candidate_commit
        or payload["request_hash"] != request.canonical_hash
        or payload["outcome"] != "passed"
        or payload["canonical_hash"] != receipt.canonical_hash
    ):
        raise RoleValidationError("receipt does not match its request")
    return receipt


def join_candidate_reports(requests: Sequence[RoleValidationRequestV1], receipts: Sequence[RoleValidationReceiptV1], *, root: Path = ROOT) -> JoinedCandidateValidationReportV1:
    """Join one passed receipt for every configured role on one candidate."""

    roles = set(load_policy(root)["roles"])
    request_by_role = {request.role: request for request in requests}
    receipt_by_role = {receipt.role: receipt for receipt in receipts}
    if set(request_by_role) != roles or set(receipt_by_role) != roles or len(request_by_role) != len(requests) or len(receipt_by_role) != len(receipts):
        raise RoleValidationError("joined report requires one request and receipt for every role")
    candidates = {request.candidate_commit for request in requests} | {receipt.candidate_commit for receipt in receipts}
    if len(candidates) != 1:
        raise RoleValidationError("joined report candidates do not match")
    if any(receipt.request_hash != request_by_role[role].canonical_hash for role, receipt in receipt_by_role.items()):
        raise RoleValidationError("joined report receipt bindings do not match")
    candidate = candidates.pop()
    request_hashes = {role: request_by_role[role].canonical_hash for role in sorted(roles)}
    receipt_hashes = {role: receipt_by_role[role].canonical_hash for role in sorted(roles)}
    payload = {"schema_version": REPORT_SCHEMA, "candidate_commit": candidate, "request_hashes": request_hashes, "receipt_hashes": receipt_hashes, "outcome": "passed"}
    return JoinedCandidateValidationReportV1(candidate, request_hashes, receipt_hashes, "passed", sha256_canonical(payload))


def validate_role_payloads(role: str, request_payload: Mapping[str, Any], receipt_payload: Mapping[str, Any], *, root: Path = ROOT) -> dict[str, Any]:
    """Validate one role's request and receipt and return a compact report."""

    request = request_from_payload(request_payload, root=root)
    if request.role != role:
        raise RoleValidationError("requested role does not match the request")
    receipt = receipt_from_payload(receipt_payload, request)
    return {"schema_version": "role_validation_result_v1", "role": role, "candidate_commit": request.candidate_commit, "request_hash": request.canonical_hash, "receipt_hash": receipt.canonical_hash, "outcome": "passed"}


def _load_payload(path: Path) -> dict[str, Any]:
    """Load one JSON object for the read-only command-line interface."""

    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RoleValidationError("cannot load validation payload") from exc
    if not isinstance(value, dict):
        raise RoleValidationError("validation payload must be an object")
    return value


def main(argv: list[str] | None = None) -> int:
    """Run the read-only role-validation command-line interface."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    commands = parser.add_subparsers(dest="command", required=True)
    validate = commands.add_parser("validate")
    validate.add_argument("--role", choices=("terra", "luna", "sol"), required=True)
    validate.add_argument("--request", type=Path, required=True)
    validate.add_argument("--receipt", type=Path, required=True)
    join = commands.add_parser("join")
    join.add_argument("--request", type=Path, action="append", required=True)
    join.add_argument("--receipt", type=Path, action="append", required=True)
    args = parser.parse_args(argv)
    try:
        root = args.root.resolve()
        if args.command == "validate":
            result = validate_role_payloads(args.role, _load_payload(args.request), _load_payload(args.receipt), root=root)
        else:
            if len(args.request) != len(args.receipt):
                raise RoleValidationError("joined report requires equal request and receipt counts")
            requests = [request_from_payload(_load_payload(path), root=root) for path in args.request]
            receipts = [receipt_from_payload(_load_payload(path), request) for path, request in zip(args.receipt, requests)]
            result = join_candidate_reports(requests, receipts, root=root).payload()
    except RoleValidationError as exc:
        print(str(exc))
        return 1
    print(canonical_json(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
