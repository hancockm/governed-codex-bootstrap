from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from governance_bootstrap.vault import check, report, sync_navigation


def main() -> int:
    """Run conservative vault reporting, checks, or breadcrumb synchronization."""
    parser = argparse.ArgumentParser(description="Maintain generated vault navigation conservatively.")
    parser.add_argument("command", choices=("report", "check", "sync-navigation"))
    parser.add_argument("--apply", action="store_true", help="Apply only generated breadcrumb updates.")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if args.command == "report":
        result = report(root)
    elif args.command == "check":
        errors = check(root)
        result = {"ok": not errors, "diagnostics": errors}
    else:
        result = sync_navigation(root, apply=args.apply)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
