from __future__ import annotations

from pathlib import Path

from governance_bootstrap.source_docs import audit_package
from governance_bootstrap.vault import check, report, sync_navigation


ROOT = Path(__file__).resolve().parents[1]


def test_vault_is_maintained_single_source_and_navigation_is_idempotent() -> None:
    assert check(ROOT) == []
    result = sync_navigation(ROOT)
    assert result == {"ok": True, "applied": False, "changes": [], "diagnostics": []}
    assert report(ROOT)["oversized"] == []
    assert not (ROOT / "canonical").exists()
    assert "Owner-authored description pending." not in "\n".join(path.read_text(encoding="utf-8") for path in (ROOT / "Project_Obsidian_Vault").rglob("*.md"))


def test_source_documentation_audit_covers_public_package_source() -> None:
    assert audit_package(ROOT / "governance_bootstrap") == []


def test_dynamic_generated_index_rejects_missing_targets(tmp_path: Path) -> None:
    import shutil
    sample = tmp_path / "sample"
    shutil.copytree(ROOT, sample, ignore=shutil.ignore_patterns(".git", "tmp", "__pycache__"))
    index = sample / "Project_Obsidian_Vault/40_Coordination/Generated/Active Records.md"
    index.write_text(index.read_text(encoding="utf-8") + "\n- [[40_Coordination/Generated/missing.md|bad]]\n", encoding="utf-8")
    assert any("link target is missing" in error for error in check(sample))
