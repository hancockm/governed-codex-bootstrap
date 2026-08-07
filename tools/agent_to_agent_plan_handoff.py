"""Create immutable, advisory implementation-plan critique handoffs."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
DISCUSSION_DIR = ROOT / "Project_Obsidian_Vault" / "40_Coordination"
DEFAULT_ACTIVE_THREAD = DISCUSSION_DIR / "Generated" / "Active Records.md"
UPDATE_LOG = DISCUSSION_DIR / "Generated" / "Critique Update Log.md"
LOG_DIR = ROOT / "tmp" / "agent_handoff_logs"
MOC_START = "<!-- managed:moc-children:start -->"
MOC_END = "<!-- managed:moc-children:end -->"
PREAMBLE = (
    "Be critical of this input. You need to be analytical in your response.  "
    "Do not take this as the answer. Look at the weak points in the argument. "
    "Let's begin to list areas of common agreement. List areas of disagreement. "
    "The goal for each iteration is to reduce one disagreement. If each round, "
    "you eliminate one disagreement but add 2 disagreements you are going in the wrong direction.  "
    "We need to converge on a plan. List ALL remaining disagreements. "
    "Don't keep adding them after each round."
)
REQUIRED_HEADINGS = (
    "## Common Agreement",
    "## All Remaining Disagreements",
    "## Critical Weak Points",
    "## Convergence Move",
    "## Decision Status",
)


class HandoffError(RuntimeError):
    """Raised when a handoff cannot be built or published safely."""


def baseline(root: Path = ROOT) -> str:
    """Return the current commit, or an explicit uncommitted-bootstrap marker."""

    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else "uncommitted-bootstrap"


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    """Parse local publication and optional external-critique arguments."""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--topic", required=True)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--plan-file", type=Path)
    source.add_argument("--plan-text")
    parser.add_argument("--owner", default="core")
    parser.add_argument("--thread", type=Path, default=DEFAULT_ACTIVE_THREAD)
    parser.add_argument("--disagreement", default="")
    parser.add_argument("--critique-file", type=Path)
    parser.add_argument("--invoke", choices=("agy", "mmx", "codex"))
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--dry-run", action="store_true")
    return parser.parse_args(argv)


def _read_plan(args: argparse.Namespace) -> str:
    """Read exactly one supplied plan and reject an empty value."""

    text = args.plan_file.read_text(encoding="utf-8") if args.plan_file else args.plan_text
    if not isinstance(text, str) or not text.strip():
        raise HandoffError("plan text cannot be empty")
    return text.replace("\r\n", "\n").replace("\r", "\n")


def build_critique_prompt(
    *, topic: str, plan_text: str, thread_path: Path, disagreement: str = ""
) -> str:
    """Build the provider-neutral critique prompt for one immutable record."""

    return (
        f"{PREAMBLE}\n\n"
        f"Topic: {topic}\n"
        f"Target record: {_display_path(thread_path)}\n"
        f"Current disagreement: {disagreement or 'None supplied.'}\n\n"
        "Return Markdown using each heading exactly once:\n"
        + "\n".join(REQUIRED_HEADINGS)
        + f"\n\nProposed plan:\n\n{plan_text}"
    )


def _safe_slug(value: str) -> str:
    """Return a conservative lowercase path segment."""

    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return slug[:64] or "plan"


def _resolve_thread(path: Path) -> Path:
    """Resolve a thread inside the registered coordination vault only."""

    resolved = path.resolve() if path.is_absolute() else (ROOT / path).resolve()
    try:
        resolved.relative_to(DISCUSSION_DIR.resolve())
    except ValueError as exc:
        raise HandoffError("thread must remain inside Project_Obsidian_Vault/40_Coordination") from exc
    return resolved


def _record_identity(
    *, topic: str, owner: str, plan_text: str, frozen_baseline: str
) -> str:
    """Return a content address for the immutable handoff request."""

    payload = {
        "topic": topic,
        "owner": owner,
        "baseline": frozen_baseline,
        "plan_sha256": hashlib.sha256(plan_text.encode("utf-8")).hexdigest(),
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _resolve_record_path(
    *, active_thread: Path, topic: str, identity: str, created_at: datetime
) -> Path:
    """Return the monthly content-addressed record path."""

    if active_thread == DEFAULT_ACTIVE_THREAD.resolve():
        return (
            DISCUSSION_DIR
            / "Threads"
            / "Implementation Plan Critiques"
            / "Entries"
            / created_at.strftime("%Y-%m")
            / f"{_safe_slug(topic)}-{identity[:12]}.md"
        )
    return active_thread


def _valid_critique(markdown: str) -> bool:
    """Return whether captured critique Markdown has the required structure."""

    return PREAMBLE in markdown and all(markdown.count(heading) == 1 for heading in REQUIRED_HEADINGS)


def _redact_cli_text(text: str) -> str:
    """Redact common credential assignments from bounded CLI output."""

    value = text
    for pattern in (
        r"(?i)(api[_-]?key\s*[=:]\s*)\S+",
        r"(?i)(token\s*[=:]\s*)\S+",
        r"(?i)(password\s*[=:]\s*)\S+",
        r"(?i)(secret\s*[=:]\s*)\S+",
    ):
        value = re.sub(pattern, r"\1[REDACTED]", value)
    return value


def _invoke_external(provider: str, prompt: str, *, identity: str) -> str:
    """Invoke one explicitly configured critique CLI and return validated Markdown."""

    env_key = f"PROJECT_{provider.upper()}_COMMAND"
    configured = os.environ.get(env_key, "").strip()
    if not configured:
        raise HandoffError(f"{env_key} is required for --invoke {provider}")
    command = shlex.split(configured, posix=os.name != "nt")
    if not command:
        raise HandoffError(f"{env_key} resolved to an empty command")
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log = LOG_DIR / f"{provider}-{identity[:12]}.log"
    result = subprocess.run(
        command,
        input=prompt,
        text=True,
        capture_output=True,
        check=False,
        timeout=600,
        cwd=ROOT,
    )
    bounded = _redact_cli_text((result.stdout + "\n" + result.stderr)[-20000:])
    log.write_text(bounded, encoding="utf-8")
    if result.returncode != 0:
        raise HandoffError(f"{provider} critique command failed; inspect {_display_path(log)}")
    critique = result.stdout.strip()
    if not _valid_critique(critique):
        raise HandoffError(f"{provider} returned invalid critique Markdown")
    return critique


def _render_record(
    *, topic: str, owner: str, plan_text: str, identity: str,
    frozen_baseline: str, created_at: datetime, critique: str
) -> str:
    """Render the immutable handoff record and its explicit advisory state."""

    metadata = {
        "schema_version": "project_plan_handoff_v1",
        "authority": "advisory",
        "topic": topic,
        "owner": owner,
        "baseline": frozen_baseline,
        "created_utc": created_at.isoformat().replace("+00:00", "Z"),
        "identity_sha256": identity,
        "plan_sha256": hashlib.sha256(plan_text.encode("utf-8")).hexdigest(),
        "critique_sha256": hashlib.sha256(critique.encode("utf-8")).hexdigest() if critique else "",
        "status": "advisory_pending_owner_disposition",
    }
    pending = "\n\n".join(f"{heading}\n\nPending." for heading in REQUIRED_HEADINGS)
    return (
        f"{PREAMBLE}\n\n# Plan Handoff: {topic}\n\n"
        f"```json\n{json.dumps(metadata, indent=2, sort_keys=True)}\n```\n\n"
        f"## Requested Critique\n\n{pending}\n\n"
        f"## Proposed Plan\n\n{plan_text.rstrip()}\n\n"
        f"## Advisory Critique\n\n{critique or 'Not yet supplied.'}\n"
    )


def _managed_block(children: Iterable[tuple[str, str]]) -> str:
    """Render one deterministic managed-child block."""

    lines = [MOC_START]
    lines.extend(f"- [[{target}|{label}]] - indexed critique record" for target, label in sorted(children))
    lines.append(MOC_END)
    return "\n".join(lines)


def _upsert_index(index: Path, target: Path, label: str) -> str:
    """Return index text containing one path-qualified record link."""

    current = index.read_text(encoding="utf-8") if index.exists() else "# Active Implementation Plan Critiques\n\n"
    try:
        vault_root = DISCUSSION_DIR.parent
        target_ref = target.relative_to(vault_root).with_suffix("").as_posix()
    except ValueError as exc:
        raise HandoffError("record path is outside the vault") from exc
    pattern = re.compile(re.escape(MOC_START) + r"\n.*?\n" + re.escape(MOC_END), re.DOTALL)
    children: dict[str, str] = {}
    match = pattern.search(current)
    if match:
        for found in re.finditer(r"^- \[\[([^]|]+)\|([^]]+)\]\] - .+$", match.group(), re.MULTILINE):
            children[found.group(1)] = found.group(2)
    children[target_ref] = label
    replacement = _managed_block(children.items())
    if match:
        return current[:match.start()] + replacement + current[match.end():]
    return current.rstrip() + "\n\n" + replacement + "\n"


def _write_transaction(changes: dict[Path, str]) -> None:
    """Publish all text files with rollback on a failed replacement."""

    originals = {path: path.read_bytes() if path.exists() else None for path in changes}
    written: list[Path] = []
    try:
        for path, text in changes.items():
            path.parent.mkdir(parents=True, exist_ok=True)
            temp = path.with_name(f".{path.name}.handoff.tmp")
            temp.write_text(text, encoding="utf-8", newline="\n")
            temp.replace(path)
            written.append(path)
    except OSError:
        for path in reversed(written):
            original = originals[path]
            if original is None:
                path.unlink(missing_ok=True)
            else:
                path.write_bytes(original)
        raise


def _update_log_text(record_path: Path, *, topic: str, identity: str) -> str:
    """Return a compact update log with an idempotent record entry."""

    current = UPDATE_LOG.read_text(encoding="utf-8") if UPDATE_LOG.exists() else "# Critique Update Log\n\n"
    target = record_path.relative_to(DISCUSSION_DIR.parent).with_suffix("").as_posix()
    entry = f"- [[{target}|{topic}]] - `{identity}`"
    return current if entry in current else current.rstrip() + "\n" + entry + "\n"


def publish_handoff(
    *, record_path: Path, active_thread: Path, record_text: str,
    topic: str, identity: str
) -> bool:
    """Publish or idempotently confirm one immutable handoff and its indexes."""

    if record_path.exists():
        if record_path.read_text(encoding="utf-8") != record_text:
            raise HandoffError("content-addressed handoff exists with different content")
        return False
    changes = {
        record_path: record_text,
        active_thread: _upsert_index(active_thread, record_path, topic),
        UPDATE_LOG: _update_log_text(record_path, topic=topic, identity=identity),
    }
    _write_transaction(changes)
    return True


def _display_path(path: Path) -> str:
    """Return a repository-relative path when possible."""

    try:
        return path.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError:
        return str(path.resolve())


def main(argv: list[str] | None = None) -> int:
    """Build, optionally critique, and optionally publish one handoff."""

    try:
        args = parse_args(argv)
        plan = _read_plan(args)
        frozen_baseline = baseline()
        identity = _record_identity(
            topic=args.topic,
            owner=args.owner,
            plan_text=plan,
            frozen_baseline=frozen_baseline,
        )
        active_thread = _resolve_thread(args.thread)
        created_at = datetime.now(timezone.utc)
        record_path = _resolve_record_path(
            active_thread=active_thread,
            topic=args.topic,
            identity=identity,
            created_at=created_at,
        )
        if args.apply and record_path.exists() and not args.critique_file and not args.invoke:
            print(json.dumps({
                "schema_version": "project_plan_handoff_result_v1",
                "valid": True,
                "applied": False,
                "record": _display_path(record_path),
                "identity_sha256": identity,
                "status": "advisory_pending_owner_disposition",
                "canonical_promotion": "requires_owner_disposition",
            }, indent=2, sort_keys=True))
            return 0
        prompt = build_critique_prompt(
            topic=args.topic,
            plan_text=plan,
            thread_path=record_path,
            disagreement=args.disagreement,
        )
        if args.dry_run:
            print(prompt)
            return 0
        critique = ""
        if args.critique_file:
            critique = args.critique_file.read_text(encoding="utf-8")
            if not _valid_critique(critique):
                raise HandoffError("critique file does not use the required structure")
        if args.invoke:
            critique = _invoke_external(args.invoke, prompt, identity=identity)
        record = _render_record(
            topic=args.topic,
            owner=args.owner,
            plan_text=plan,
            identity=identity,
            frozen_baseline=frozen_baseline,
            created_at=created_at,
            critique=critique,
        )
        applied = publish_handoff(
            record_path=record_path,
            active_thread=active_thread,
            record_text=record,
            topic=args.topic,
            identity=identity,
        ) if args.apply else False
        print(json.dumps({
            "schema_version": "project_plan_handoff_result_v1",
            "valid": True,
            "applied": applied,
            "record": _display_path(record_path),
            "identity_sha256": identity,
            "status": "advisory_pending_owner_disposition",
            "canonical_promotion": "requires_owner_disposition",
        }, indent=2, sort_keys=True))
        return 0
    except (OSError, subprocess.SubprocessError, HandoffError) as exc:
        print(json.dumps({"valid": False, "error": str(exc)}, sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
