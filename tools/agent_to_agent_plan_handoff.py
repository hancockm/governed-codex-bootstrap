from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from governance_bootstrap.coordination import CRITIQUE_HEADINGS, CRITIQUE_PREAMBLE, content_id, update_index, write_immutable


def baseline(root: Path) -> str:
    """Return the current commit when available, otherwise a stable local marker."""
    result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, text=True, capture_output=True, check=False)
    return result.stdout.strip() if result.returncode == 0 else "uncommitted-bootstrap"


def main() -> int:
    """Create a dry-run or immutable advisory plan-handoff record without provider use."""
    parser = argparse.ArgumentParser(description="Create an advisory, content-addressed plan critique handoff.")
    parser.add_argument("--topic", required=True)
    parser.add_argument("--plan-file", type=Path, required=True)
    parser.add_argument("--owner", default="core")
    parser.add_argument("--critique-file", type=Path)
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    plan = args.plan_file.read_text(encoding="utf-8")
    critique = args.critique_file.read_text(encoding="utf-8") if args.critique_file else ""
    if critique and (CRITIQUE_PREAMBLE not in critique or any(f"# {heading}" not in critique for heading in CRITIQUE_HEADINGS)):
        parser.error("advisory critique must contain the required preamble and headings")
    metadata = {"kind": "plan_handoff", "topic": args.topic, "owner": args.owner, "baseline": baseline(root), "plan_sha256": hashlib.sha256(plan.encode("utf-8")).hexdigest(), "advisory_critique_sha256": hashlib.sha256(critique.encode("utf-8")).hexdigest() if critique else None, "status": "advisory_pending_owner_disposition"}
    identifier = content_id(metadata)[:16]
    relative = f"40_Coordination/Generated/Plan Handoffs/handoff-{identifier}.md"
    record = "\n\n".join([CRITIQUE_PREAMBLE, "# Plan Handoff", "```json\n" + json.dumps(metadata, indent=2, sort_keys=True) + "\n```", "## Required Critique\n" + "\n".join(f"# {heading}\nPending." for heading in CRITIQUE_HEADINGS), "## Plan\n" + plan, "## Advisory Critique\n" + (critique or "None supplied.")]) + "\n"
    index = root / "Project_Obsidian_Vault/40_Coordination/Generated/Active Records.md"
    target = root / "Project_Obsidian_Vault" / relative
    result = {"ok": True, "applied": args.apply, "record": relative, "status": metadata["status"], "canonical_promotion": "requires_owner_disposition"}
    if args.apply:
        write_immutable(target, record)
        update_index(index, relative, f"plan handoff {identifier}")
        monthly = root / "Project_Obsidian_Vault/40_Coordination/Generated/Monthly" / f"{datetime.now(timezone.utc):%Y-%m}.md"
        update_index(monthly, relative, f"plan handoff {identifier}")
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
