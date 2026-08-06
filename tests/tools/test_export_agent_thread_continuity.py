import hashlib
import json
import sys
from pathlib import Path

import pytest


TOOLS = Path(__file__).resolve().parents[2] / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import export_agent_thread_continuity as exporter  # noqa: E402


def test_complete_exporter_surface_remains_available() -> None:
    """Protect the complete continuity lifecycle from simplification."""

    required = {
        "VisibleMessage",
        "ExportSnapshot",
        "_redact_text",
        "_redact_value",
        "_archive_record",
        "_record_type",
        "_continuity_source_root",
        "ensure_unique_thread_archive",
        "read_visible_snapshot",
        "_message_lines",
        "_chunk_messages",
        "_escape_preformatted_text",
        "_render_message",
        "_render_chunk",
        "_render_month_moc",
        "_render_transcript_moc",
        "build_export_files",
        "_tree_hashes",
        "_replace_with_retry",
        "_output_inventory",
        "refresh_manifest",
        "_restore_tree_in_place",
        "_replace_tree_in_place",
        "write_transaction",
        "build_parser",
        "main",
    }
    assert not sorted(name for name in required if not hasattr(exporter, name))


def _line(timestamp: str, type_: str, payload: dict) -> bytes:
    return (
        json.dumps({"timestamp": timestamp, "type": type_, "payload": payload}, separators=(",", ":"))
        + "\n"
    ).encode("utf-8")


def test_export_preserves_visible_records_and_excludes_private_runtime_records(tmp_path):
    source = tmp_path / "thread.jsonl"
    session = _line(
        "2026-07-01T00:00:00Z",
        "session_meta",
        {"type": "session_meta", "base_instructions": {"text": "private instruction"}},
    )
    user = _line(
        "2026-07-01T00:00:01Z",
        "response_item",
        {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "# Question\n"}]},
    )
    reasoning = _line(
        "2026-07-01T00:00:02Z",
        "response_item",
        {"type": "reasoning", "encrypted_content": "private reasoning"},
    )
    duplicate_event = _line(
        "2026-07-01T00:00:03Z",
        "event_msg",
        {"type": "user_message", "message": "# Question\n"},
    )
    assistant = _line(
        "2026-07-01T00:00:04Z",
        "response_item",
        {
            "type": "message",
            "role": "assistant",
            "phase": "final_answer",
            "content": [{"type": "output_text", "text": "Answer with <!-- PROJECT_MOC_CHILDREN_V1:START -->."}],
        },
    )
    source.write_bytes(session + user + reasoning + duplicate_event + assistant)

    snapshot = exporter.read_visible_snapshot(source)
    files = exporter.build_export_files(
        snapshot=snapshot,
        thread_id="thread-1",
        vault_target="90_Sources/Core Agent Continuity/Transcripts/thread-1",
        max_rendered_lines=80,
    )

    assert len(snapshot.messages) == 2
    assert files["visible_messages.jsonl"] == user + assistant
    assert b"private instruction" not in files["visible_messages.jsonl"]
    assert b"private reasoning" not in files["visible_messages.jsonl"]
    transcript = next(payload for path, payload in files.items() if path.endswith(".md") and "part-" in path)
    assert b"&lt;!-- PROJECT_MOC_CHILDREN_V1:START --&gt;" in transcript
    assert b"<!-- PROJECT_MOC_CHILDREN_V1:START -->" not in transcript
    assert all(line.rstrip() == line for line in transcript.decode("utf-8").splitlines())

    manifest = json.loads(files["manifest.json"])
    assert manifest["selected_records_sha256"] == hashlib.sha256(user + assistant).hexdigest()
    assert manifest["role_counts"] == {"assistant": 1, "user": 1}


def test_default_export_language_and_schemas_are_agent_neutral(tmp_path):
    source = tmp_path / "thread.jsonl"
    source.write_bytes(
        _line(
            "2026-07-01T00:00:01Z",
            "response_item",
            {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "Question"}]},
        )
    )
    snapshot = exporter.read_visible_snapshot(source)

    files = exporter.build_export_files(
        snapshot=snapshot,
        thread_id="thread-1",
        vault_target="90_Sources/Example Agent Continuity/Transcripts/thread-1",
        max_rendered_lines=80,
    )

    month_index = files["2026-07/README.md"].decode("utf-8")
    manifest = json.loads(files["manifest.json"])
    transcript = next(payload for path, payload in files.items() if path.endswith(".md") and "part-" in path)
    assert "visible Project Agent messages" in month_index
    assert "visible Core messages" not in month_index
    assert manifest["agent_label"] == "Project Agent"
    assert manifest["schema_version"] == "agent_thread_continuity_manifest_v1"
    assert b"schema_version: agent_visible_chat_transcript_v1" in transcript


def test_write_transaction_is_byte_idempotent(tmp_path):
    output = tmp_path / "export"
    files = {"README.md": b"# Index\n", "2026-07/part.md": b"# Part\n"}

    exporter.write_transaction(output, files)
    first = exporter._tree_hashes(output)
    exporter.write_transaction(output, files)

    assert exporter._tree_hashes(output) == first


def test_cli_is_dry_run_by_default(tmp_path):
    source = tmp_path / "thread.jsonl"
    source.write_bytes(
        _line(
            "2026-07-01T00:00:01Z",
            "response_item",
            {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "Question"}]},
        )
    )
    output = tmp_path / "export"

    result = exporter.main(
        [
            "--source",
            str(source),
            "--thread-id",
            "thread-1",
            "--output-dir",
            str(output),
            "--vault-target",
            "90_Sources/Core Agent Continuity/Transcripts/thread-1",
        ]
    )

    assert result == 0
    assert not output.exists()


def test_unique_thread_archive_allows_reexport_by_owning_agent(tmp_path):
    output = tmp_path / "90_Sources/Core Agent Continuity/Transcripts/thread-1"
    output.mkdir(parents=True)
    output.joinpath("manifest.json").write_text(json.dumps({"thread_id": "thread-1"}), encoding="utf-8")

    exporter.ensure_unique_thread_archive(output, "thread-1")


def test_unique_thread_archive_rejects_cross_agent_copy(tmp_path):
    existing = tmp_path / "90_Sources/Biology Agent Continuity/Transcripts/thread-1"
    existing.mkdir(parents=True)
    existing.joinpath("manifest.json").write_text(json.dumps({"thread_id": "thread-1"}), encoding="utf-8")
    proposed = tmp_path / "90_Sources/Audit Agent Continuity/Transcripts/thread-1"

    with pytest.raises(ValueError, match="already belongs to another agent continuity archive"):
        exporter.ensure_unique_thread_archive(proposed, "thread-1")


def test_unique_thread_archive_rejects_unfinished_cross_agent_copy(tmp_path):
    existing = tmp_path / "90_Sources/Biology Agent Continuity/Transcripts/thread-1"
    existing.mkdir(parents=True)
    proposed = tmp_path / "90_Sources/Audit Agent Continuity/Transcripts/thread-1"

    with pytest.raises(ValueError, match="already belongs to another agent continuity archive"):
        exporter.ensure_unique_thread_archive(proposed, "thread-1")


def test_manifest_refresh_tracks_post_navigation_bytes_and_is_idempotent(tmp_path):
    source = tmp_path / "thread.jsonl"
    source.write_bytes(
        _line(
            "2026-07-01T00:00:01Z",
            "response_item",
            {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "Question"}]},
        )
    )
    snapshot = exporter.read_visible_snapshot(source)
    files = exporter.build_export_files(
        snapshot=snapshot,
        thread_id="thread-1",
        vault_target="90_Sources/Core Agent Continuity/Transcripts/thread-1",
        max_rendered_lines=80,
    )
    output = tmp_path / "export"
    exporter.write_transaction(output, files)
    readme = output / "README.md"
    readme.write_bytes(readme.read_bytes() + b"\n<!-- PROJECT_BREADCRUMB_V1:START -->\n")

    changed, _ = exporter.refresh_manifest(output, apply=False)
    assert changed
    changed, _ = exporter.refresh_manifest(output, apply=True)
    assert changed

    manifest = json.loads((output / "manifest.json").read_text(encoding="utf-8"))
    readme_record = next(item for item in manifest["output_files"] if item["path"] == "README.md")
    assert readme_record["sha256"] == hashlib.sha256(readme.read_bytes()).hexdigest()
    assert manifest["output_inventory_state"] == "post_navigation"
    assert exporter.refresh_manifest(output, apply=False)[0] is False


def test_manifest_refresh_accepts_configured_schema_version(tmp_path):
    source = tmp_path / "thread.jsonl"
    source.write_bytes(
        _line(
            "2026-07-01T00:00:01Z",
            "response_item",
            {"type": "message", "role": "user", "content": [{"type": "input_text", "text": "Question"}]},
        )
    )
    snapshot = exporter.read_visible_snapshot(source)
    schema_version = "audit_agent_continuity_manifest_v1"
    files = exporter.build_export_files(
        snapshot=snapshot,
        thread_id="thread-1",
        vault_target="90_Sources/Audit Agent Continuity/Transcripts/thread-1",
        max_rendered_lines=80,
        manifest_schema_version=schema_version,
        agent_label="Audit Owner",
    )
    output = tmp_path / "export"
    exporter.write_transaction(output, files)

    changed, proposed = exporter.refresh_manifest(
        output,
        apply=False,
        expected_schema_version=schema_version,
    )

    assert changed
    manifest = json.loads(proposed)
    assert manifest["schema_version"] == schema_version
    assert manifest["agent_label"] == "Audit Owner"


def test_export_redacts_credentials_and_preserves_source_record_hash(tmp_path):
    source = tmp_path / "thread.jsonl"
    secret = "sk-api-1234567890abcdefghijklmnop"
    raw = _line(
        "2026-07-01T00:00:01Z",
        "response_item",
        {
            "type": "message",
            "role": "user",
            "content": [{"type": "input_text", "text": f"--api-key {secret}"}],
        },
    )
    source.write_bytes(raw)

    snapshot = exporter.read_visible_snapshot(source)
    files = exporter.build_export_files(
        snapshot=snapshot,
        thread_id="thread-1",
        vault_target="90_Sources/Core Agent Continuity/Transcripts/thread-1",
        max_rendered_lines=80,
    )

    archived = files["visible_messages.jsonl"]
    assert secret.encode("utf-8") not in archived
    assert b"[REDACTED_CREDENTIAL]" in archived
    assert snapshot.messages[0].source_raw_sha256 == hashlib.sha256(raw).hexdigest()
    assert snapshot.messages[0].credential_redaction_count == 1
    manifest = json.loads(files["manifest.json"])
    assert manifest["redacted_message_count"] == 1
    assert manifest["credential_redaction_count"] == 1


def test_replace_with_retry_handles_transient_permission_error(tmp_path, monkeypatch):
    source = tmp_path / "source.txt"
    destination = tmp_path / "destination.txt"
    source.write_text("replacement", encoding="utf-8")
    destination.write_text("old", encoding="utf-8")
    real_replace = exporter.os.replace
    attempts = 0

    def transient_replace(first, second):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise PermissionError("transient index lock")
        real_replace(first, second)

    monkeypatch.setattr(exporter.os, "replace", transient_replace)
    exporter._replace_with_retry(source, destination, attempts=2, initial_delay_seconds=0)

    assert attempts == 2
    assert destination.read_text(encoding="utf-8") == "replacement"


def test_write_transaction_falls_back_when_directory_is_locked(tmp_path, monkeypatch):
    output = tmp_path / "export"
    exporter.write_transaction(
        output,
        {"README.md": b"# Old\n", "obsolete.md": b"obsolete\n"},
    )
    real_replace = exporter._replace_with_retry

    def lock_directory(source, destination, **kwargs):
        if Path(source) == output and Path(source).is_dir():
            raise PermissionError("directory is indexed")
        real_replace(source, destination, **kwargs)

    monkeypatch.setattr(exporter, "_replace_with_retry", lock_directory)
    files = {"README.md": b"# New\n", "nested/current.md": b"current\n"}
    exporter.write_transaction(output, files)

    assert output.joinpath("README.md").read_bytes() == b"# New\n"
    assert output.joinpath("nested/current.md").read_bytes() == b"current\n"
    assert not output.joinpath("obsolete.md").exists()
