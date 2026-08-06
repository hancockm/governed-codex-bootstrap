"""Conservative maintenance for a path-qualified Markdown knowledge vault."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

LINK_PATTERN = re.compile(r"(?<!!)\[\[([^\]|#]+)(?:\|[^\]]+)?\]\]")
TRANSCLUSION_PATTERN = re.compile(r"!\[\[")
START = "<!-- generated:breadcrumbs:start -->"
END = "<!-- generated:breadcrumbs:end -->"


def _load(root: Path) -> tuple[dict[str, Any], Path]:
    """Load the maintenance registry and resolve its vault root."""
    registry = json.loads((root / "configs/vault_maintenance_registry_v1.json").read_text(encoding="utf-8"))
    return registry, root / registry["vault_root"]


def _notes(vault_root: Path) -> list[Path]:
    """Return deterministic Markdown note paths."""
    return sorted(vault_root.rglob("*.md"))


def _relative(path: Path, vault_root: Path) -> str:
    """Return a vault-relative POSIX path."""
    return path.relative_to(vault_root).as_posix()


def report(root: Path) -> dict[str, Any]:
    """Report vault note count, size diagnostics, and navigation issues without writes."""
    registry, vault_root = _load(root)
    diagnostics = check(root)
    oversized = [_relative(note, vault_root) for note in _notes(vault_root) if note.stat().st_size > registry["max_note_bytes"]]
    return {"ok": not diagnostics, "note_count": len(_notes(vault_root)), "oversized": oversized, "diagnostics": diagnostics}


def check(root: Path) -> list[str]:
    """Return conservative vault conformance errors without modifying files."""
    registry, vault_root = _load(root)
    errors: list[str] = []
    if not vault_root.is_dir():
        return ["vault root is missing"]
    dynamic_scopes = registry.get("dynamic_scopes", {})
    def dynamic(path: str) -> bool:
        return any(path == scope or path.startswith(f"{scope}/") for scope in dynamic_scopes)
    all_paths = {_relative(note, vault_root) for note in _notes(vault_root)}
    static_paths = {path for path in all_paths if not dynamic(path)} | {"40_Coordination/Generated/Active Records.md"}
    expected = set(registry["parentage"]) | {registry["root_moc"]}
    if static_paths != expected:
        errors.append("registry parentage must enumerate every Markdown note exactly once")
    if registry["root_moc"] in registry["parentage"]:
        errors.append("root MOC may not have a parent")
    for child, parent in registry["parentage"].items():
        if child not in all_paths or parent not in all_paths:
            errors.append(f"parentage references missing note: {child}")
        if "/" not in parent:
            errors.append(f"parentage link is not path-qualified: {parent}")
    for path in _notes(vault_root):
        relative = _relative(path, vault_root)
        text = path.read_text(encoding="utf-8")
        if TRANSCLUSION_PATTERN.search(text):
            errors.append(f"transclusion is forbidden: {relative}")
        if path.stat().st_size > registry["max_note_bytes"]:
            errors.append(f"note exceeds size diagnostic limit: {relative}")
        for target in LINK_PATTERN.findall(text):
            if "/" not in target:
                errors.append(f"link is not path-qualified: {relative} -> {target}")
            elif target not in all_paths and not dynamic(target):
                errors.append(f"link target is missing: {relative} -> {target}")
        if relative in registry["parentage"]:
            expected_breadcrumb = _breadcrumb(registry["parentage"][relative])
            if expected_breadcrumb not in text:
                errors.append(f"breadcrumb is missing or stale: {relative}")
    for moc, children in registry["mocs"].items():
        if moc not in all_paths:
            errors.append(f"MOC is missing: {moc}")
            continue
        text = (vault_root / moc).read_text(encoding="utf-8")
        for child in children:
            if f"[[{child}]]" not in text:
                errors.append(f"MOC link is missing: {moc} -> {child}")
    return errors


def _breadcrumb(parent: str) -> str:
    """Produce the generated, path-qualified breadcrumb block."""
    return f"{START}\n> Parent: [[{parent}]]\n{END}"


def sync_navigation(root: Path, apply: bool = False) -> dict[str, Any]:
    """Preview or apply only generated breadcrumb blocks after fail-closed checks.

    The registry must be complete and every existing generated block must be valid;
    no headings are split, moved, or deleted.
    """
    registry, vault_root = _load(root)
    initial = check(root)
    safe_errors = [error for error in initial if not error.startswith("breadcrumb is missing or stale:")]
    if safe_errors:
        return {"ok": False, "applied": False, "changes": [], "diagnostics": initial}
    changes: list[str] = []
    replacements: list[tuple[Path, str]] = []
    block_pattern = re.compile(re.escape(START) + r".*?" + re.escape(END) + r"\n?", re.DOTALL)
    for child, parent in registry["parentage"].items():
        path = vault_root / child
        text = path.read_text(encoding="utf-8")
        desired = _breadcrumb(parent) + "\n\n"
        updated = block_pattern.sub("", text).lstrip("\n")
        updated = desired + updated
        if updated != text:
            changes.append(child)
            replacements.append((path, updated))
    if apply:
        for path, text in replacements:
            path.write_text(text, encoding="utf-8")
        final = check(root)
        if final:
            return {"ok": False, "applied": True, "changes": changes, "diagnostics": final}
    return {"ok": True, "applied": apply, "changes": changes, "diagnostics": []}
