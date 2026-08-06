from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from governance_bootstrap.source_docs import audit_package


def main() -> int:
    """Audit public package source documentation and type annotations."""
    root = Path(__file__).resolve().parents[1]
    findings = audit_package(root / "governance_bootstrap")
    print(json.dumps({"ok": not findings, "findings": findings}, indent=2))
    return 0 if not findings else 1


if __name__ == "__main__":
    raise SystemExit(main())
