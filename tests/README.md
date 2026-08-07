# Test Suite

## Purpose

This directory proves the bootstrap's governance behavior and clean-room
architecture. Tests are split between parallel-safe surfaces and exclusive
repository/process fixtures by [configs/testing/execution_v1.json](../configs/testing/execution_v1.json).

## Contents

| File or directory | Significance |
| --- | --- |
| [test_conformance.py](test_conformance.py) | Verifies the six planes, documentation system, research-first state, owners, and orchestration bindings. |
| [test_research.py](test_research.py) | Verifies immutable text/PDF intake, authorized commit-pinned Git snapshots, recursive organization, Git identity/path/limit boundaries, optional PDF dependency consent states, deterministic PDF page extraction, duplicate detection, review states, and promotion boundaries. |
| [test_runner.py](test_runner.py) | Verifies affected-test selection and lifecycle-aware runner behavior. |
| [test_workflow_tools.py](test_workflow_tools.py) | Verifies coordination handoff and workflow entry points. |
| [tools/](tools) | Contains focused tests for each substantial repository CLI. |

## Change Discipline

Add focused tests with every changed contract and update the impact map. Keep
real-repository, Git, port, service, or shared-state tests in the serial phase
unless independent evidence proves worker isolation.
