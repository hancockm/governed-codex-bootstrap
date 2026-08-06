"""Repository architecture conformance checks."""

from __future__ import annotations

import json
from pathlib import Path


def check_repository(root: Path) -> list[str]:
    """Return deterministic violations of the bootstrap architecture."""
    config = json.loads((root / "configs/conformance_v1.json").read_text(encoding="utf-8"))
    failures: list[str] = []
    for plane, paths in config["required_planes"].items():
        for item in paths:
            if not (root / item).is_file():
                failures.append(f"{plane}: missing {item}")
    research = root / config["research_first"]["research_dir"]
    records = research / "records"
    if not research.is_dir() or not records.is_dir():
        failures.append("research-first: research records directory is missing")
    owners = json.loads((root / "configs/owners_v1.json").read_text(encoding="utf-8"))["owners"]
    active = sorted(name for name, value in owners.items() if value.get("active"))
    if active != config["research_first"]["initial_active_owners"]:
        failures.append("research-first: initial bootstrap may activate only Core")
    for marker in config["forbidden_project_markers"]:
        for path in root.rglob("*"):
            if path.is_file() and path.relative_to(root).as_posix() != "configs/conformance_v1.json" and ".git" not in path.parts and path.suffix in {".md", ".json", ".py", ".toml"}:
                if marker in path.read_text(encoding="utf-8", errors="ignore"):
                    failures.append(f"neutrality: forbidden marker {marker!r} in {path.relative_to(root)}")
    return failures
