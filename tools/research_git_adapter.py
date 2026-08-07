"""Capture an exact bounded public Git repository as immutable research."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from governance_bootstrap.git_research import (
    DEFAULT_MAX_FILE_BYTES,
    DEFAULT_MAX_FILES,
    DEFAULT_MAX_TOTAL_BYTES,
    GitCliRepositoryAdapter,
    GitResearchError,
    capture_git_repository,
)


def main(argv: list[str] | None = None) -> int:
    """Capture one authorized public HTTPS Git ref at an expected commit."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--url", required=True)
    parser.add_argument("--ref", required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--title", required=True)
    parser.add_argument("--include-prefix", action="append", default=[])
    parser.add_argument("--max-files", type=int, default=DEFAULT_MAX_FILES)
    parser.add_argument("--max-file-bytes", type=int, default=DEFAULT_MAX_FILE_BYTES)
    parser.add_argument("--max-total-bytes", type=int, default=DEFAULT_MAX_TOTAL_BYTES)
    parser.add_argument(
        "--authorize-network",
        action="store_true",
        help="Acknowledge the approved public HTTPS network acquisition.",
    )
    args = parser.parse_args(argv)
    root = Path(__file__).resolve().parents[1]
    try:
        result = capture_git_repository(
            root,
            GitCliRepositoryAdapter(root / "tmp"),
            repository_url=args.url,
            requested_ref=args.ref,
            expected_commit=args.commit,
            title=args.title,
            include_prefixes=tuple(args.include_prefix),
            network_authorized=args.authorize_network,
            max_files=args.max_files,
            max_file_bytes=args.max_file_bytes,
            max_total_bytes=args.max_total_bytes,
        )
    except GitResearchError as error:
        print(
            json.dumps(
                {"status": "unavailable", "reason": str(error)},
                indent=2,
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
