from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from governance_bootstrap.common import canonical_json
from governance_bootstrap.packets import packet_hash, validate_packet, validate_receipt


def load(root: Path, path: str) -> dict:
    """Load one JSON configuration document."""
    return json.loads((root / path).read_text(encoding="utf-8"))


def main() -> int:
    """Inspect and bind owner-scoped work without invoking models or mutating Git."""
    parser = argparse.ArgumentParser(description="Owner-scoped packet utility; model invocation and Git mutation are intentionally absent.")
    parser.add_argument("command", choices=("check-owner", "classify", "prepare", "bind-runner", "validate", "record"))
    parser.add_argument("--owner")
    parser.add_argument("--packet", type=Path)
    parser.add_argument("--receipt", type=Path)
    parser.add_argument("--change-file", type=Path)
    parser.add_argument("--runner-id")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    owners = load(root, "configs/owners_v1.json")["owners"]
    orchestration = load(root, "configs/owner_scoped_orchestration_v1.json")
    if args.command == "check-owner":
        owner = owners.get(args.owner or "")
        ok = bool(owner and owner.get("active") and all((root / owner[key]).exists() for key in ("role", "bootstrap", "continuity")))
        print(json.dumps({"ok": ok, "owner": args.owner, "active": bool(owner and owner.get("active"))}, indent=2))
        return 0 if ok else 1
    if args.command == "classify":
        changes = json.loads(args.change_file.read_text(encoding="utf-8")) if args.change_file else {}
        triggers = set(changes.get("triggers", []))
        tiers = load(root, "configs/risk_classification_v1.json")["tiers"]
        risk = "high" if triggers & set(tiers["high"]) else "standard" if triggers & set(tiers["standard"]) else "low"
        print(json.dumps({"ok": True, "risk": risk, "triggers": sorted(triggers)}, indent=2))
        return 0
    if not args.packet:
        parser.error(f"{args.command} requires --packet")
    packet = json.loads(args.packet.read_text(encoding="utf-8"))
    errors = validate_packet(packet, {name for name, value in owners.items() if value.get("active")})
    if args.command == "validate" and args.receipt:
        receipt = json.loads(args.receipt.read_text(encoding="utf-8"))
        errors.extend(validate_receipt(receipt, packet, orchestration["project_bound_luna_thread"], orchestration["saved_project_id"]))
    bundle = {"packet_sha256": packet_hash(packet), "packet": packet, "runner_id": args.runner_id, "errors": errors}
    if args.command in {"prepare", "bind-runner", "record"} and args.apply and not errors:
        target = root / "tmp/orchestration_bundles" / f"{bundle['packet_sha256']}.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        text = canonical_json(bundle) + "\n"
        if target.exists() and target.read_text(encoding="utf-8") != text:
            print(json.dumps({"ok": False, "errors": ["immutable bundle collision"]}, indent=2))
            return 1
        if not target.exists():
            target.write_text(text, encoding="utf-8")
    print(json.dumps({"ok": not errors, "command": args.command, "packet_sha256": bundle["packet_sha256"], "applied": args.apply, "errors": errors}, indent=2))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
