# Governance Bootstrap Package

## Purpose

This Python package contains reusable library logic behind the repository
commands. It implements governance mechanics, not the future product runtime.

## Contents

| Module | Significance |
| --- | --- |
| `__init__.py` | Declares the reusable package. |
| `common.py` | Shared canonical serialization, hashing, path, and validation primitives. |
| `conformance.py` | Composes six-plane, documentation, vault, owner, testing, artifact, and neutrality checks. |
| `coordination.py` | Builds and validates content-addressed coordination records. |
| `research.py` | Implements immutable `.md`, `.txt`, and `.pdf` research intake and provenance records without parser installation. |
| `research_organizer.py` | Implements text-section and native-text PDF-page extraction, explicit dependency/format diagnostics, source comparison, review state, and research-map construction. |

The CLI adapters for these modules are indexed in [`tools/README.md`](../tools/README.md).

## Change Discipline

Keep this package project-neutral. Public behavior needs type annotations,
docstrings, focused tests, impact-map coverage, and conformance verification.
Do not place product or domain doctrine here.
