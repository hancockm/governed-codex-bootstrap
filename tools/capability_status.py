from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def main() -> int:
    """Check or report machine capability maturity, evidence, and verification links."""
    parser = argparse.ArgumentParser(description="Inspect capability registry consistency.")
    parser.add_argument("command", choices=("check", "report"))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    registry = json.loads((root / "configs/capability_registry_v1.json").read_text(encoding="utf-8"))
    allowed = {"proposed", "active", "verified", "deferred", "superseded", "retired"}
    errors = []
    for item in registry.get("capabilities", []):
        if item.get("state") not in allowed:
            errors.append(f"invalid state: {item.get('id')}")
        if not item.get("owner") or not item.get("evidence") or not item.get("verification"):
            errors.append(f"incomplete maturity evidence: {item.get('id')}")
    result = {"ok": not errors, "capabilities": registry.get("capabilities", []), "errors": errors}
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
