"""Organize immutable research through the generic source-preserving adapter."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from governance_bootstrap import research_organizer as organizer


def scan(root: Path) -> dict:
    """Report supported and unsupported immutable research records."""

    return organizer.scan(root)


def build(root: Path) -> dict:
    """Build deterministic source-preserving research candidates."""

    return organizer.build(root)


def review(root: Path, candidate_id: str, status: str, reason: str) -> dict:
    """Record one separate human review decision for a candidate."""

    return organizer.review(root, candidate_id, status, reason)


def may_enter_canonical(root: Path, candidate_id: str) -> bool:
    """Return whether a candidate has a separate current review decision."""

    return organizer.may_enter_canonical(root, candidate_id)


def main() -> int:
    """Run scan, deterministic build, or separate human review commands."""

    parser = argparse.ArgumentParser(description="Organize immutable research without promoting it.")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("scan")
    commands.add_parser("build")
    review_parser = commands.add_parser("review")
    review_parser.add_argument("candidate_id")
    review_parser.add_argument("--status", required=True)
    review_parser.add_argument("--reason", required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    result = scan(root) if args.command == "scan" else build(root) if args.command == "build" else review(root, args.candidate_id, args.status, args.reason)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
