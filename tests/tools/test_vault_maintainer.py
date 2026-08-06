import json
import sys
from pathlib import Path

import pytest


TOOLS = Path(__file__).resolve().parents[2] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import vault_maintainer as vault  # noqa: E402


def _write_registry(
    tmp_path: Path,
    scopes: list[dict],
    *,
    footer_lines: int = 10,
    vault_root: Path | None = None,
) -> Path:
    registry = {
        "schema_version": "vault_maintenance_v1",
        "vault_root": str(vault_root or tmp_path / "vault"),
        "navigation_footer_min_lines": footer_lines,
        "default_size_budget": {"warning_lines": 50, "error_lines": 100},
        "size_exceptions": [],
        "scopes": scopes,
    }
    path = tmp_path / "registry.json"
    path.write_text(json.dumps(registry), encoding="utf-8")
    return path


def _scope(root_moc: str, directory: str, *, state: str = "enforced") -> dict:
    return {
        "scope_id": "test",
        "owner": "Test Agent",
        "rollout_state": state,
        "root_mocs": [root_moc],
        "managed_directories": [directory],
    }


def _moc(title: str, children: list[tuple[str, str, str]]) -> str:
    lines = [f"# {title}", "", "A narrative introduction.", "", vault.MOC_START]
    lines.extend(f"- [[{target}|{label}]] - {summary}" for target, label, summary in children)
    lines.extend([vault.MOC_END, ""])
    return "\n".join(lines)


def test_parse_moc_children_supports_multiple_blocks_and_requires_sentences():
    text = (
        _moc("Root", [("Docs/One", "One", "First concept.")])
        + "\n## More\n\n"
        + vault.MOC_START
        + "\n- [[Docs/Two|Two]] - Missing punctuation\n"
        + vault.MOC_END
        + "\n"
    )

    children, diagnostics = vault.parse_moc_children(text, path="Root.md")

    assert [child.target for child in children] == ["Docs/One", "Docs/Two"]
    assert [item.code for item in diagnostics] == ["child_summary_not_sentence"]


def test_nested_mocs_generate_path_qualified_breadcrumbs_and_are_byte_idempotent(tmp_path):
    vault_root = tmp_path / "vault"
    (vault_root / "Docs" / "Nested").mkdir(parents=True)
    (vault_root / "Root.md").write_text(
        _moc("Root", [("Docs/Section", "Section", "Routes to the nested section.")]),
        encoding="utf-8",
    )
    (vault_root / "Docs" / "Section.md").write_text(
        _moc(
            "Section",
            [
                ("Docs/Nested/One", "One", "Explains the first concept."),
                ("Docs/Nested/Two", "Two", "Explains the second concept."),
            ],
        ),
        encoding="utf-8",
    )
    (vault_root / "Docs" / "Nested" / "One.md").write_text("# One\n\nBody.\n", encoding="utf-8")
    (vault_root / "Docs" / "Nested" / "Two.md").write_text(
        "# Two\n\n" + "line\n" * 12,
        encoding="utf-8",
    )
    registry_path = _write_registry(tmp_path, [_scope("Root.md", "Docs")])
    registry = vault.load_registry(registry_path)
    scope = registry.scopes[0]

    first = vault.navigation_changes(registry, [scope])
    vault._write_transaction(first)
    second = vault.navigation_changes(registry, [scope])

    assert second == {}
    one = (vault_root / "Docs" / "Nested" / "One.md").read_text(encoding="utf-8")
    two = (vault_root / "Docs" / "Nested" / "Two.md").read_text(encoding="utf-8")
    assert "Previous: none | Up: [[Docs/Section]] | Next: [[Docs/Nested/Two]]" in one
    assert two.count(vault.NAV_START) == 2


def test_multiple_canonical_parents_abort_navigation_sync(tmp_path):
    vault_root = tmp_path / "vault"
    (vault_root / "Docs").mkdir(parents=True)
    (vault_root / "Root.md").write_text(
        _moc(
            "Root",
            [
                ("Docs/Left", "Left", "Routes through the left map."),
                ("Docs/Right", "Right", "Routes through the right map."),
            ],
        ),
        encoding="utf-8",
    )
    for name in ("Left", "Right"):
        (vault_root / "Docs" / f"{name}.md").write_text(
            _moc(name, [("Docs/Shared", "Shared", "Claims the shared child.")]),
            encoding="utf-8",
        )
    (vault_root / "Docs" / "Shared.md").write_text("# Shared\n", encoding="utf-8")
    registry = vault.load_registry(_write_registry(tmp_path, [_scope("Root.md", "Docs")]))

    with pytest.raises(ValueError, match="structural validation failed"):
        vault.navigation_changes(registry, registry.scopes)


def test_frontmatter_after_heading_and_transclusion_are_rejected(tmp_path):
    vault_root = tmp_path / "vault"
    (vault_root / "Docs").mkdir(parents=True)
    (vault_root / "Root.md").write_text(
        "# Root\n\n---\nstatus: current\n---\n\n![[Image]]\n\n"
        + vault.MOC_START
        + "\n- [[Docs/Child|Child]] - Explains the child.\n"
        + vault.MOC_END
        + "\n",
        encoding="utf-8",
    )
    (vault_root / "Docs" / "Child.md").write_text("# Child\n", encoding="utf-8")
    registry = vault.load_registry(_write_registry(tmp_path, [_scope("Root.md", "Docs")]))
    diagnostics = vault.validate_scope(registry, registry.scopes[0], require_navigation=False)

    assert {item.code for item in diagnostics} >= {"frontmatter_not_first", "transclusion_in_moc"}


def test_validate_scope_supports_deep_worktree_paths(tmp_path):
    long_parent = tmp_path
    for index in range(12):
        long_parent = long_parent / f"segment-{index:02d}-xxxxxxxxxxxxxxxx"
    vault_root = long_parent / "vault"
    child_path = vault_root / "Docs" / "Child.md"
    assert len(str(child_path.resolve())) > 260
    vault._mkdir(child_path.parent)
    vault._write_text(
        vault_root / "Root.md",
        _moc("Root", [("Docs/Child", "Child", "Explains the child.")]),
    )
    vault._write_text(child_path, "# Child\n\nBody.\n")
    registry = vault.load_registry(
        _write_registry(tmp_path, [_scope("Root.md", "Docs")], vault_root=vault_root)
    )

    diagnostics = vault.validate_scope(registry, registry.scopes[0], require_navigation=False)

    assert [item for item in diagnostics if item.severity == "error"] == []


def test_plan_thread_slices_preserve_repeated_internal_headings_and_source_bytes():
    prelude = vault.A2A_PREAMBLE + "\n\n# Active\n\n"
    record_one = (
        vault.A2A_PREAMBLE
        + "\n\n## Codex Plan Handoff - 2026-07-01 00:00:00 UTC\n\n"
        + "**Topic:** First plan\n\n## Common Agreement\n\nA\n\n## Decision Status\n\nOpen.\n\n"
        + vault.A2A_PREAMBLE
        + "\n\n## Common Agreement\n\nB\n\n## Decision Status\n\nReviewed.\n\n"
    )
    record_two = (
        vault.A2A_PREAMBLE
        + "\n\n## Codex Plan Handoff - 2026-07-02 00:00:00 UTC\n\n"
        + "**Topic:** Second plan\n\n## Common Agreement\n\nC\n"
    )
    source = prelude + record_one + record_two

    slices = vault._slice_plan_thread(source, "Entries")
    vault._verify_source_slices(source.encode("utf-8"), slices)

    assert len(slices) == 3
    assert slices[1].payload.count("## Common Agreement") == 2
    assert slices[1].destination != slices[2].destination


def test_update_log_long_prefixes_get_hash_disambiguated_destinations():
    prefix = vault.A2A_PREAMBLE + "\n\n# Log\n\n## Update Entries\n\n"
    shared = "2026-07-01 00:00:00 UTC - " + "very long repeated prefix " * 6
    source = prefix + f"### {shared}alpha\n\nA\n\n### {shared}beta\n\nB\n"

    slices = vault._slice_update_log(source, "Updates")

    assert len(slices) == 3
    assert slices[1].destination != slices[2].destination
    vault._verify_source_slices(source.encode("utf-8"), slices)


def test_source_wrapper_round_trips_trailing_newlines_exactly():
    payload = "## Record\n\nBody.\n\n"
    wrapped = "# Container\n\n" + vault._source_wrapper(payload) + "\n"

    assert vault.extract_source_payload(wrapped) == payload.encode("utf-8")


def test_navigation_ignores_h1_inside_immutable_source_wrapper():
    payload = "# Archived Source Heading\n\nExact archived content.\n"
    document = vault._source_wrapper(payload) + "\n\n# Live Map Heading\n\nNarrative.\n"
    nav = (
        f"{vault.NAV_START}\n"
        "<< Previous: none | Up: [[Root]] | Next: none >>\n"
        f"{vault.NAV_END}"
    )

    rendered = vault.render_navigation(document, nav=nav, footer_min_lines=300)

    assert rendered.index(vault.NAV_START) > rendered.index("# Live Map Heading")
    assert vault.extract_source_payload(rendered) == payload.encode("utf-8")
