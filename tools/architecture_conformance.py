from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from governance_bootstrap.conformance import check_repository


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    failures = check_repository(root)
    print(json.dumps({"ok": not failures, "failures": failures}, indent=2))
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
