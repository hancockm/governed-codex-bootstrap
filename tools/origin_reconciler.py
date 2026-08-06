from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from governance_bootstrap.git_safety import git, inspect, sync_main_safe


def main() -> int:
    """Inspect reconciliation facts without inferring an integration decision."""
    parser = argparse.ArgumentParser(description="Bounded Git reconciliation: 0 clear, 2 routed inbox, 3 safety failure.")
    parser.add_argument("command", choices=("inspect", "closeout", "inbox", "sync-main"))
    parser.add_argument("--agent")
    parser.add_argument("--branch")
    parser.add_argument("--disposition", choices=("landed", "superseded", "awaiting_named_integrator"))
    parser.add_argument("--no-fetch", action="store_true")
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    if args.command == "inspect":
        result = inspect(root)
        print(json.dumps(result, indent=2, sort_keys=True))
        return 0 if not result["inspection_failed"] else 3
    if args.command == "sync-main":
        if not args.agent:
            parser.error("sync-main requires --agent core")
        errors = sync_main_safe(root, agent=args.agent, no_fetch=args.no_fetch)
        print(json.dumps({"ok": not errors, "errors": errors}, indent=2, sort_keys=True))
        return 0 if not errors else 3
    if args.command == "closeout":
        if not args.agent or not args.branch or not args.disposition:
            parser.error("closeout requires --agent, --branch, and --disposition")
        report = {"agent": args.agent, "branch": args.branch, "disposition": args.disposition, "inspection": inspect(root), "integration_decision": "not_inferred"}
        print(json.dumps(report, indent=2, sort_keys=True))
        return 2 if args.disposition == "awaiting_named_integrator" else (0 if not report["inspection"]["inspection_failed"] else 3)
    code, output = git(root, "for-each-ref", "--format=%(refname:short)", "refs/remotes/origin")
    if code:
        print(json.dumps({"ok": False, "errors": ["remote inspection failed"]}, indent=2))
        return 3
    branches = sorted(branch for branch in output.splitlines() if branch and not branch.endswith("/master") and not branch.endswith("/HEAD"))
    print(json.dumps({"ok": not branches, "items": [{"branch": branch, "disposition": "requires_owner_review"} for branch in branches]}, indent=2, sort_keys=True))
    return 2 if branches else 0


if __name__ == "__main__":
    raise SystemExit(main())
