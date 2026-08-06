from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from governance_bootstrap.git_safety import inspect, sync_main_safe


def main() -> int:
    parser = argparse.ArgumentParser(description="Inspect or safely verify primary Git synchronization.")
    parser.add_argument("command", choices=("inspect", "sync-main"))
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if args.command == "inspect":
        print(json.dumps(inspect(root), indent=2))
        return 0
    errors = sync_main_safe(root)
    print(json.dumps({"ok": not errors, "errors": errors}, indent=2))
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
