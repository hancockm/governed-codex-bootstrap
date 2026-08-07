#!/usr/bin/env python3
"""Validate and maintain the project's narrative Obsidian maps.

The maintainer is deliberately conservative. Narrative and child descriptions
remain owner-authored; routine commands only inspect structure or synchronize
explicitly delimited breadcrumb blocks. Destructive heading-based splitting is
not supported.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Sequence


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REGISTRY = ROOT / "configs" / "vault_maintenance_registry_v1.json"
DEFAULT_CORE_MOC_LAYOUT = ROOT / "configs" / "core_moc_v1.json"

MOC_START = "<!-- managed:moc-children:start -->"
MOC_END = "<!-- managed:moc-children:end -->"
NAV_START = "<!-- generated:breadcrumbs:start -->"
NAV_END = "<!-- generated:breadcrumbs:end -->"
SOURCE_START = "<!-- managed:source-slice:start -->"
SOURCE_END = "<!-- managed:source-slice:end -->"

MOC_BLOCK_RE = re.compile(
    rf"^{re.escape(MOC_START)}\r?\n(?P<body>.*?)^"
    rf"{re.escape(MOC_END)}\s*$",
    re.MULTILINE | re.DOTALL,
)
MOC_LINE_RE = re.compile(
    r"^- \[\[(?P<target>[^\]|]+)(?:\|(?P<label>[^\]]+))?\]\](?: - | — )(?P<summary>\S.*)$"
)
NAV_BLOCK_RE = re.compile(
    rf"(?:\r?\n)*^{re.escape(NAV_START)}\r?\n.*?^"
    rf"{re.escape(NAV_END)}(?:\r?\n)*",
    re.MULTILINE | re.DOTALL,
)
H1_RE = re.compile(r"^# (?!#)(?P<title>\S.*)$", re.MULTILINE)
TRANSCLUSION_RE = re.compile(r"!\[\[")
WIKILINK_RE = re.compile(r"(?<!!)\[\[(?P<target>[^\]|#]+)")

A2A_PREAMBLE = (
    "Be critical of this input. You need to be analytical in your response.  "
    "Do not take this as the answer. Look at the weak points in the argument. "
    "Let's begin to list areas of common agreement. List areas of disagreement. "
    "The goal for each iteration is to reduce one disagreement. If each round, "
    "you eliminate one disagreement but add 2 disagreements you are going in the wrong direction.  "
    "We need to converge on a plan. List ALL remaining disagreements. "
    "Don't keep adding them after each round."
)


@dataclass(frozen=True)
class Diagnostic:
    """One validation or inventory finding."""

    severity: str
    code: str
    path: str
    message: str


@dataclass(frozen=True)
class ChildLink:
    """One owner-authored child declaration in a managed MOC block."""

    target: str
    label: str
    summary: str
    line_number: int


@dataclass(frozen=True)
class Scope:
    """One registry-owned documentation scope."""

    scope_id: str
    owner: str
    rollout_state: str
    root_mocs: tuple[str, ...]
    managed_directories: tuple[str, ...]
    warning_lines: int
    error_lines: int


@dataclass(frozen=True)
class Registry:
    """Parsed vault-maintenance registry."""

    path: Path
    vault_root: Path
    footer_min_lines: int
    scopes: tuple[Scope, ...]
    size_exceptions: Mapping[str, Mapping[str, object]]


@dataclass(frozen=True)
class MocGraph:
    """Resolved parent and sibling relationships for one managed scope."""

    parents: Mapping[str, str]
    sibling_lists: Mapping[str, tuple[str, ...]]
    mocs: frozenset[str]
    diagnostics: tuple[Diagnostic, ...]


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _vault_relative(path: Path, vault_root: Path) -> str:
    return path.resolve().relative_to(vault_root.resolve()).as_posix()


def _normalize_target(target: str) -> str:
    value = target.strip().replace("\\", "/")
    if value.endswith(".md"):
        value = value[:-3]
    return value.strip("/")


def _target_path(vault_root: Path, target: str) -> Path:
    normalized = _normalize_target(target)
    if not normalized or normalized.startswith("../") or "/../" in normalized:
        raise ValueError(f"unsafe or empty wikilink target: {target!r}")
    candidate = (vault_root / f"{normalized}.md").resolve()
    candidate.relative_to(vault_root.resolve())
    return candidate


def _windows_long_path(path: Path) -> Path:
    """Return a Windows long-path capable absolute path when needed."""

    if os.name != "nt":
        return path
    if not path.is_absolute():
        return path
    value = str(path)
    if value.startswith("\\\\?\\"):
        return path
    if value.startswith("\\\\"):
        return Path("\\\\?\\UNC\\" + value.lstrip("\\"))
    return Path("\\\\?\\" + value)


def _path_exists(path: Path) -> bool:
    """Return whether path exists without failing on deep Windows worktrees."""

    return _windows_long_path(path).exists()


def _read_text(path: Path) -> str:
    """Read UTF-8 text from a path that may exceed Windows MAX_PATH."""

    return _windows_long_path(path).read_text(encoding="utf-8")


def _read_bytes(path: Path) -> bytes:
    """Read bytes from a path that may exceed Windows MAX_PATH."""

    return _windows_long_path(path).read_bytes()


def _write_text(path: Path, text: str, *, newline: str | None = None) -> None:
    """Write UTF-8 text to a path that may exceed Windows MAX_PATH."""

    _windows_long_path(path).write_text(text, encoding="utf-8", newline=newline)


def _write_bytes(path: Path, data: bytes) -> None:
    """Write bytes to a path that may exceed Windows MAX_PATH."""

    _windows_long_path(path).write_bytes(data)


def _mkdir(path: Path) -> None:
    """Create a directory that may exceed Windows MAX_PATH."""

    _windows_long_path(path).mkdir(parents=True, exist_ok=True)


def _replace(source: Path, destination: Path) -> None:
    """Atomically replace a destination that may exceed Windows MAX_PATH."""

    os.replace(_windows_long_path(source), _windows_long_path(destination))


def _unlink(path: Path) -> None:
    """Remove a path that may exceed Windows MAX_PATH if it exists."""

    _windows_long_path(path).unlink(missing_ok=True)


def load_registry(path: Path = DEFAULT_REGISTRY) -> Registry:
    """Load and validate the maintenance registry."""

    data = json.loads(_read_text(path))
    if data.get("schema_version") != "vault_maintenance_v1":
        raise ValueError("unsupported vault maintenance registry schema")
    vault_value = Path(str(data["vault_root"]))
    vault_root = vault_value if vault_value.is_absolute() else ROOT / vault_value
    default_budget = data["default_size_budget"]
    scopes = tuple(
        Scope(
            scope_id=str(raw["scope_id"]),
            owner=str(raw["owner"]),
            rollout_state=str(raw["rollout_state"]),
            root_mocs=tuple(str(item) for item in raw.get("root_mocs", [])),
            managed_directories=tuple(str(item) for item in raw.get("managed_directories", [])),
            warning_lines=int(raw.get("warning_lines", default_budget["warning_lines"])),
            error_lines=int(raw.get("error_lines", default_budget["error_lines"])),
        )
        for raw in data["scopes"]
    )
    exceptions = {
        str(item["path"]): item for item in data.get("size_exceptions", [])
    }
    return Registry(
        path=path,
        vault_root=vault_root,
        footer_min_lines=int(data["navigation_footer_min_lines"]),
        scopes=scopes,
        size_exceptions=exceptions,
    )


def _selected_scopes(registry: Registry, scope_ids: Sequence[str]) -> tuple[Scope, ...]:
    if not scope_ids:
        return registry.scopes
    wanted = set(scope_ids)
    selected = tuple(scope for scope in registry.scopes if scope.scope_id in wanted)
    missing = wanted - {scope.scope_id for scope in selected}
    if missing:
        raise ValueError(f"unknown scope IDs: {', '.join(sorted(missing))}")
    return selected


def parse_moc_children(text: str, *, path: str) -> tuple[list[ChildLink], list[Diagnostic]]:
    """Parse explicit MOC child blocks without interpreting other wikilinks."""

    children: list[ChildLink] = []
    diagnostics: list[Diagnostic] = []
    for block in MOC_BLOCK_RE.finditer(text):
        body_start = block.start("body")
        for offset, line in enumerate(block.group("body").splitlines()):
            line_number = text.count("\n", 0, body_start) + offset + 1
            if not line.strip():
                continue
            match = MOC_LINE_RE.fullmatch(line)
            if not match:
                diagnostics.append(
                    Diagnostic("error", "invalid_child_line", path, f"line {line_number}: {line}")
                )
                continue
            target = _normalize_target(match.group("target"))
            label = (match.group("label") or Path(target).name).strip()
            summary = match.group("summary").strip()
            if "/" not in target:
                diagnostics.append(
                    Diagnostic(
                        "error",
                        "unqualified_child_link",
                        path,
                        f"line {line_number}: {target}",
                    )
                )
            if summary[-1:] not in {".", "?", "!"}:
                diagnostics.append(
                    Diagnostic(
                        "error",
                        "child_summary_not_sentence",
                        path,
                        f"line {line_number}: {summary}",
                    )
                )
            children.append(ChildLink(target, label, summary, line_number))
    return children, diagnostics


def _frontmatter_diagnostics(text: str, path: str) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    visible = re.sub(
        rf"{re.escape(SOURCE_START)}.*?{re.escape(SOURCE_END)}",
        "",
        text,
        flags=re.DOTALL,
    )
    markers = list(re.finditer(r"(?m)^---\s*$", visible))
    for opening, closing in zip(markers[::2], markers[1::2]):
        body = visible[opening.end() : closing.start()]
        if re.search(r"(?m)^[A-Za-z_][\w-]*:\s*.*$", body):
            if opening.start() != 0:
                diagnostics.append(
                    Diagnostic(
                        "error",
                        "frontmatter_not_first",
                        path,
                        "frontmatter must begin at byte zero",
                    )
                )
            break
    return diagnostics


def _visible_h1(text: str) -> re.Match[str] | None:
    """Return the first H1 outside an immutable source-slice wrapper."""

    source_ranges = tuple(
        (match.start(), match.end())
        for match in re.finditer(
            rf"{re.escape(SOURCE_START)}.*?{re.escape(SOURCE_END)}",
            text,
            flags=re.DOTALL,
        )
    )
    for match in H1_RE.finditer(text):
        if not any(start <= match.start() < end for start, end in source_ranges):
            return match
    return None


def _moc_diagnostics(text: str, path: str) -> list[Diagnostic]:
    diagnostics = _frontmatter_diagnostics(text, path)
    diagnostics.extend(_wikilink_diagnostics(text, path))
    if TRANSCLUSION_RE.search(text):
        diagnostics.append(
            Diagnostic("error", "transclusion_in_moc", path, "managed MOCs cannot contain ![[...]]")
        )
    if not _visible_h1(text):
        diagnostics.append(Diagnostic("error", "missing_h1", path, "managed MOC has no H1"))
    return diagnostics


def _wikilink_diagnostics(text: str, path: str) -> list[Diagnostic]:
    """Reject file extensions that Obsidian would expose as link labels."""

    diagnostics: list[Diagnostic] = []
    for match in WIKILINK_RE.finditer(text):
        target = match.group("target").strip().replace("\\", "/")
        if target.endswith(".md"):
            diagnostics.append(
                Diagnostic(
                    "error",
                    "markdown_extension_in_wikilink",
                    path,
                    f"use extensionless Obsidian target: {target[:-3]}",
                )
            )
    return diagnostics


def build_scope_graph(registry: Registry, scope: Scope) -> MocGraph:
    """Resolve all MOCs and children reachable from a scope's roots."""

    vault_root = registry.vault_root
    parents: dict[str, str] = {}
    sibling_lists: dict[str, tuple[str, ...]] = {}
    mocs: set[str] = set()
    diagnostics: list[Diagnostic] = []
    queue = [_normalize_target(item) for item in scope.root_mocs]
    seen: set[str] = set()

    while queue:
        moc_target = queue.pop(0)
        if moc_target in seen:
            continue
        seen.add(moc_target)
        moc_path = _target_path(vault_root, moc_target)
        moc_rel = f"{moc_target}.md"
        if not _path_exists(moc_path):
            diagnostics.append(Diagnostic("error", "missing_root_or_moc", moc_rel, "file does not exist"))
            continue
        text = _read_text(moc_path)
        children, parse_diagnostics = parse_moc_children(text, path=moc_rel)
        diagnostics.extend(_moc_diagnostics(text, moc_rel))
        diagnostics.extend(parse_diagnostics)
        mocs.add(moc_target)
        targets = tuple(child.target for child in children)
        sibling_lists[moc_target] = targets
        for child in children:
            try:
                child_path = _target_path(vault_root, child.target)
            except ValueError as exc:
                diagnostics.append(Diagnostic("error", "unsafe_child_link", moc_rel, str(exc)))
                continue
            child_rel = f"{child.target}.md"
            if not _path_exists(child_path):
                diagnostics.append(
                    Diagnostic("error", "missing_child", moc_rel, f"line {child.line_number}: {child_rel}")
                )
                continue
            existing_parent = parents.get(child.target)
            if existing_parent and existing_parent != moc_target:
                diagnostics.append(
                    Diagnostic(
                        "error",
                        "multiple_canonical_parents",
                        child_rel,
                        f"claimed by {existing_parent}.md and {moc_rel}",
                    )
                )
                continue
            parents[child.target] = moc_target
            child_text = _read_text(child_path)
            if MOC_START in child_text:
                queue.append(child.target)

    return MocGraph(parents, sibling_lists, frozenset(mocs), tuple(diagnostics))


def _expected_nav(graph: MocGraph, target: str) -> str:
    parent = graph.parents[target]
    siblings = graph.sibling_lists[parent]
    index = siblings.index(target)
    previous = f"[[{siblings[index - 1]}]]" if index else "none"
    following = f"[[{siblings[index + 1]}]]" if index + 1 < len(siblings) else "none"
    return (
        f"{NAV_START}\n"
        f"<< Previous: {previous} | Up: [[{parent}]] | Next: {following} >>\n"
        f"{NAV_END}"
    )


def _strip_nav(text: str) -> str:
    return NAV_BLOCK_RE.sub("\n\n", text).strip("\n") + "\n"


def render_navigation(text: str, *, nav: str, footer_min_lines: int) -> str:
    """Return text with deterministic top and optional footer navigation."""

    base = _strip_nav(text)
    h1 = _visible_h1(base)
    if not h1:
        raise ValueError("cannot insert navigation into a document without an H1")
    insertion = h1.end()
    rendered = base[:insertion] + "\n\n" + nav + base[insertion:]
    if len(rendered.splitlines()) >= footer_min_lines:
        rendered = rendered.rstrip("\n") + "\n\n" + nav + "\n"
    elif not rendered.endswith("\n"):
        rendered += "\n"
    return rendered


def _size_diagnostic(
    registry: Registry,
    scope: Scope,
    relative_path: str,
    line_count: int,
) -> Diagnostic | None:
    if relative_path in registry.size_exceptions:
        return None
    if line_count > scope.error_lines:
        return Diagnostic(
            "error",
            "size_error",
            relative_path,
            f"{line_count} lines exceeds {scope.error_lines}",
        )
    if line_count > scope.warning_lines:
        return Diagnostic(
            "warning",
            "size_warning",
            relative_path,
            f"{line_count} lines exceeds {scope.warning_lines}",
        )
    return None


def validate_scope(registry: Registry, scope: Scope, *, require_navigation: bool) -> list[Diagnostic]:
    """Validate one scope and return deterministic diagnostics."""

    graph = build_scope_graph(registry, scope)
    diagnostics = list(graph.diagnostics)
    vault_root = registry.vault_root
    for target, parent in sorted(graph.parents.items()):
        del parent
        path = _target_path(vault_root, target)
        relative_path = f"{target}.md"
        text = _read_text(path)
        diagnostics.extend(_frontmatter_diagnostics(text, relative_path))
        diagnostics.extend(_wikilink_diagnostics(text, relative_path))
        visible_h1 = _visible_h1(text)
        if not visible_h1:
            diagnostics.append(Diagnostic("error", "missing_h1", relative_path, "managed child has no H1"))
        size = _size_diagnostic(registry, scope, relative_path, len(text.splitlines()))
        if size:
            diagnostics.append(size)
        if require_navigation and visible_h1:
            expected = render_navigation(
                text,
                nav=_expected_nav(graph, target),
                footer_min_lines=registry.footer_min_lines,
            )
            if expected != text:
                diagnostics.append(
                    Diagnostic("error", "navigation_drift", relative_path, "breadcrumb block is missing or stale")
                )

    linked = set(graph.parents) | set(graph.mocs)
    for directory in scope.managed_directories:
        directory_path = registry.vault_root / directory
        if not _path_exists(directory_path):
            continue
        for path in directory_path.rglob("*.md"):
            target = _vault_relative(path, vault_root)[:-3]
            if target not in linked:
                severity = "warning" if scope.rollout_state != "enforced" else "error"
                diagnostics.append(
                    Diagnostic(severity, "orphaned_managed_note", f"{target}.md", "not reachable from a root MOC")
                )
    return sorted(diagnostics, key=lambda item: (item.severity, item.path, item.code, item.message))


def _effective_diagnostics(scope: Scope, diagnostics: Iterable[Diagnostic]) -> list[Diagnostic]:
    if scope.rollout_state == "enforced":
        return list(diagnostics)
    return [
        Diagnostic("warning", item.code, item.path, item.message)
        if item.severity == "error"
        else item
        for item in diagnostics
    ]


def collect_diagnostics(
    registry: Registry,
    scopes: Sequence[Scope],
    *,
    require_navigation: bool,
) -> list[Diagnostic]:
    """Collect effective diagnostics for the selected ownership scopes."""

    diagnostics: list[Diagnostic] = []
    for scope in scopes:
        diagnostics.extend(
            _effective_diagnostics(
                scope,
                validate_scope(registry, scope, require_navigation=require_navigation),
            )
        )
    return diagnostics


def _print_diagnostics(diagnostics: Sequence[Diagnostic]) -> None:
    for item in diagnostics:
        print(f"{item.severity.upper()} [{item.code}] {item.path}: {item.message}")
    errors = sum(item.severity == "error" for item in diagnostics)
    warnings = sum(item.severity == "warning" for item in diagnostics)
    print(f"Vault diagnostics: {errors} error(s), {warnings} warning(s)")


def _write_transaction(changes: Mapping[Path, str]) -> None:
    """Apply text changes with rollback if any replacement fails."""

    originals = {path: _read_bytes(path) if _path_exists(path) else None for path in changes}
    temporary: dict[Path, Path] = {}
    replaced: list[Path] = []
    try:
        for path, text in changes.items():
            _mkdir(path.parent)
            temp_id = _sha256(str(path).encode("utf-8"))[:12]
            temp = path.with_name(f".project-vault-{temp_id}.tmp")
            _write_text(temp, text, newline="\n")
            temporary[path] = temp
        for path, temp in temporary.items():
            _replace(temp, path)
            replaced.append(path)
    except Exception:
        for path in replaced:
            original = originals[path]
            if original is None:
                _unlink(path)
            else:
                _write_bytes(path, original)
        raise
    finally:
        for temp in temporary.values():
            _unlink(temp)


def navigation_changes(registry: Registry, scopes: Sequence[Scope]) -> dict[Path, str]:
    """Build the complete breadcrumb change set after structural validation."""

    diagnostics = collect_diagnostics(registry, scopes, require_navigation=False)
    errors = [item for item in diagnostics if item.severity == "error"]
    if errors:
        _print_diagnostics(diagnostics)
        raise ValueError("navigation synchronization refused because structural validation failed")
    changes: dict[Path, str] = {}
    for scope in scopes:
        graph = build_scope_graph(registry, scope)
        for target in sorted(graph.parents):
            path = _target_path(registry.vault_root, target)
            text = _read_text(path)
            rendered = render_navigation(
                text,
                nav=_expected_nav(graph, target),
                footer_min_lines=registry.footer_min_lines,
            )
            if rendered != text:
                changes[path] = rendered
    return changes


def _run_git(*args: str) -> bytes:
    result = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        capture_output=True,
        check=False,
    )
    if result.returncode:
        raise RuntimeError(result.stderr.decode("utf-8", errors="replace").strip())
    return result.stdout


def _git_blob(source_ref: str, relative_path: str) -> tuple[str, bytes]:
    listing = _run_git("ls-tree", source_ref, "--", relative_path).decode("utf-8").strip()
    if not listing:
        raise ValueError(f"missing Git source at {source_ref}:{relative_path}")
    blob_id = listing.split()[2]
    data = _run_git("show", f"{source_ref}:{relative_path}")
    return blob_id, data


def _source_wrapper(payload: str) -> str:
    return f"{SOURCE_START}\n{payload}\n{SOURCE_END}"


def extract_source_payload(text: str) -> bytes:
    """Extract one exact UTF-8 payload from a migrated source wrapper."""

    start_marker = f"{SOURCE_START}\n"
    end_marker = f"\n{SOURCE_END}"
    start = text.find(start_marker)
    end = text.rfind(end_marker)
    if start < 0 or end < start:
        raise ValueError("missing or malformed source slice markers")
    return text[start + len(start_marker) : end].encode("utf-8")


def _safe_slug(value: str, *, limit: int = 72) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-") or "record"
    return slug[:limit].rstrip("-")


def _timestamp_parts(value: str) -> tuple[str, str]:
    match = re.search(r"(?P<date>\d{4}-\d{2}-\d{2})(?:[ T](?P<time>\d{2}:?\d{2}:?\d{2}))?", value)
    if not match:
        return "undated", "undated"
    date = match.group("date")
    time_value = (match.group("time") or "000000").replace(":", "")
    return date[:7], f"{date.replace('-', '')}T{time_value}Z"


@dataclass(frozen=True)
class SourceSlice:
    """One exact source range and its destination record."""

    ordinal: int
    start: int
    end: int
    payload: str
    title: str
    timestamp: str
    destination: str


def _slice_update_log(text: str, base_dir: str) -> tuple[SourceSlice, ...]:
    marker = text.find("## Update Entries")
    starts = [match.start() for match in re.finditer(r"(?m)^### \S", text[marker if marker >= 0 else 0 :])]
    offset = marker if marker >= 0 else 0
    starts = [item + offset for item in starts]
    if not starts:
        return (SourceSlice(0, 0, len(text), text, "Source prelude", "undated", ""),)
    slices = [SourceSlice(0, 0, starts[0], text[: starts[0]], "Source prelude", "undated", "")]
    for index, start in enumerate(starts, 1):
        end = starts[index] if index < len(starts) else len(text)
        payload = text[start:end]
        heading = payload.splitlines()[0].removeprefix("### ").strip()
        month, stamp = _timestamp_parts(heading)
        digest = _sha256(payload.encode("utf-8"))[:12]
        destination = f"{base_dir}/{month}/{stamp}-{_safe_slug(heading, limit=32)}-{digest}.md"
        slices.append(SourceSlice(index, start, end, payload, heading, heading, destination))
    return tuple(slices)


def _slice_plan_thread(text: str, base_dir: str) -> tuple[SourceSlice, ...]:
    starts: list[int] = []
    for heading in re.finditer(r"(?m)^## Codex Plan Handoff - (?P<timestamp>.+)$", text):
        preamble = text.rfind(A2A_PREAMBLE, 0, heading.start())
        start = preamble if preamble >= 0 else heading.start()
        if not starts or start > starts[-1]:
            starts.append(start)
    if not starts:
        return (SourceSlice(0, 0, len(text), text, "Source prelude", "undated", ""),)
    slices = [SourceSlice(0, 0, starts[0], text[: starts[0]], "Source prelude", "undated", "")]
    for index, start in enumerate(starts, 1):
        end = starts[index] if index < len(starts) else len(text)
        payload = text[start:end]
        heading_match = re.search(r"(?m)^## Codex Plan Handoff - (?P<timestamp>.+)$", payload)
        topic_match = re.search(r"(?m)^\*\*Topic:\*\*\s*(?P<topic>.+)$", payload)
        timestamp = heading_match.group("timestamp").strip() if heading_match else "undated"
        topic = topic_match.group("topic").strip() if topic_match else "Implementation plan critique"
        month, stamp = _timestamp_parts(timestamp)
        digest = _sha256(payload.encode("utf-8"))[:12]
        destination = f"{base_dir}/{month}/{stamp}-{_safe_slug(topic, limit=32)}-{digest}.md"
        slices.append(SourceSlice(index, start, end, payload, topic, timestamp, destination))
    return tuple(slices)


def _slice_repeated_preamble(text: str, base_dir: str) -> tuple[SourceSlice, ...]:
    occurrences = [match.start() for match in re.finditer(re.escape(A2A_PREAMBLE), text)]
    starts = occurrences[1:]
    if not starts:
        return (SourceSlice(0, 0, len(text), text, "Source prelude", "undated", ""),)
    slices = [SourceSlice(0, 0, starts[0], text[: starts[0]], "Source prelude", "undated", "")]
    for index, start in enumerate(starts, 1):
        end = starts[index] if index < len(starts) else len(text)
        payload = text[start:end]
        heading_match = re.search(r"(?m)^## (?P<title>.+)$", payload)
        title = heading_match.group("title").strip() if heading_match else f"Discussion round {index}"
        month, stamp = _timestamp_parts(title)
        if month == "undated":
            month, stamp = "undated", f"round-{index:04d}"
        digest = _sha256(payload.encode("utf-8"))[:12]
        destination = f"{base_dir}/{month}/{stamp}-{_safe_slug(title, limit=32)}-{digest}.md"
        slices.append(SourceSlice(index, start, end, payload, title, title, destination))
    return tuple(slices)


def _record_text(slice_: SourceSlice, parent_target: str) -> str:
    title = slice_.title.replace("\n", " ").strip()
    record_id = f"a2a:{_safe_slug(slice_.timestamp, limit=32)}:{_sha256(slice_.payload.encode('utf-8'))[:12]}"
    return (
        "---\n"
        "schema_version: a2a_record_v1\n"
        f"record_id: {record_id}\n"
        f"topic: {json.dumps(title, ensure_ascii=True)}\n"
        f"created_utc: {json.dumps(slice_.timestamp, ensure_ascii=True)}\n"
        "status: migrated\n"
        f"parent_moc: {json.dumps(parent_target, ensure_ascii=True)}\n"
        "prior_round_ref:\n"
        "---\n\n"
        f"# {title}\n\n"
        f"{_source_wrapper(slice_.payload)}\n"
    )


def _monthly_moc_text(month: str, target: str, records: Sequence[SourceSlice]) -> str:
    lines = [
        f"# {month} Agent-To-Agent Records",
        "",
        "This chronological map preserves exact source records for selective review.",
        "",
        MOC_START,
    ]
    for record in records:
        child_target = _normalize_target(record.destination)
        label = record.title.replace("|", "-").replace("]", ")")
        lines.append(f"- [[{child_target}|{label}]] - Preserves source record: {label}.")
    lines.extend([MOC_END, ""])
    return "\n".join(lines)


def _existing_a2a_records(vault_root: Path, base_dir: str) -> tuple[SourceSlice, ...]:
    """Return schema-versioned records created after the recovery source ref."""

    base_path = vault_root / base_dir
    if not _path_exists(base_path):
        return ()
    records: list[SourceSlice] = []
    for path in sorted(base_path.rglob("*.md")):
        if path.name == "README.md":
            continue
        text = _read_text(path)
        if "schema_version: a2a_record_v1" not in text:
            continue
        title_match = H1_RE.search(text)
        title = title_match.group("title").strip() if title_match else path.stem
        destination = _vault_relative(path, vault_root)
        month = path.parent.name
        records.append(
            SourceSlice(
                ordinal=0,
                start=0,
                end=0,
                payload="",
                title=title,
                timestamp=month,
                destination=destination,
            )
        )
    return tuple(records)


def _migration_moc_text(
    prefix: SourceSlice,
    *,
    title: str,
    monthly_mocs: Sequence[tuple[str, str]],
) -> str:
    lines = [
        _source_wrapper(prefix.payload),
        "",
        f"# {title}",
        "",
        "This narrative map preserves the original thread prelude and routes to losslessly migrated records.",
        "",
        "## Record Archive",
        "",
        "Open only the month that contains the implementation or critique event under review.",
        "",
        MOC_START,
    ]
    for month, target in monthly_mocs:
        lines.append(f"- [[{target}|{month} records]] - Groups the preserved {month} records in chronological order.")
    lines.extend([MOC_END, ""])
    return "\n".join(lines)


def _verify_source_slices(source: bytes, slices: Sequence[SourceSlice]) -> None:
    reconstructed = "".join(item.payload for item in sorted(slices, key=lambda item: item.ordinal)).encode("utf-8")
    if reconstructed != source:
        raise ValueError("source slices do not reconstruct the original Git blob")


def build_a2a_migration(source_ref: str, registry: Registry) -> tuple[dict[Path, str], dict[str, object], tuple[Path, ...]]:
    """Build the complete verified A2A migration without writing files."""

    sources = [
        {
            "path": "Project_Obsidian_Vault/40_Coordination/Critique Update Log.md",
            "vault_path": "40_Coordination/Critique Update Log.md",
            "title": "Critique Update Log",
            "base": "40_Coordination/Critique Update Log Entries",
            "slicer": _slice_update_log,
        },
        {
            "path": "Project_Obsidian_Vault/40_Coordination/Implementation Plan Critiques/Active Implementation Plan Critiques.md",
            "vault_path": "40_Coordination/Implementation Plan Critiques/Active Implementation Plan Critiques.md",
            "title": "Active Implementation Plan Critiques",
            "base": "40_Coordination/Implementation Plan Critiques/Entries",
            "slicer": _slice_plan_thread,
        },
        {
            "path": "Project_Obsidian_Vault/40_Coordination/Core Boundary Requests/Workgroup Output Record Request.md",
            "vault_path": "40_Coordination/Core Boundary Requests/Workgroup Output Record Request.md",
            "title": "Workgroup Output Record Request",
            "base": "40_Coordination/Core Boundary Requests/Workgroup Output Record Request Entries",
            "slicer": _slice_repeated_preamble,
        },
    ]
    changes: dict[Path, str] = {}
    manifest_sources: list[dict[str, object]] = []
    cleanup: list[Path] = []

    for source in sources:
        blob_id, source_bytes = _git_blob(source_ref, str(source["path"]))
        text = source_bytes.decode("utf-8")
        slicer = source["slicer"]
        slices = slicer(text, str(source["base"]))
        _verify_source_slices(source_bytes, slices)
        prefix, records = slices[0], slices[1:]
        grouped: dict[str, list[SourceSlice]] = {}
        for record in records:
            month = Path(record.destination).parent.name
            grouped.setdefault(month, []).append(record)
            record_path = registry.vault_root / record.destination
            parent_target = f"{Path(record.destination).parent.as_posix()}/README"
            changes[record_path] = _record_text(record, parent_target)
        existing_destinations = {record.destination for records_ in grouped.values() for record in records_}
        for existing in _existing_a2a_records(registry.vault_root, str(source["base"])):
            if existing.destination in existing_destinations:
                continue
            month = Path(existing.destination).parent.name
            grouped.setdefault(month, []).append(existing)
        monthly_targets: list[tuple[str, str]] = []
        for month, month_records in sorted(grouped.items()):
            moc_target = f"{source['base']}/{month}/README"
            monthly_targets.append((month, moc_target))
            changes[registry.vault_root / f"{moc_target}.md"] = _monthly_moc_text(
                month,
                moc_target,
                month_records,
            )
        source_path = ROOT / str(source["path"])
        changes[source_path] = _migration_moc_text(
            prefix,
            title=str(source["title"]),
            monthly_mocs=monthly_targets,
        )
        manifest_sources.append(
            {
                "path": str(source["path"]),
                "blob_id": blob_id,
                "byte_count": len(source_bytes),
                "sha256": _sha256(source_bytes),
                "slices": [
                    {
                        "ordinal": item.ordinal,
                        "start": item.start,
                        "end": item.end,
                        "sha256": _sha256(item.payload.encode("utf-8")),
                        "destination": str(source["vault_path"]) if item.ordinal == 0 else item.destination,
                    }
                    for item in slices
                ],
            }
        )
        failed_dir = source_path.with_name(f"{source_path.stem} Logs")
        if _path_exists(failed_dir):
            cleanup.append(failed_dir)

    manifest_id = f"a2a-{source_ref[:12]}-{_sha256(json.dumps(manifest_sources, sort_keys=True).encode())[:12]}"
    manifest = {
        "schema_version": "vault_migration_manifest_v1",
        "migration_id": manifest_id,
        "source_ref": source_ref,
        "sources": manifest_sources,
    }
    manifest_path = registry.vault_root / "90_Archive" / "Generated" / "vault_migrations" / f"{manifest_id}.json"
    changes[manifest_path] = json.dumps(manifest, indent=2, ensure_ascii=True) + "\n"
    return changes, manifest, tuple(cleanup)


def _verify_migrated_manifest(manifest: Mapping[str, object], vault_root: Path) -> None:
    for source in manifest["sources"]:
        assert isinstance(source, dict)
        payloads: list[bytes] = []
        for slice_info in sorted(source["slices"], key=lambda item: item["ordinal"]):
            destination = vault_root / slice_info["destination"]
            text = _read_text(destination)
            payload = extract_source_payload(text)
            if _sha256(payload) != slice_info["sha256"]:
                raise ValueError(f"migrated slice hash mismatch: {destination}")
            payloads.append(payload)
        reconstructed = b"".join(payloads)
        if len(reconstructed) != source["byte_count"] or _sha256(reconstructed) != source["sha256"]:
            raise ValueError(f"migrated source reconstruction mismatch: {source['path']}")


def _heading_sections(text: str, *, level: int) -> tuple[str, tuple[tuple[str, str], ...]]:
    marker = "#" * level
    matches = list(re.finditer(rf"(?m)^{re.escape(marker)} (?!#)(?P<title>\S.*)$", text))
    if not matches:
        return text, ()
    prefix = text[: matches[0].start()]
    sections: list[tuple[str, str]] = []
    for index, match in enumerate(matches):
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        sections.append((match.group("title").strip(), text[match.start() : end]))
    return prefix, tuple(sections)


def _promote_first_heading(text: str, *, from_level: int) -> str:
    source = "#" * from_level + " "
    if not text.startswith(source):
        raise ValueError(f"section does not begin with an H{from_level} heading")
    return "# " + text[len(source) :]


def _render_declared_moc(
    prefix: str,
    *,
    groups: Sequence[Mapping[str, object]],
    child_dir: str,
) -> str:
    lines = [prefix.rstrip(), ""]
    seen: set[str] = set()
    for group in groups:
        heading = str(group["heading"])
        narrative = str(group["narrative"])
        lines.extend([f"## {heading}", "", narrative, "", MOC_START])
        for child in group["children"]:
            title, summary = str(child[0]), str(child[1])
            if title in seen:
                raise ValueError(f"duplicate MOC child declaration: {title}")
            seen.add(title)
            target = f"00_Canonical/{child_dir}/{_section_filename(title)}"
            lines.append(f"- [[{target}|{title}]] - {summary}")
        lines.extend([MOC_END, ""])
    return "\n".join(lines)


def build_core_source_migration(
    source_ref: str,
    registry: Registry,
) -> tuple[dict[Path, str], dict[str, object]]:
    """Build Core section files from exact pre-split Git blobs."""

    documents = (
        ("Core Thesis.md", "Core"),
        ("ARCHITECTURE.md", "Architecture"),
        ("SPEC.md", "Spec"),
        ("ROADMAP.md", "Roadmap"),
    )
    nested = {
        ("ARCHITECTURE.md", "System Layers"),
        ("SPEC.md", "Data Types"),
        ("SPEC.md", "Embedding"),
    }
    identities: list[dict[str, object]] = []
    source_payloads: list[tuple[str, str, str, bytes]] = []
    for name, child_dir in documents:
        source_path = f"Project_Obsidian_Vault/00_Canonical/{name}"
        blob_id, source_bytes = _git_blob(source_ref, source_path)
        identities.append(
            {
                "path": source_path,
                "blob_id": blob_id,
                "byte_count": len(source_bytes),
                "sha256": _sha256(source_bytes),
            }
        )
        source_payloads.append((name, child_dir, source_path, source_bytes))
    manifest_seed = json.dumps(identities, sort_keys=True, ensure_ascii=True).encode("utf-8")
    migration_id = f"core-{source_ref[:12]}-{_sha256(manifest_seed)[:12]}"
    archive_root = (
        registry.vault_root
        / "90_Archive"
        / "Generated"
        / "vault_migrations"
        / migration_id
        / "source_slices"
    )
    changes: dict[Path, str] = {}
    manifest_sources: list[dict[str, object]] = []
    source_prefixes: dict[str, str] = {}
    source_sections: dict[tuple[str, str], str] = {}

    for name, child_dir, source_path, source_bytes in source_payloads:
        source_text = source_bytes.decode("utf-8")
        archive_path = archive_root / f"{_section_filename(Path(name).stem)}.md"
        changes[archive_path] = _source_wrapper(source_text) + "\n"
        prefix, sections = _heading_sections(source_text, level=2)
        source_prefixes[name] = prefix
        for title, payload in sections:
            source_sections[(name, title)] = payload
            child_path = (
                registry.vault_root
                / "00_Canonical"
                / child_dir
                / f"{_section_filename(title)}.md"
            )
            child_text = _promote_first_heading(payload, from_level=2)
            changes[child_path] = child_text
            if (name, title) in nested:
                _, subsections = _heading_sections(payload, level=3)
                nested_dir = child_path.with_suffix("")
                for subtitle, subpayload in subsections:
                    nested_path = nested_dir / f"{_section_filename(subtitle)}.md"
                    nested_text = _promote_first_heading(subpayload, from_level=3)
                    changes[nested_path] = nested_text
        identity = next(item for item in identities if item["path"] == source_path)
        manifest_sources.append(
            {
                **identity,
                "slices": [
                    {
                        "ordinal": 0,
                        "start": 0,
                        "end": len(source_bytes),
                        "sha256": _sha256(source_bytes),
                        "destination": _vault_relative(archive_path, registry.vault_root),
                    }
                ],
            }
        )
    layout = json.loads(_read_text(DEFAULT_CORE_MOC_LAYOUT))
    declared_documents = {str(item["source_name"]): item for item in layout["documents"]}
    if set(declared_documents) != {item[0] for item in documents}:
        raise ValueError("Core MOC layout does not declare exactly the four canonical documents")
    for name, child_dir in documents:
        document = declared_documents[name]
        if str(document["child_dir"]) != child_dir:
            raise ValueError(f"Core MOC child directory mismatch for {name}")
        declared_titles = {
            str(child[0])
            for group in document["groups"]
            for child in group["children"]
        }
        source_titles = {title for source_name, title in source_sections if source_name == name}
        if declared_titles != source_titles:
            missing = sorted(source_titles - declared_titles)
            unknown = sorted(declared_titles - source_titles)
            raise ValueError(f"Core MOC coverage mismatch for {name}: missing={missing}, unknown={unknown}")
        root_path = registry.vault_root / "00_Canonical" / name
        changes[root_path] = _render_declared_moc(
            source_prefixes[name],
            groups=document["groups"],
            child_dir=child_dir,
        )
    for nested_layout in layout["nested_maps"]:
        name = str(nested_layout["source_name"])
        parent_title = str(nested_layout["parent_title"])
        payload = source_sections[(name, parent_title)]
        prelude, subsections = _heading_sections(payload, level=3)
        source_subtitles = {title for title, _ in subsections}
        declared_subtitles = {str(child[0]) for child in nested_layout["children"]}
        if declared_subtitles != source_subtitles:
            missing = sorted(source_subtitles - declared_subtitles)
            unknown = sorted(declared_subtitles - source_subtitles)
            raise ValueError(
                f"Nested MOC coverage mismatch for {name}:{parent_title}: "
                f"missing={missing}, unknown={unknown}"
            )
        child_dir = str(declared_documents[name]["child_dir"])
        parent_path = (
            registry.vault_root
            / "00_Canonical"
            / child_dir
            / f"{_section_filename(parent_title)}.md"
        )
        nested_child_dir = f"{child_dir}/{_section_filename(parent_title)}"
        nested_group = {
            "heading": "Narrative Sequence",
            "narrative": str(nested_layout["intro"]),
            "children": nested_layout["children"],
        }
        changes[parent_path] = _render_declared_moc(
            _promote_first_heading(prelude, from_level=2),
            groups=[nested_group],
            child_dir=nested_child_dir,
        )
    canonical_outputs = [
        {
            "path": _vault_relative(path, registry.vault_root),
            "sha256": _sha256(text.encode("utf-8")),
        }
        for path, text in changes.items()
        if "00_Canonical" in path.parts
    ]
    manifest = {
        "schema_version": "vault_migration_manifest_v1",
        "migration_id": migration_id,
        "source_ref": source_ref,
        "sources": manifest_sources,
        "canonical_outputs": sorted(canonical_outputs, key=lambda item: str(item["path"])),
    }
    manifest_path = registry.vault_root / "90_Archive" / "Generated" / "vault_migrations" / f"{migration_id}.json"
    changes[manifest_path] = json.dumps(manifest, indent=2, ensure_ascii=True) + "\n"
    return changes, manifest


def cmd_check(args: argparse.Namespace) -> int:
    """Validate selected vault scopes and print human-readable diagnostics."""

    registry = load_registry(args.registry)
    scopes = _selected_scopes(registry, args.scope)
    if args.enforced_only:
        scopes = tuple(scope for scope in scopes if scope.rollout_state == "enforced")
    diagnostics = collect_diagnostics(registry, scopes, require_navigation=True)
    _print_diagnostics(diagnostics)
    return 1 if any(item.severity == "error" for item in diagnostics) else 0


def cmd_report(args: argparse.Namespace) -> int:
    """Print a read-only JSON report for selected vault scopes."""

    registry = load_registry(args.registry)
    scopes = _selected_scopes(registry, args.scope)
    report: list[dict[str, object]] = []
    for scope in scopes:
        diagnostics = _effective_diagnostics(
            scope,
            validate_scope(registry, scope, require_navigation=True),
        )
        report.append(
            {
                "scope_id": scope.scope_id,
                "owner": scope.owner,
                "rollout_state": scope.rollout_state,
                "errors": sum(item.severity == "error" for item in diagnostics),
                "warnings": sum(item.severity == "warning" for item in diagnostics),
                "diagnostics": [item.__dict__ for item in diagnostics],
            }
        )
    print(json.dumps({"schema_version": "vault_report_v1", "scopes": report}, indent=2))
    return 0


def cmd_sync_navigation(args: argparse.Namespace) -> int:
    """Preview or atomically apply deterministic breadcrumb navigation."""

    registry = load_registry(args.registry)
    scopes = _selected_scopes(registry, args.scope)
    changes = navigation_changes(registry, scopes)
    print(f"Navigation changes: {len(changes)}")
    for path in changes:
        print(_vault_relative(path, registry.vault_root))
    if args.apply and changes:
        _write_transaction(changes)
        if navigation_changes(registry, scopes):
            raise RuntimeError("navigation synchronization was not byte-idempotent")
    return 0


def cmd_migrate_a2a(args: argparse.Namespace) -> int:
    """Preview or apply a verified source-preserving A2A migration."""

    registry = load_registry(args.registry)
    changes, manifest, cleanup = build_a2a_migration(args.source_ref, registry)
    print(f"Migration: {manifest['migration_id']}")
    print(f"Files to write: {len(changes)}")
    print(f"Failed split directories to remove after verification: {len(cleanup)}")
    if not args.apply:
        return 0
    _write_transaction(changes)
    _verify_migrated_manifest(manifest, registry.vault_root)
    for path in cleanup:
        shutil.rmtree(path)
    print("A2A migration verified and applied.")
    return 0


def cmd_migrate_core(args: argparse.Namespace) -> int:
    """Preview or apply canonical source recovery into declared MOC children."""

    registry = load_registry(args.registry)
    changes, manifest = build_core_source_migration(args.source_ref, registry)
    print(f"Migration: {manifest['migration_id']}")
    print(f"Files to write: {len(changes)}")
    if not args.apply:
        return 0
    _write_transaction(changes)
    _verify_migrated_manifest(manifest, registry.vault_root)
    print("Core source recovery and section regeneration verified and applied.")
    return 0


def cmd_restore(args: argparse.Namespace) -> int:
    """Verify and optionally restore exact source bytes from a migration manifest."""

    manifest = json.loads(_read_text(args.manifest))
    registry = load_registry(args.registry)
    _verify_migrated_manifest(manifest, registry.vault_root)
    outputs: dict[Path, bytes] = {}
    for source in manifest["sources"]:
        payloads = []
        for slice_info in sorted(source["slices"], key=lambda item: item["ordinal"]):
            text = _read_text(registry.vault_root / slice_info["destination"])
            payloads.append(extract_source_payload(text))
        relative = Path(source["path"])
        if relative.parts and relative.parts[0] == registry.vault_root.name:
            relative = Path(*relative.parts[1:])
        outputs[args.output_dir / relative] = b"".join(payloads)
    for path, data in outputs.items():
        print(f"{path}: {len(data)} bytes sha256={_sha256(data)}")
    if args.apply:
        for path, data in outputs.items():
            _mkdir(path.parent)
            _write_bytes(path, data)
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Build the vault-maintenance command-line parser."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY)
    subparsers = parser.add_subparsers(dest="command", required=True)

    def add_scope_options(command: argparse.ArgumentParser) -> None:
        command.add_argument("--scope", action="append", default=[])

    check = subparsers.add_parser("check", help="Validate managed MOCs and navigation.")
    add_scope_options(check)
    check.add_argument("--enforced-only", action="store_true")
    check.set_defaults(func=cmd_check)

    report = subparsers.add_parser("report", help="Print a read-only JSON inventory.")
    add_scope_options(report)
    report.set_defaults(func=cmd_report)

    sync = subparsers.add_parser("sync-navigation", help="Synchronize generated breadcrumb blocks.")
    add_scope_options(sync)
    sync.add_argument("--apply", action="store_true")
    sync.set_defaults(func=cmd_sync_navigation)

    migrate = subparsers.add_parser("migrate-a2a", help="Losslessly migrate damaged A2A monoliths.")
    migrate.add_argument("--source-ref", default="2ec9a0ad")
    migrate.add_argument("--apply", action="store_true")
    migrate.set_defaults(func=cmd_migrate_a2a)

    migrate_core = subparsers.add_parser(
        "migrate-core",
        help="Recover Core source blobs and regenerate canonical section files.",
    )
    migrate_core.add_argument("--source-ref", default="2ec9a0ad")
    migrate_core.add_argument("--apply", action="store_true")
    migrate_core.set_defaults(func=cmd_migrate_core)

    restore = subparsers.add_parser("restore", help="Reconstruct original documents from a migration manifest.")
    restore.add_argument("--manifest", type=Path, required=True)
    restore.add_argument("--output-dir", type=Path, required=True)
    restore.add_argument("--apply", action="store_true")
    restore.set_defaults(func=cmd_restore)
    return parser


def main(argv: list[str] | None = None) -> int:
    """Run the requested vault maintenance command."""

    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
