from __future__ import annotations

from governance_bootstrap import __file__ as package_file

from tools import test_runner


def test_affected_mapping_is_focused_for_known_source() -> None:
    assert test_runner.affected_targets(["governance_bootstrap/research.py"]) == ["tests/test_research.py"]


def test_affected_mapping_fails_closed_for_unknown_runtime_source() -> None:
    assert test_runner.affected_targets(["governance_bootstrap/new_runtime.py"]) == ["tests"]


def test_pytest_command_uses_current_interpreter() -> None:
    assert test_runner.pytest_command(["-q"])[1:] == ["-m", "pytest", "-q"]
