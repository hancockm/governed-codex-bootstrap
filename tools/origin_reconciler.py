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
    parser.add_argument("--integrator")
    parser.add_argument("--target")
    parser.add_argument("--commits")
    parser.add_argument("--remaining-action")
    parser.add_argument("--evidence", type=Path)
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
    if args.command in {"closeout", "inbox"} and not args.no_fetch:
        code, detail = git(root, "fetch", "--prune", "origin")
        if code:
            print(json.dumps({"ok": False, "errors": [f"fetch failed: {detail}"]}, indent=2))
            return 3
    if args.command == "closeout":
        if not args.agent or not args.branch or not args.disposition:
            parser.error("closeout requires --agent, --branch, and --disposition")
        report = {"agent": args.agent, "branch": args.branch, "disposition": args.disposition, "inspection": inspect(root), "integration_decision": "not_inferred", "evidence": []}
        if args.disposition == "landed":
            code, _ = git(root, "merge-base", "--is-ancestor", args.branch, "origin/master")
            if code:
                report["errors"] = ["landed requires exact reachability from origin/master; patch-equivalence is not implemented by this bounded reconciler"]
                print(json.dumps(report, indent=2, sort_keys=True))
                return 3
            report["evidence"].append("exact_reachability")
        if args.disposition == "superseded":
            if not args.evidence or not args.evidence.is_file():
                report["errors"] = ["superseded requires explicit replacement or abandonment evidence file"]
                print(json.dumps(report, indent=2, sort_keys=True))
                return 3
            report["evidence"].append(str(args.evidence))
        if args.disposition == "awaiting_named_integrator":
            if not all((args.integrator, args.target, args.commits, args.remaining_action, args.evidence and args.evidence.is_file())):
                report["errors"] = ["awaiting_named_integrator requires integrator, target, commits, remaining action, and evidence"]
                print(json.dumps(report, indent=2, sort_keys=True))
                return 3
            report.update({"integrator": args.integrator, "target": args.target, "commits": args.commits.split(","), "remaining_action": args.remaining_action, "evidence": [str(args.evidence)]})
        print(json.dumps(report, indent=2, sort_keys=True))
        return 2 if args.disposition == "awaiting_named_integrator" else (0 if not report["inspection"]["inspection_failed"] else 3)
    code, output = git(root, "for-each-ref", "--format=%(refname:short)", "refs/remotes/origin")
    if code:
        print(json.dumps({"ok": False, "errors": ["remote inspection failed"]}, indent=2))
        return 3
    owners = json.loads((root / "configs/owners_v1.json").read_text(encoding="utf-8"))["owners"]
    prefixes = {name: json.loads((root / value["profile"]).read_text(encoding="utf-8"))["branch_prefix"] for name, value in owners.items()}
    known, unknown = [], []
    for branch in sorted(branch for branch in output.splitlines() if branch and not branch.endswith("/master") and not branch.endswith("/HEAD")):
        code, commits = git(root, "rev-list", "origin/master.." + branch)
        if code:
            print(json.dumps({"ok": False, "errors": [f"cannot inspect {branch}"]}, indent=2))
            return 3
        if not commits:
            continue
        owner = next((name for name, prefix in prefixes.items() if branch.removeprefix("origin/").startswith(prefix)), None)
        entry = {"branch": branch, "branch_only_commits": commits.splitlines(), "disposition": "requires_owner_review"}
        (known if owner else unknown).append({**entry, **({"owner": owner} if owner else {})})
    result = {"ok": not known, "items": known, "unknown_owner_diagnostics": unknown, "markdown": "| Branch | Owner | State |\n|---|---|---|\n" + "\n".join(f"| {item['branch']} | {item.get('owner', 'unknown')} | review |" for item in [*known, *unknown])}
    print(json.dumps(result, indent=2, sort_keys=True))
    return 2 if known else 0


if __name__ == "__main__":
    raise SystemExit(main())
