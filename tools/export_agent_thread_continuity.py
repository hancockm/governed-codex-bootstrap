"""Export user-visible Codex messages into an agent continuity archive.

The exporter retains byte-exact JSONL source records for user and assistant
messages unless a credential must be redacted. It excludes reasoning, tool
calls, tool outputs, and hidden runtime instructions, and creates display-safe
Markdown projections without treating the transcript as canonical doctrine.
One Codex thread may belong to only one agent continuity archive.
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import os
import re
import shutil
import tempfile
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, Sequence


SCHEMA_VERSION = "agent_thread_continuity_manifest_v1"
TRANSCRIPT_SCHEMA_VERSION = "agent_visible_chat_transcript_v1"
MOC_START = "<!-- managed:moc-children:start -->"
MOC_END = "<!-- managed:moc-children:end -->"
VISIBLE_ROLES = frozenset({"user", "assistant"})
TEXT_CONTENT_TYPES = frozenset({"input_text", "output_text"})
SECRET_PATTERNS = (
    re.compile(r"(?<![A-Za-z0-9])(?:sk|oat)-[A-Za-z0-9_-]{20,}"),
    re.compile(r"(?<![A-Za-z0-9])gh[pousr]_[A-Za-z0-9]{20,}"),
    re.compile(r"(?<![A-Za-z0-9])github_pat_[A-Za-z0-9_]{20,}"),
    re.compile(r"(?<![A-Z0-9])AKIA[A-Z0-9]{16}(?![A-Z0-9])"),
    re.compile(r"(?i)Bearer\s+[A-Za-z0-9._~+/=-]{20,}"),
    re.compile(
        r"-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY-----.*?"
        r"-----END (?:[A-Z ]+ )?PRIVATE KEY-----",
        re.DOTALL,
    ),
)


@dataclass(frozen=True)
class VisibleMessage:
    """One exact user-visible response-item message."""

    ordinal: int
    timestamp: str
    role: str
    phase: str
    content_types: tuple[str, ...]
    text_parts: tuple[str, ...]
    raw_line: bytes
    source_raw_sha256: str
    credential_redaction_count: int

    @property
    def month(self) -> str:
        """Return the ISO year-month used for chronological grouping."""

        return self.timestamp[:7] if len(self.timestamp) >= 7 else "undated"

    @property
    def raw_sha256(self) -> str:
        """Return the hash of the archived, potentially redacted record."""

        return hashlib.sha256(self.raw_line).hexdigest()

    @property
    def text(self) -> str:
        """Return text parts in their declared order without normalization."""

        return "".join(self.text_parts)

    @property
    def text_sha256(self) -> str:
        """Return the hash of the exact concatenated visible text."""

        return hashlib.sha256(self.text.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ExportSnapshot:
    """A bounded source prefix and its selected visible messages."""

    source_observed_bytes: int
    source_prefix_bytes: int
    source_prefix_sha256: str
    source_record_count: int
    source_record_type_counts: Mapping[str, int]
    messages: tuple[VisibleMessage, ...]


def _redact_text(value: str) -> tuple[str, int]:
    redacted = value
    count = 0
    for pattern in SECRET_PATTERNS:
        redacted, replacements = pattern.subn("[REDACTED_CREDENTIAL]", redacted)
        count += replacements
    return redacted, count


def _redact_value(value: object) -> tuple[object, int]:
    if isinstance(value, str):
        return _redact_text(value)
    if isinstance(value, list):
        redacted_items: list[object] = []
        count = 0
        for item in value:
            redacted_item, item_count = _redact_value(item)
            redacted_items.append(redacted_item)
            count += item_count
        return redacted_items, count
    if isinstance(value, dict):
        redacted_mapping: dict[str, object] = {}
        count = 0
        for key, item in value.items():
            redacted_item, item_count = _redact_value(item)
            redacted_mapping[str(key)] = redacted_item
            count += item_count
        return redacted_mapping, count
    return value, 0


def _archive_record(record: Mapping[str, object], raw_line: bytes) -> tuple[Mapping[str, object], bytes, int]:
    redacted, count = _redact_value(dict(record))
    if not isinstance(redacted, Mapping):
        raise ValueError("redacted continuity record is not an object")
    if count == 0:
        return redacted, raw_line, 0
    archived_line = (json.dumps(redacted, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")
    return redacted, archived_line, count


def _record_type(record: Mapping[str, object]) -> str:
    outer = str(record.get("type", "unknown"))
    payload = record.get("payload")
    if isinstance(payload, Mapping) and payload.get("type"):
        return f"{outer}:{payload['type']}"
    return outer


def _continuity_source_root(output_dir: Path) -> Path | None:
    """Return the containing vault/test root for an owner transcript path."""

    if output_dir.parent.name != "Transcripts":
        return None
    for ancestor in output_dir.parents:
        if ancestor.name == "Project_Obsidian_Vault":
            return ancestor
    for ancestor in output_dir.parents:
        if re.fullmatch(r"\d{2}_.+", ancestor.name):
            return ancestor.parent
    return None


def ensure_unique_thread_archive(output_dir: Path, thread_id: str) -> None:
    """Reject a thread already assigned to another agent continuity pack.

    The check is automatically scoped to the containing project vault. Owner
    packs may use any registered vault location, but their archive directory
    must be named ``Transcripts``. Re-exporting the owning archive is allowed;
    mirroring the same thread into a second owner pack is not.

    Args:
        output_dir: Proposed transcript archive directory.
        thread_id: Stable Codex thread identifier.

    Raises:
        ValueError: If another agent continuity pack already contains the
            thread ID.
    """

    continuity_root = _continuity_source_root(output_dir)
    if continuity_root is None or not continuity_root.is_dir():
        return

    proposed = os.path.normcase(str(output_dir.resolve()))
    for transcripts_dir in continuity_root.rglob("Transcripts"):
        if not transcripts_dir.is_dir():
            continue
        for candidate in transcripts_dir.iterdir():
            if not candidate.is_dir() or os.path.normcase(str(candidate.resolve())) == proposed:
                continue

            archived_thread_id = candidate.name
            manifest_path = candidate / "manifest.json"
            if manifest_path.is_file():
                try:
                    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                except (OSError, UnicodeDecodeError, json.JSONDecodeError):
                    manifest = None
                if isinstance(manifest, Mapping) and isinstance(manifest.get("thread_id"), str):
                    archived_thread_id = manifest["thread_id"]

            if candidate.name == thread_id or archived_thread_id == thread_id:
                raise ValueError(
                    f"thread {thread_id!r} already belongs to another agent continuity archive: {candidate}"
                )


def read_visible_snapshot(source: Path) -> ExportSnapshot:
    """Read a stable full-line prefix and select visible messages.

    The source may still be active. The initial byte count is used as a hard
    upper bound, and a partial final line is never admitted.

    Args:
        source: Codex session JSONL path.

    Returns:
        The bounded source snapshot and exact selected message records.

    Raises:
        ValueError: If a complete source line is malformed or has an invalid
            message shape.
    """

    observed_bytes = source.stat().st_size
    prefix_hasher = hashlib.sha256()
    type_counts: Counter[str] = Counter()
    messages: list[VisibleMessage] = []
    consumed = 0
    source_records = 0

    with source.open("rb") as handle:
        for line_number, raw_line in enumerate(handle, 1):
            if consumed + len(raw_line) > observed_bytes:
                break
            if not raw_line.endswith(b"\n"):
                break
            consumed += len(raw_line)
            prefix_hasher.update(raw_line)
            source_records += 1
            try:
                record = json.loads(raw_line)
            except (UnicodeDecodeError, json.JSONDecodeError) as exc:
                raise ValueError(f"invalid JSONL record at line {line_number}") from exc
            if not isinstance(record, Mapping):
                raise ValueError(f"non-object JSONL record at line {line_number}")
            type_counts[_record_type(record)] += 1

            if record.get("type") != "response_item":
                continue
            payload = record.get("payload")
            if not isinstance(payload, Mapping) or payload.get("type") != "message":
                continue
            role = str(payload.get("role", ""))
            if role not in VISIBLE_ROLES:
                continue
            archived_record, archived_line, redaction_count = _archive_record(record, raw_line)
            archived_payload = archived_record.get("payload")
            if not isinstance(archived_payload, Mapping):
                raise ValueError(f"invalid archived message payload at line {line_number}")
            content = archived_payload.get("content", ())
            if not isinstance(content, Sequence) or isinstance(content, (str, bytes)):
                raise ValueError(f"invalid message content at line {line_number}")
            content_types: list[str] = []
            text_parts: list[str] = []
            for item in content:
                if not isinstance(item, Mapping):
                    raise ValueError(f"invalid content item at line {line_number}")
                item_type = str(item.get("type", "unknown"))
                content_types.append(item_type)
                if item_type in TEXT_CONTENT_TYPES:
                    text = item.get("text", "")
                    if not isinstance(text, str):
                        raise ValueError(f"invalid text content at line {line_number}")
                    text_parts.append(text)
            messages.append(
                VisibleMessage(
                    ordinal=len(messages) + 1,
                    timestamp=str(record.get("timestamp", "unknown")),
                    role=role,
                    phase=str(archived_payload.get("phase", "none")),
                    content_types=tuple(content_types),
                    text_parts=tuple(text_parts),
                    raw_line=archived_line,
                    source_raw_sha256=hashlib.sha256(raw_line).hexdigest(),
                    credential_redaction_count=redaction_count,
                )
            )

    return ExportSnapshot(
        source_observed_bytes=observed_bytes,
        source_prefix_bytes=consumed,
        source_prefix_sha256=prefix_hasher.hexdigest(),
        source_record_count=source_records,
        source_record_type_counts=dict(sorted(type_counts.items())),
        messages=tuple(messages),
    )


def _message_lines(message: VisibleMessage) -> int:
    return max(1, message.text.count("\n") + 1) + 12


def _chunk_messages(
    messages: Sequence[VisibleMessage],
    *,
    max_rendered_lines: int,
) -> tuple[tuple[VisibleMessage, ...], ...]:
    chunks: list[tuple[VisibleMessage, ...]] = []
    current: list[VisibleMessage] = []
    current_lines = 12
    for message in messages:
        message_lines = _message_lines(message)
        if current and current_lines + message_lines > max_rendered_lines:
            chunks.append(tuple(current))
            current = []
            current_lines = 12
        current.append(message)
        current_lines += message_lines
    if current:
        chunks.append(tuple(current))
    return tuple(chunks)


def _escape_preformatted_text(value: str) -> str:
    """Escape visible text and encode end-of-line whitespace for clean diffs."""

    escaped = html.escape(value, quote=False)

    def replace(match: re.Match[str]) -> str:
        return "".join("&#9;" if character == "\t" else "&#32;" for character in match.group())

    return re.sub(r"[ \t]+(?=\r?$)", replace, escaped, flags=re.MULTILINE)


def _render_message(message: VisibleMessage) -> str:
    label = "User" if message.role == "user" else "Assistant"
    phase = f"; phase={message.phase}" if message.phase != "none" else ""
    content_types = ", ".join(message.content_types) or "none"
    text = _escape_preformatted_text(message.text)
    if not message.text:
        text = "[No text content. Exact non-text message envelope is retained in visible_messages.jsonl.]"
    metadata = [f"`source_record_sha256={message.source_raw_sha256}`"]
    if message.source_raw_sha256 != message.raw_sha256:
        metadata.append(f"`archived_record_sha256={message.raw_sha256}`")
    if message.credential_redaction_count:
        metadata.append(f"`credential_redactions={message.credential_redaction_count}`")
    metadata.extend(
        [
            f"`text_sha256={message.text_sha256}`",
            f"`content_types={content_types}{phase}`",
        ]
    )
    return (
        f"## {message.ordinal:05d} {label} - {message.timestamp}\n\n"
        f"{'  '.join(metadata)}\n\n"
        "<details>\n"
        f"<summary>{label} message</summary>\n\n"
        f"<pre>{text}</pre>\n\n"
        "</details>\n"
    )


def _render_chunk(
    *,
    thread_id: str,
    month: str,
    part: int,
    messages: Sequence[VisibleMessage],
    manifest_target: str,
    agent_label: str,
    transcript_schema_version: str,
) -> str:
    first = messages[0]
    last = messages[-1]
    body = "\n".join(_render_message(message) for message in messages)
    return (
        "---\n"
        f"schema_version: {transcript_schema_version}\n"
        f"thread_id: {thread_id}\n"
        f"month: {month}\n"
        f"part: {part}\n"
        f"first_message_ordinal: {first.ordinal}\n"
        f"last_message_ordinal: {last.ordinal}\n"
        "authority: source_only\n"
        "---\n\n"
        f"# {agent_label} Visible Chat Transcript - {month} Part {part:03d}\n\n"
        "This generated projection contains user-visible messages only. It is source history, "
        "not canonical doctrine. Sanitized selected JSONL records and export policy are bound by "
        f"[[{manifest_target}|the continuity manifest]].\n\n"
        f"Messages `{first.ordinal}` through `{last.ordinal}` are shown chronologically.\n\n"
        f"{body}"
    )


def _render_month_moc(month: str, children: Sequence[tuple[str, str]], *, agent_label: str) -> str:
    lines = [
        f"# {month} {agent_label} Visible Chat Transcript",
        "",
        "This chronological map indexes generated, display-safe projections of exact visible-message records.",
        "",
        MOC_START,
    ]
    for target, label in children:
        lines.append(
            f"- [[{target}|{label}]] - Preserves the next chronological group of visible {agent_label} messages."
        )
    lines.extend([MOC_END, ""])
    return "\n".join(lines)


def _render_transcript_moc(
    *,
    thread_id: str,
    snapshot: ExportSnapshot,
    month_targets: Sequence[tuple[str, str]],
    agent_label: str,
) -> str:
    lines = [
        f"# {agent_label} Visible Chat Transcript",
        "",
        f"This source map preserves the user-visible history of the long-running {agent_label} task.",
        "Private reasoning, tool payloads, encrypted content, and hidden instructions are deliberately excluded; detected credentials are redacted.",
        "",
        "## Snapshot",
        "",
        f"- Thread: `{thread_id}`",
        f"- Source prefix bytes: `{snapshot.source_prefix_bytes}`",
        f"- Source prefix SHA-256: `{snapshot.source_prefix_sha256}`",
        f"- Visible messages: `{len(snapshot.messages)}`",
        "- Authority: source history only",
        "",
        "## Chronological Archive",
        "",
        MOC_START,
    ]
    for target, month in month_targets:
        lines.append(f"- [[{target}|{month} transcript]] - Indexes visible {agent_label} messages recorded during {month}.")
    lines.extend([MOC_END, ""])
    return "\n".join(lines)


def build_export_files(
    *,
    snapshot: ExportSnapshot,
    thread_id: str,
    vault_target: str,
    max_rendered_lines: int,
    manifest_schema_version: str = SCHEMA_VERSION,
    transcript_schema_version: str = TRANSCRIPT_SCHEMA_VERSION,
    agent_label: str = "Project Agent",
) -> dict[str, bytes]:
    """Build all deterministic files for one continuity snapshot.

    Args:
        snapshot: Bounded source snapshot.
        thread_id: Stable Codex thread identifier.
        vault_target: Vault-relative output directory without a trailing slash.
        max_rendered_lines: Soft per-transcript-part line budget.
        manifest_schema_version: Schema version stamped into the manifest.
        transcript_schema_version: Schema version stamped into Markdown parts.
        agent_label: Human-readable agent name used in generated headings.

    Returns:
        Relative output paths mapped to exact bytes.
    """

    files: dict[str, bytes] = {}
    by_month: dict[str, list[VisibleMessage]] = defaultdict(list)
    for message in snapshot.messages:
        by_month[message.month].append(message)

    month_targets: list[tuple[str, str]] = []
    manifest_target = f"{vault_target}/manifest.json"
    for month in sorted(by_month):
        month_target = f"{vault_target}/{month}/README"
        month_targets.append((month_target, month))
        children: list[tuple[str, str]] = []
        chunks = _chunk_messages(by_month[month], max_rendered_lines=max_rendered_lines)
        for part, messages in enumerate(chunks, 1):
            digest = hashlib.sha256(b"".join(item.raw_line for item in messages)).hexdigest()[:12]
            filename = f"part-{part:03d}-{digest}.md"
            relative = f"{month}/{filename}"
            target = f"{vault_target}/{month}/{filename[:-3]}"
            children.append((target, f"Part {part:03d}"))
            files[relative] = _render_chunk(
                thread_id=thread_id,
                month=month,
                part=part,
                messages=messages,
                manifest_target=manifest_target,
                agent_label=agent_label,
                transcript_schema_version=transcript_schema_version,
            ).encode("utf-8")
        files[f"{month}/README.md"] = _render_month_moc(month, children, agent_label=agent_label).encode("utf-8")

    files["README.md"] = _render_transcript_moc(
        thread_id=thread_id,
        snapshot=snapshot,
        month_targets=month_targets,
        agent_label=agent_label,
    ).encode("utf-8")
    selected_bytes = b"".join(message.raw_line for message in snapshot.messages)
    files["visible_messages.jsonl"] = selected_bytes

    role_counts = Counter(message.role for message in snapshot.messages)
    phase_counts = Counter(message.phase for message in snapshot.messages)
    redacted_messages = sum(bool(message.credential_redaction_count) for message in snapshot.messages)
    credential_redactions = sum(message.credential_redaction_count for message in snapshot.messages)
    output_inventory = [
        {
            "path": path,
            "bytes": len(payload),
            "sha256": hashlib.sha256(payload).hexdigest(),
        }
        for path, payload in sorted(files.items())
    ]
    manifest = {
        "schema_version": manifest_schema_version,
        "agent_label": agent_label,
        "thread_id": thread_id,
        "source_locator": f"codex_session:{thread_id}",
        "source_observed_bytes": snapshot.source_observed_bytes,
        "source_prefix_bytes": snapshot.source_prefix_bytes,
        "source_prefix_sha256": snapshot.source_prefix_sha256,
        "source_record_count": snapshot.source_record_count,
        "source_record_type_counts": snapshot.source_record_type_counts,
        "selection_policy": {
            "included": "response_item message records with role user or assistant; detected credentials are redacted",
            "excluded": [
                "session metadata and hidden instructions",
                "reasoning and encrypted reasoning",
                "tool calls and tool outputs",
                "event-message duplicates",
                "runtime and world-state records",
            ],
            "markdown_projection": "HTML-escaped visible text; sanitized selected JSONL records remain authoritative",
        },
        "credential_redaction_policy": {
            "pattern_profile": "common_credentials_v1",
            "replacement": "[REDACTED_CREDENTIAL]",
            "ordinary_records": "retained byte-exact when no credential pattern is detected",
            "redacted_records": "deterministically reserialized after credential replacement",
            "source_record_hash_retained": True,
        },
        "redacted_message_count": redacted_messages,
        "credential_redaction_count": credential_redactions,
        "visible_message_count": len(snapshot.messages),
        "role_counts": dict(sorted(role_counts.items())),
        "phase_counts": dict(sorted(phase_counts.items())),
        "first_message_timestamp": snapshot.messages[0].timestamp if snapshot.messages else None,
        "last_message_timestamp": snapshot.messages[-1].timestamp if snapshot.messages else None,
        "selected_records_bytes": len(selected_bytes),
        "selected_records_sha256": hashlib.sha256(selected_bytes).hexdigest(),
        "output_files": output_inventory,
        "authority": "source_only",
    }
    files["manifest.json"] = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8")
    return files


def _tree_hashes(root: Path) -> dict[str, str]:
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _replace_with_retry(
    source: Path,
    destination: Path,
    *,
    attempts: int = 8,
    initial_delay_seconds: float = 0.1,
) -> None:
    """Atomically replace a path with bounded retries for Windows index locks."""

    for attempt in range(attempts):
        try:
            os.replace(source, destination)
            return
        except PermissionError:
            if attempt + 1 == attempts:
                raise
            time.sleep(initial_delay_seconds * (2**attempt))


def _output_inventory(root: Path) -> list[dict[str, object]]:
    """Return current hashes for all archive files except the manifest."""

    return [
        {
            "path": path.relative_to(root).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        }
        for path in sorted(root.rglob("*"))
        if path.is_file() and path.name != "manifest.json"
    ]


def refresh_manifest(
    output_dir: Path,
    *,
    apply: bool,
    expected_schema_version: str = SCHEMA_VERSION,
) -> tuple[bool, bytes]:
    """Refresh final archive hashes after managed navigation synchronization.

    Args:
        output_dir: Existing transcript export directory.
        apply: Whether to atomically replace the manifest.
        expected_schema_version: Manifest schema version that the existing
            archive must use.

    Returns:
        A pair containing the change status and proposed manifest bytes.

    Raises:
        ValueError: If the existing manifest is missing or malformed.
    """

    manifest_path = output_dir / "manifest.json"
    if not manifest_path.is_file():
        raise ValueError(f"continuity manifest does not exist: {manifest_path}")
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid continuity manifest: {manifest_path}") from exc
    if not isinstance(manifest, dict) or manifest.get("schema_version") != expected_schema_version:
        raise ValueError(f"unsupported continuity manifest: {manifest_path}")

    inventory = _output_inventory(output_dir)
    manifest["output_files"] = inventory
    manifest["output_inventory_state"] = "post_navigation"
    manifest["archive_file_count_excluding_manifest"] = len(inventory)
    manifest["archive_bytes_excluding_manifest"] = sum(int(item["bytes"]) for item in inventory)
    proposed = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8")
    changed = proposed != manifest_path.read_bytes()

    if apply and changed:
        descriptor, temporary_name = tempfile.mkstemp(prefix=".manifest-", dir=output_dir)
        temporary_path = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(proposed)
                handle.flush()
                os.fsync(handle.fileno())
            if hashlib.sha256(temporary_path.read_bytes()).digest() != hashlib.sha256(proposed).digest():
                raise RuntimeError("staged continuity manifest failed hash verification")
            _replace_with_retry(temporary_path, manifest_path)
        finally:
            if temporary_path.exists():
                temporary_path.unlink()
    return changed, proposed


def _restore_tree_in_place(output_dir: Path, backup: Path) -> None:
    """Restore an in-place transaction from its verified backup tree."""

    backup_files = {
        path.relative_to(backup).as_posix(): path
        for path in backup.rglob("*")
        if path.is_file()
    }
    for path in sorted(output_dir.rglob("*"), reverse=True):
        if path.is_file() and path.relative_to(output_dir).as_posix() not in backup_files:
            path.unlink()
    for relative, source in backup_files.items():
        destination = output_dir / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(prefix=".restore-", dir=destination.parent)
        temporary_path = Path(temporary_name)
        os.close(descriptor)
        try:
            shutil.copy2(source, temporary_path)
            _replace_with_retry(temporary_path, destination)
        finally:
            if temporary_path.exists():
                temporary_path.unlink()
    for path in sorted(output_dir.rglob("*"), reverse=True):
        if path.is_dir() and not any(path.iterdir()):
            path.rmdir()
    if _tree_hashes(output_dir) != _tree_hashes(backup):
        raise RuntimeError("continuity export rollback failed hash verification")


def _replace_tree_in_place(
    output_dir: Path,
    staged_tree: Path,
    backup: Path,
    expected: Mapping[str, str],
) -> None:
    """Apply a verified file transaction when Windows holds the directory open."""

    shutil.copytree(output_dir, backup)
    if _tree_hashes(output_dir) != _tree_hashes(backup):
        raise RuntimeError("continuity export backup failed hash verification")
    try:
        for relative in sorted(expected):
            source = staged_tree / relative
            destination = output_dir / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            _replace_with_retry(source, destination)
        for path in sorted(output_dir.rglob("*"), reverse=True):
            if path.is_file() and path.relative_to(output_dir).as_posix() not in expected:
                path.unlink()
        for path in sorted(output_dir.rglob("*"), reverse=True):
            if path.is_dir() and not any(path.iterdir()):
                path.rmdir()
        if _tree_hashes(output_dir) != dict(expected):
            raise RuntimeError("in-place continuity export failed hash verification")
    except Exception:
        _restore_tree_in_place(output_dir, backup)
        raise


def write_transaction(output_dir: Path, files: Mapping[str, bytes]) -> None:
    """Replace an export directory only after a complete staged write.

    Args:
        output_dir: Destination directory.
        files: Relative paths mapped to bytes.

    Raises:
        RuntimeError: If staged bytes fail verification.
    """

    output_dir.parent.mkdir(parents=True, exist_ok=True)
    temp_root = Path(tempfile.mkdtemp(prefix=f".{output_dir.name}-", dir=output_dir.parent))
    backup = output_dir.with_name(f".{output_dir.name}.backup")
    try:
        for relative, payload in files.items():
            destination = temp_root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(payload)
        expected = {path: hashlib.sha256(payload).hexdigest() for path, payload in files.items()}
        if _tree_hashes(temp_root) != expected:
            raise RuntimeError("staged continuity export failed hash verification")
        if backup.exists():
            shutil.rmtree(backup)
        if output_dir.exists():
            try:
                _replace_with_retry(output_dir, backup, attempts=3)
            except PermissionError:
                _replace_tree_in_place(output_dir, temp_root, backup, expected)
                shutil.rmtree(backup)
                shutil.rmtree(temp_root)
                return
        _replace_with_retry(temp_root, output_dir)
        if backup.exists():
            shutil.rmtree(backup)
    except Exception:
        if temp_root.exists():
            shutil.rmtree(temp_root)
        if backup.exists() and not output_dir.exists():
            _replace_with_retry(backup, output_dir)
        raise


def build_parser() -> argparse.ArgumentParser:
    """Build the command-line parser."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, help="Codex session JSONL path.")
    parser.add_argument("--thread-id", help="Stable Codex thread identifier.")
    parser.add_argument("--output-dir", type=Path, required=True, help="Transcript export directory.")
    parser.add_argument(
        "--vault-target",
        help="Vault-relative output target used in generated wikilinks.",
    )
    parser.add_argument("--max-rendered-lines", type=int, default=480)
    parser.add_argument(
        "--agent-label",
        default="Project Agent",
        help="Human-readable agent label for generated transcript headings.",
    )
    parser.add_argument(
        "--manifest-schema-version",
        default=SCHEMA_VERSION,
        help="Manifest schema version to stamp in the generated archive.",
    )
    parser.add_argument(
        "--transcript-schema-version",
        default=TRANSCRIPT_SCHEMA_VERSION,
        help="Markdown transcript schema version to stamp in generated parts.",
    )
    parser.add_argument(
        "--refresh-manifest",
        action="store_true",
        help="Refresh final output hashes after vault navigation synchronization.",
    )
    parser.add_argument("--apply", action="store_true", help="Write the verified export transaction.")
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    """Run a dry-run or verified continuity export."""

    parser = build_parser()
    args = parser.parse_args(argv)
    if args.refresh_manifest:
        changed, proposed = refresh_manifest(
            args.output_dir,
            apply=args.apply,
            expected_schema_version=args.manifest_schema_version,
        )
        print(
            json.dumps(
                {
                    "apply": args.apply,
                    "changed": changed,
                    "manifest_bytes": len(proposed),
                    "output_dir": str(args.output_dir),
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 0
    if args.source is None or args.thread_id is None or args.vault_target is None:
        parser.error("--source, --thread-id, and --vault-target are required for an export")
    ensure_unique_thread_archive(args.output_dir, args.thread_id)
    snapshot = read_visible_snapshot(args.source)
    files = build_export_files(
        snapshot=snapshot,
        thread_id=args.thread_id,
        vault_target=args.vault_target.rstrip("/"),
        max_rendered_lines=args.max_rendered_lines,
        manifest_schema_version=args.manifest_schema_version,
        transcript_schema_version=args.transcript_schema_version,
        agent_label=args.agent_label,
    )
    summary = {
        "source_prefix_bytes": snapshot.source_prefix_bytes,
        "source_prefix_sha256": snapshot.source_prefix_sha256,
        "visible_messages": len(snapshot.messages),
        "output_files": len(files),
        "output_bytes": sum(len(payload) for payload in files.values()),
        "apply": args.apply,
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    if args.apply:
        write_transaction(args.output_dir, files)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
