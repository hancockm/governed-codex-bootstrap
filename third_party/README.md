# Third-Party Artifact Records

## Purpose

This directory contains exact-artifact provenance and license records for
third-party material intentionally used by the bootstrap.

## Contents

- `pytest-xdist-3.8.0.json` records the pinned parallel-test dependency.
- `execnet-2.1.2.json` records xdist's pinned worker-transport dependency.
- `pypdf-6.14.2.json` records the optional, user-approved native-text PDF
  research extractor. It is not installed by the cold start and provides no
  OCR capability.

## Change Discipline

One immutable record describes one exact artifact. Record its version, hash,
provenance, license, and posture before use; never treat a package name or
SBOM alone as exact legal or integrity evidence.
