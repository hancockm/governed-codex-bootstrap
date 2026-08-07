# Research Intake

## Purpose

Research is the source-only starting surface for the project. `.md`, `.txt`,
and `.pdf` inputs are preserved as exact immutable records before any
interpretation or canonical promotion.

## Contents

- `inbox/` stages exact user-supplied sources.
- `records/` contains content-addressed source bytes and provenance metadata.
- `derived/` contains reproducible organizer output.
- `reviews/` contains separate human/Core dispositions.
- `schema.json` describes intake metadata; `example-record.json` is only an
  example.

Markdown and plain-text organization uses the base install. PDF organization
requires user approval before installing the optional `pypdf==6.14.2` extra,
extracts native text only, and leaves OCR/image-only limitations explicit.

## Change Discipline

Do not edit immutable records, silently omit unavailable sources, or treat an
organizer candidate as accepted doctrine. Register changed bytes as a new
record and keep extraction diagnostics with the derived map.
