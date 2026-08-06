from __future__ import annotations

import json
from pathlib import Path

from governance_bootstrap.conformance import check_repository


ROOT = Path(__file__).resolve().parents[1]


def test_complete_repository_conforms_to_six_plane_architecture() -> None:
    assert check_repository(ROOT) == []


def test_research_is_the_first_cold_start_evidence_lane() -> None:
    policy = json.loads((ROOT / "configs/conformance_v1.json").read_text(encoding="utf-8"))
    owners = json.loads((ROOT / "configs/owners_v1.json").read_text(encoding="utf-8"))["owners"]
    assert (ROOT / policy["research_first"]["research_dir"] / "records").is_dir()
    assert list((ROOT / "research/records").glob("*.md"))
    assert [name for name, item in owners.items() if item["active"]] == ["core"]


def test_no_project_specific_markers_or_absolute_paths() -> None:
    policy = json.loads((ROOT / "configs/conformance_v1.json").read_text(encoding="utf-8"))
    assert not [item for item in check_repository(ROOT) if item.startswith("neutrality:")]
    assert "C:" not in (ROOT / "README.md").read_text(encoding="utf-8")
    assert policy["forbidden_project_markers"]
