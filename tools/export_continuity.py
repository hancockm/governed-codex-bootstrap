from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from governance_bootstrap.continuity import export_bounded


def main() -> int:
    parser = argparse.ArgumentParser(description="Export a bounded user-visible response prefix.")
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--prefix", type=int, required=True)
    args = parser.parse_args()
    print(json.dumps(export_bounded(args.source, args.destination, args.prefix), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
