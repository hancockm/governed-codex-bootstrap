"""Deterministic work-packet and receipt validation."""

from __future__ import annotations

import hashlib
from typing import Any

from .common import canonical_json


PACKET_REQUIRED = {"packet_id", "implementation_cycle_id", "owner", "risk", "scope", "checks"}
RECEIPT_REQUIRED = {"packet_id", "packet_sha256", "lane", "status"}


def packet_hash(packet: dict[str, Any]) -> str:
    """Return a stable identity hash for a work packet."""
    return hashlib.sha256(canonical_json(packet).encode("utf-8")).hexdigest()


def validate_packet(packet: dict[str, Any], active_owners: set[str]) -> list[str]:
    """Return packet schema and authority violations."""
    errors = [f"missing {key}" for key in sorted(PACKET_REQUIRED - packet.keys())]
    if packet.get("owner") not in active_owners:
        errors.append("packet owner is not active")
    if packet.get("risk") not in {"low", "standard", "high"}:
        errors.append("risk must be low, standard, or high")
    if not isinstance(packet.get("scope"), list) or not packet.get("scope"):
        errors.append("scope must be a nonempty list")
    if not isinstance(packet.get("checks"), list) or not packet.get("checks"):
        errors.append("checks must be a nonempty list")
    return errors


def validate_receipt(receipt: dict[str, Any], packet: dict[str, Any], luna_thread: str, saved_project: str) -> list[str]:
    """Return receipt binding and lane-boundary violations."""
    errors = [f"missing {key}" for key in sorted(RECEIPT_REQUIRED - receipt.keys())]
    if receipt.get("packet_id") != packet.get("packet_id"):
        errors.append("receipt packet_id does not bind packet")
    if receipt.get("packet_sha256") != packet_hash(packet):
        errors.append("receipt packet_sha256 does not bind exact packet")
    lane = receipt.get("lane")
    if lane not in {"terra", "luna"}:
        errors.append("receipt lane must be terra or luna")
    if lane == "luna":
        if not receipt.get("candidate_commit"):
            errors.append("Luna receipt requires candidate_commit")
        if receipt.get("project_bound_thread_id") != luna_thread:
            errors.append("Luna receipt must reuse project-bound thread")
        if not saved_project or saved_project.startswith("replace-") or receipt.get("saved_project_id") != saved_project:
            errors.append("Luna receipt must be created inside the saved project")
        if receipt.get("implementation_cycle_id") != packet.get("implementation_cycle_id"):
            errors.append("Luna receipt must bind the implementation cycle")
        if receipt.get("archival_acknowledged") is not True:
            errors.append("Luna receipt requires archival acknowledgment")
    return errors
