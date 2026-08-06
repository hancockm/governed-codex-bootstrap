from __future__ import annotations

from governance_bootstrap.packets import packet_hash, validate_packet, validate_receipt, validate_sol_finalization


def packet() -> dict[str, object]:
    return {"packet_id": "pkt-1", "implementation_cycle_id": "cycle-1", "owner": "core", "risk": "standard", "scope": ["tools"], "checks": ["focused"]}


def test_packet_and_project_bound_luna_receipt_validate() -> None:
    work = packet()
    receipt = {"packet_id": "pkt-1", "packet_sha256": packet_hash(work), "lane": "luna", "status": "accepted", "candidate_commit": "a" * 40, "project_bound_thread_id": "task-123", "saved_project_id": "project-abc", "implementation_cycle_id": "cycle-1"}
    assert validate_packet(work, {"core"}) == []
    assert validate_receipt(receipt, work, "task-123", "project-abc") == []


def test_luna_rejects_projectless_or_nonreused_receipt() -> None:
    work = packet()
    receipt = {"packet_id": "pkt-1", "packet_sha256": packet_hash(work), "lane": "luna", "status": "accepted", "candidate_commit": "sha", "project_bound_thread_id": "other", "saved_project_id": "", "implementation_cycle_id": "other"}
    errors = validate_receipt(receipt, work, "task-123", "project-abc")
    assert any("project-bound" in error for error in errors)
    assert any("saved project" in error for error in errors)
    assert any("implementation cycle" in error for error in errors)


def test_sol_finalization_is_separate_and_requires_terminal_delivery() -> None:
    work = packet()
    receipt = {"packet_id": "pkt-1", "packet_sha256": packet_hash(work), "lane": "luna", "status": "accepted", "candidate_commit": "sha", "project_bound_thread_id": "task-123", "saved_project_id": "project-abc", "implementation_cycle_id": "cycle-1"}
    finalization = {"owner": "sol", "acknowledgment": "subordinate_archive", "packet_id": "pkt-1", "candidate_commit": "sha", "status": "archived", "no_correction_pending": True, "delivery_complete": True, "primary_branch_synced": True, "terminal_reconciliation": True, "worktree_cleaned": True}
    assert validate_sol_finalization(finalization, receipt, work) == []
    finalization["status"] = "blocked"
    assert any("remain visible" in error for error in validate_sol_finalization(finalization, receipt, work))
