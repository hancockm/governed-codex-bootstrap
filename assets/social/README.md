# Social Media Asset Catalog

## Purpose

This catalog provides a coherent visual sequence for introducing Governed
Codex Bootstrap to readers and developers. The initial set follows the launch
order in the system narrative: architecture, research, orchestration, A2A
owner boundaries, PDF intake, explicit PDF status receipts, conceptual testing,
executable test commands, and continuity.

## Contents

- `catalog.json` binds each asset to its purpose, source, export, dimensions,
  launch position, and alt text.
- `source/` contains editable SVG masters with exact text.
- `x/` contains PNG exports ready for X posts and the profile header.

Post images are 1200×628 PNG files. X documents that PNG is supported and
that a single image within the standard 2:1-to-3:4 range displays without
forced cropping. The profile header uses X's documented 1500×500 dimensions.

## Export And Publication

The SVG files are the maintained source. Re-export a selected source with a
local SVG-capable renderer at its registered dimensions, then run
`python -m pytest tests/test_social_assets.py -q`. Publish the PNG, use the
catalog alt text, and link back to the repository or user guide where the post
calls for it.

Do not publish all images at once. Use the catalog's `launch_order`: the
architecture overview anchors the launch thread; the focused developer assets
follow as standalone posts.

The A2A boundary post follows owner-scoped orchestration because the reader
first needs to understand independent owner authority. Its registered
`post_copy` is ready for X, and `post_timing` records its place in the series.
The research-first post follows the architecture overview and now shows both
file intake and exact commit-pinned Git capture. Git is a bounded source
adapter here, not permission to check out or execute a repository.
The terminal test-runner post follows the conceptual testing diagram so readers
see the lifecycle before receiving the five exact commands.
The PDF-status terminal follows the conceptual PDF post and makes unavailable,
empty-text, and encrypted boundaries concrete without implying OCR support.

## Change Discipline

Preserve the navy, cyan, violet, gold, and white palette; generous padding;
large type; and short claims. Avoid screenshots of private state, credentials,
user data, or unverified metrics. Update the SVG, PNG, catalog entry, tests,
and nearest README together.
