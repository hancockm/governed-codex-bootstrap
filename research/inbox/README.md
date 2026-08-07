# Research Inbox

## Purpose

This directory is the staging surface for original project research before it
is registered by [research_intake.py](../../tools/research_intake.py).

## Contents

Place exact `.md`, `.txt`, or `.pdf` source files here temporarily with enough
external provenance to describe their origin. Intake preserves all three as
exact byte records. Markdown and plain-text organization use the base Python
environment. PDF organization requires the optional, exact `pypdf==6.14.2`
dependency after Core obtains user approval; it extracts native text only and
does not perform OCR. Other formats remain visible rather than being silently
converted or discarded.

Do not clone a repository into this inbox. Use [research_git_adapter.py](../../tools/research_git_adapter.py) so
repository URL, explicit ref, full expected commit, tree, blob identities,
selection limits, and network authorization are recorded together.

## Change Discipline

Do not edit a source merely to make it easier to ingest. Register exact bytes,
verify the immutable record, and retain or remove the staging copy according
to the project's accepted source-retention policy.
