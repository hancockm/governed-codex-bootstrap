"""external critique hook helper that surfaces the latest agent-to-agent critique updates.

The script is intentionally read-only. external critique CLI can run it as a BeforeAgent
hook and append the returned ``additionalContext`` to the next model request.
"""

from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
UPDATE_LOG = (
    ROOT
    / "Project_Obsidian_Vault"
    / "40_Coordination"
    / "Critique Update Log.md"
)
MOC_START = "<!-- managed:moc-children:start -->"
MOC_END = "<!-- managed:moc-children:end -->"


def main() -> int:
    """Print hook JSON for external critique CLI."""

    if not UPDATE_LOG.exists():
        print(json.dumps({}))
        return 0

    records = _resolve_indexed_records(UPDATE_LOG)
    if records:
        tail = _recent_record_context(records, max_chars=5000)
    else:
        text = UPDATE_LOG.read_text(encoding="utf-8")
        tail = _tail_update_entries(text, max_chars=5000)
    context = (
        "Latest project agent-to-agent critique update log context follows. "
        "Use it to detect Codex handoffs before implementation critique work.\n\n"
        f"{tail}"
    )
    print(json.dumps({"hookSpecificOutput": {"additionalContext": context}}))
    return 0


def _resolve_indexed_records(root_moc: Path) -> list[Path]:
    """Resolve atomic records reachable through managed child blocks."""

    vault_root = root_moc.parents[2]
    pending = [root_moc]
    visited: set[Path] = set()
    records: list[Path] = []
    while pending:
        current = pending.pop()
        if current in visited or not current.exists():
            continue
        visited.add(current)
        text = current.read_text(encoding="utf-8")
        if "schema_version: a2a_update_record_v1" in text:
            records.append(current)
            continue
        for target in _managed_targets(text):
            child = vault_root / f"{target}.md"
            pending.append(child)
    return sorted(records, key=lambda path: path.name)


def _managed_targets(text: str) -> list[str]:
    targets: list[str] = []
    pattern = re.compile(
        rf"{re.escape(MOC_START)}\n(?P<body>.*?){re.escape(MOC_END)}",
        re.DOTALL,
    )
    for block in pattern.finditer(text):
        targets.extend(
            match.group(1)
            for match in re.finditer(r"^- \[\[([^]|]+)(?:\|[^]]+)?\]\] - .+$", block.group("body"), re.MULTILINE)
        )
    return targets


def _recent_record_context(records: list[Path], *, max_chars: int) -> str:
    selected: list[str] = []
    size = 0
    for path in reversed(records):
        text = path.read_text(encoding="utf-8").strip()
        addition = len(text) + 2
        if selected and size + addition > max_chars:
            break
        selected.append(text if addition <= max_chars else text[-max_chars:])
        size += addition
    return "\n\n".join(reversed(selected))


def _tail_update_entries(text: str, *, max_chars: int) -> str:
    """Return a compact tail of the update log without splitting tiny logs."""

    if len(text) <= max_chars:
        return text
    marker = "\n### "
    start = text.rfind(marker, 0, len(text) - max_chars)
    if start == -1:
        return text[-max_chars:]
    return text[start + 1 :]


if __name__ == "__main__":
    raise SystemExit(main())
