"""Lifecycle-aware pytest runner; keep mode-specific options out of global addopts."""

from __future__ import annotations

import argparse
import fnmatch
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def pytest_command(arguments: list[str]) -> list[str]:
    """Build a pytest command using the current interpreter."""
    return [sys.executable, "-m", "pytest", *arguments]


def changed_paths(base: str) -> list[str]:
    """Return changed tracked paths for a Git comparison, including deletions."""
    result = subprocess.run(["git", "diff", "--name-only", f"{base}...HEAD"], cwd=ROOT, text=True, capture_output=True, check=False)
    if result.returncode:
        raise RuntimeError(result.stderr.strip() or f"cannot compare against {base}")
    return [line for line in result.stdout.splitlines() if line]


def affected_targets(paths: list[str]) -> list[str]:
    """Map changes to focused tests and fail closed to the broad boundary."""
    config = json.loads((ROOT / "configs/testing/test_impact_v1.json").read_text(encoding="utf-8"))
    selected: set[str] = set()
    unknown = False
    for path in paths:
        matched = False
        for mapping in config["mappings"]:
            if any(fnmatch.fnmatch(path, pattern) for pattern in mapping["source_globs"]):
                selected.update(mapping["focused"])
                matched = True
        if not matched and (path.endswith(".py") or path.startswith("configs/") or path.startswith("canonical/")):
            unknown = True
    if unknown:
        return config["unknown_runtime_boundary"]
    return sorted(selected) or config["unknown_runtime_boundary"]


def run(arguments: list[str]) -> int:
    """Run pytest in the project root."""
    return subprocess.run(pytest_command(arguments), cwd=ROOT, check=False).returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="Run governed test profiles.")
    parser.add_argument("profile", choices=("focused", "failed", "affected", "broad", "full"))
    parser.add_argument("targets", nargs="*")
    parser.add_argument("--base")
    args = parser.parse_args()
    if args.profile == "focused":
        if not args.targets:
            parser.error("focused requires one or more test targets")
        return run([*args.targets, "-x", "--tb=short"])
    if args.profile == "failed":
        return run(["--lf", "--lfnf=none", "-x"])
    if args.profile == "affected":
        if not args.base:
            parser.error("affected requires --base")
        return run([*affected_targets(changed_paths(args.base)), "-x", "--tb=short"])
    policy = json.loads((ROOT / "configs/testing/execution_v1.json").read_text(encoding="utf-8"))
    if args.profile == "broad":
        return run([*policy["broad"], "--maxfail=3"])
    full = policy["full"]
    parallel = run([*policy["parallel_safe"], "-n", "auto", "--maxprocesses", str(full["workers"]), "--dist", full["distribution"], "--max-worker-restart", str(full["max_worker_restart"])])
    if parallel:
        return parallel
    return run([*policy["serial"], "-n", "0"])


if __name__ == "__main__":
    raise SystemExit(main())
