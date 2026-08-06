from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from governance_bootstrap.coordination import content_id, update_index, write_immutable


def main() -> int:
    """Create an advisory, source-only frozen-baseline work-selection audit."""
    parser = argparse.ArgumentParser(description="Record non-gating work-selection evidence.")
    parser.add_argument("--input", type=Path, required=True, help="JSON with candidates, prerequisites, owner_dispositions, and assumptions.")
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    source = json.loads(args.input.read_text(encoding="utf-8"))
    required = {"candidates", "prerequisites", "owner_dispositions", "assumptions"}
    if required - source.keys():
        parser.error("input lacks required source-only evidence fields")
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, text=True, capture_output=True, check=False).stdout.strip() or "uncommitted-bootstrap"
    record = {"kind": "work_selection_audit", "baseline": commit, "status": "advisory_non_gating", "authority": "none", **source}
    identifier = content_id(record)[:16]
    relative = f"40_Coordination/Generated/Work Selection Audits/audit-{identifier}.json"
    target = root / "Project_Obsidian_Vault" / relative
    if args.apply:
        write_immutable(target, json.dumps(record, indent=2, sort_keys=True) + "\n")
        update_index(root / "Project_Obsidian_Vault/40_Coordination/Generated/Active Records.md", relative, f"selection audit {identifier}")
        update_index(root / "Project_Obsidian_Vault/40_Coordination/Generated/Monthly" / f"{datetime.now(timezone.utc):%Y-%m}.md", relative, f"selection audit {identifier}")
    print(json.dumps({"ok": True, "applied": args.apply, "record": relative, "status": record["status"]}, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
