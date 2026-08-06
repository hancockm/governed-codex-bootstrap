"""Create content-addressed immutable records from supplied research files."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from governance_bootstrap.research import intake


def main() -> int:
    """Parse one research source and print its immutable intake record."""

    parser = argparse.ArgumentParser(description="Create an immutable research record.")
    parser.add_argument("source", type=Path)
    parser.add_argument("--title", required=True)
    parser.add_argument("--origin", required=True)
    args = parser.parse_args()
    print(json.dumps(intake(Path(__file__).resolve().parents[1], args.source, args.title, args.origin), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
