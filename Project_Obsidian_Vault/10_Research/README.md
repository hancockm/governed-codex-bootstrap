# Research Area Guide

<!-- generated:breadcrumbs:start -->
<< Previous: none | Up: [[10_Research/Research Sources MOC]] | Next: [[10_Research/Research Source Map]] >>
<!-- generated:breadcrumbs:end -->

Research is the beginning source material for a new project. It remains
source-only until Core promotes a supported conclusion.

## Intake

Place candidate `.md`, `.txt`, or `.pdf` files in [research/inbox/](../../research/inbox), then
register them with [tools/research_intake.py](../../tools/research_intake.py). Intake records origin, title,
content identity, and exact bytes. Never overwrite an existing immutable
record.

For an authorized public Git repository, use [tools/research_git_adapter.py](../../tools/research_git_adapter.py)
with a credential-free HTTPS URL, explicit branch or tag ref, full expected
commit, title, and `--authorize-network`. The adapter creates a bounded
immutable snapshot with commit, tree, blob, path, byte-size, and SHA-256
lineage. It never checks out or executes repository code. Source licensing and
reuse rights remain separate review questions.

## Organization

[tools/research_organizer.py](../../tools/research_organizer.py) builds deterministic maps, extracts Markdown and
plain text recursively from file and Git-snapshot records, and extracts native
PDF text in page order when the approved
optional `pypdf==6.14.2` dependency is installed. Core asks the user before
downloading or installing that dependency. The extractor performs no OCR,
does not open encrypted PDFs, and records pages without extractable text as
diagnostics. Organization is not semantic promotion. Unsupported formats and
ambiguous material remain visible.

## Review

Reviews classify a candidate as current, candidate, superseded,
dead-end candidate, evidence, or source. A status explains how Core should
read it; it does not delete the record. Preserve contradictions and dead ends
when they explain why a later design was selected.

## Promotion

Core compares source records, reviews, assumptions, and current canonical
material. Promotion requires user authorization where applicable, precise
canonical wording, owner alignment, and executable evidence proportional to
the claim.

Use [[10_Research/Research Source Map]] as the vault entry to the generated
research map. The authoritative byte records remain under [research/records/](../../research/records).
