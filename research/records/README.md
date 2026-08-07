# Immutable Research Records

## Purpose

This directory contains content-addressed source records created by
[research_intake.py](../../tools/research_intake.py) and reviewed or mapped by
[research_organizer.py](../../tools/research_organizer.py).

## Contents

Each record preserves the source hash, provenance, title, origin, and review
state. Markdown, plain text, and PDFs remain source material, not canonical
doctrine. PDF page text is a derived candidate projection; the exact PDF bytes
remain authoritative. Empty/image-only pages remain explicit diagnostics and
are never presented as successfully extracted prose.

Git snapshots use a `git-<identity>` directory containing exact selected file
bytes and `snapshot.json`. The manifest binds the public repository URL,
requested ref, full commit, tree, blob IDs, SHA-256 hashes, limits, and known
omissions. The organizer reads supported files recursively, while the manifest
remains provenance rather than candidate prose.

## Change Discipline

Never overwrite an existing content identity. Add a new record for changed
bytes or provenance, preserve superseded and dead-end candidates, and require
explicit Core review before any claim enters canonical documentation.
