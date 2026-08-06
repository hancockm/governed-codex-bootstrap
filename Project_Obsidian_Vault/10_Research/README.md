# Research Area Guide

<!-- generated:breadcrumbs:start -->
<< Previous: none | Up: [[10_Research/Research Sources MOC]] | Next: [[10_Research/Research Source Map]] >>
<!-- generated:breadcrumbs:end -->

Research is the beginning source material for a new project. It remains
source-only until Core promotes a supported conclusion.

## Intake

Place candidate files in `research/inbox/`, then register them with
`tools/research_intake.py`. Intake records origin, title, content identity,
and exact bytes. Never overwrite an existing immutable record.

## Organization

`tools/research_organizer.py` builds deterministic maps, extracts supported
text, and identifies exact or near-duplicate candidates. Organization is not
semantic promotion. Unsupported formats and ambiguous material remain visible.

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

Use [[10_Research/Research Source Map.md]] as the vault entry to the generated
research map. The authoritative byte records remain under `research/records/`.
