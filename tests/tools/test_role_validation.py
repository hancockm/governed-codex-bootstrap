from __future__ import annotations

import json
from pathlib import Path

import pytest

from tools import role_validation, test_runner


ROOT = Path(__file__).resolve().parents[2]
CANDIDATE = "a" * 40
PATHS = ["tools/test_runner.py"]


def _request(role: str) -> role_validation.RoleValidationRequestV1:
    stages = role_validation.load_policy(ROOT)["roles"][role]["required_stages"]
    return role_validation.make_request(
        role,
        "core",
        CANDIDATE,
        PATHS,
        [{"stage": stage, "command": f"python -m pytest {stage}"} for stage in stages],
        root=ROOT,
    )


def _receipt(request: role_validation.RoleValidationRequestV1) -> role_validation.RoleValidationReceiptV1:
    return role_validation.make_receipt(
        request,
        [{"stage": item["stage"], "command": item["command"], "outcome": "passed"} for item in request.checks],
    )


def test_role_request_receipt_and_join_are_self_hashing() -> None:
    requests = [_request(role) for role in ("terra", "luna", "sol")]
    receipts = [_receipt(request) for request in requests]
    report = role_validation.join_candidate_reports(requests, receipts, root=ROOT)

    assert report.candidate_commit == CANDIDATE
    assert set(report.request_hashes) == {"terra", "luna", "sol"}
    assert set(report.receipt_hashes) == {"terra", "luna", "sol"}
    assert report.outcome == "passed"


def test_request_requires_authoritative_path_ownership() -> None:
    with pytest.raises(role_validation.RoleValidationError, match="declared owner"):
        role_validation.make_request(
            "terra",
            "core",
            CANDIDATE,
            ["unowned/example.py"],
            [
                {"stage": "focused", "command": "python -m pytest focused"},
                {"stage": "affected", "command": "python -m pytest affected"},
            ],
            root=ROOT,
        )


def test_test_runner_validate_uses_role_specific_request_and_receipt(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    request = _request("terra")
    receipt = _receipt(request)
    request_path = tmp_path / "request.json"
    receipt_path = tmp_path / "receipt.json"
    request_path.write_text(json.dumps(request.payload()), encoding="utf-8")
    receipt_path.write_text(json.dumps(receipt.payload()), encoding="utf-8")

    assert test_runner.main([
        "validate", "--role", "terra", "--request", str(request_path), "--receipt", str(receipt_path),
    ]) == 0
    result = json.loads(capsys.readouterr().out)
    assert result["outcome"] == "passed"
    assert result["role"] == "terra"
