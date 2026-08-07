from __future__ import annotations

import subprocess

import pytest

from governance_bootstrap import __file__ as package_file

from tools import test_runner


def test_affected_mapping_is_focused_for_known_source() -> None:
    assert test_runner.affected_targets(["governance_bootstrap/research.py"]) == ["tests/test_research.py"]


def test_operational_policy_mapping_is_bounded_for_terra_triage() -> None:
    expected = [
        "tests/test_conformance.py",
        "tests/test_runner.py",
        "tests/tools/test_owner_scoped_orchestration.py",
    ]
    assert test_runner.affected_targets(["AGENTS.md"], posture="broad") == expected
    assert test_runner.affected_targets(["AGENTS.md"]) == [
        "tests/test_conformance.py",
        "tests/tools/test_owner_scoped_orchestration.py",
    ]


def test_affected_mapping_fails_closed_for_unknown_runtime_source() -> None:
    assert test_runner.affected_targets(["governance_bootstrap/new_runtime.py"]) == ["tests"]
    assert test_runner.affected_targets(["tests/test_runner.py"]) == ["tests/test_runner.py"]
    assert test_runner.affected_targets(["tests/test_runner.py"], posture="broad") == ["tests/test_runner.py"]


def test_changed_paths_includes_worktree_and_untracked_changes(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []

    def inspect(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        output = "AGENTS.md\n" if command[1] == "diff" else "docs/new.md\n"
        return subprocess.CompletedProcess(command, 0, stdout=output, stderr="")

    monkeypatch.setattr(test_runner.subprocess, "run", inspect)
    assert test_runner.changed_paths("origin/master") == ["AGENTS.md", "docs/new.md"]
    assert calls == [
        ["git", "diff", "--name-only", "--diff-filter=ACMRD", "origin/master", "--"],
        ["git", "ls-files", "--others", "--exclude-standard", "--"],
    ]


def test_pytest_command_uses_current_interpreter() -> None:
    assert test_runner.pytest_command(["-q"])[1:] == ["-m", "pytest", "-q"]
