from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from governance_bootstrap.packets import validate_packet, validate_receipt, validate_sol_finalization


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a work packet or lane receipt.")
    parser.add_argument("packet", type=Path)
    parser.add_argument("--receipt", type=Path)
    parser.add_argument("--finalization", type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    packet = json.loads(args.packet.read_text(encoding="utf-8"))
    owners = json.loads((root / "configs/owners_v1.json").read_text(encoding="utf-8"))["owners"]
    errors = validate_packet(packet, {name for name, item in owners.items() if item.get("active")})
    if args.receipt:
        receipt = json.loads(args.receipt.read_text(encoding="utf-8"))
        orchestration = json.loads((root / "configs/owner_scoped_orchestration_v1.json").read_text(encoding="utf-8"))
        errors.extend(validate_receipt(receipt, packet, orchestration["project_bound_luna_thread"], orchestration["saved_project_id"]))
        if args.finalization:
            errors.extend(validate_sol_finalization(json.loads(args.finalization.read_text(encoding="utf-8")), receipt, packet))
    elif args.finalization:
        parser.error("--finalization requires --receipt")
    print(json.dumps({"ok": not errors, "errors": errors}, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
