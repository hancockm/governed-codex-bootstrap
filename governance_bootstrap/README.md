# Governance Bootstrap Package

## Purpose

This Python package contains reusable library logic behind the repository
commands. It implements governance mechanics, not the future product runtime.

## Contents

| Module | Significance |
| --- | --- |
| [__init__.py](__init__.py) | Declares the reusable package. |
| [common.py](common.py) | Shared canonical serialization, hashing, path, and validation primitives. |
| [conformance.py](conformance.py) | Composes six-plane, documentation, vault, owner, testing, artifact, and neutrality checks. |
| [coordination.py](coordination.py) | Builds and validates content-addressed coordination records. |
| [git_research.py](git_research.py) | Captures explicitly authorized public HTTPS Git refs at an exact commit into bounded immutable Markdown, text, and PDF research snapshots without checkout or code execution. |
| [research.py](research.py) | Implements immutable `.md`, `.txt`, and `.pdf` research intake and provenance records without parser installation. |
| [research_organizer.py](research_organizer.py) | Recursively maps file and Git-snapshot research records, including text sections and native-text PDF pages, explicit dependency/format diagnostics, source comparison, and review state. |

The CLI adapters for these modules are indexed in [`tools/README.md`](../tools/README.md).

## Change Discipline

Keep this package project-neutral. Public behavior needs type annotations,
docstrings, focused tests, impact-map coverage, and conformance verification.
Do not place product or domain doctrine here.
