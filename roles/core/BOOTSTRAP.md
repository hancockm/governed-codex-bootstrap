# Core Bootstrap Entry Point

Use `Project_Obsidian_Vault/30_Core/Core Bootstrap.md` as the complete cold-
start and rehydration prompt. This file is the stable role-level pointer.

Required order:

1. root repository policy;
2. `configs/codex_bootstrap_v1.json` native-capability and plugin preflight;
3. Core role and complete vault bootstrap;
4. Core continuity MOC and relevant protocols;
5. research MOCs and exact source records; when `.pdf` sources are present or
   requested, inspect the optional PDF dependency state and ask the user before
   any download or installation; when a public Git source is requested, require
   its exact URL/ref/commit identity and separate network authorization;
6. canonical MOCs and capability registry;
7. coordination records relevant to the request;
8. source, tests, configuration, receipts, Git status/history;
9. Core integration inbox and safe primary synchronization.

The first response reports baseline/freshness, Codex native-capability and
plugin preflight, inspected evidence, current request status,
canonical/runtime discrepancies, challenged assumptions, and owner
boundaries. Do not infer product doctrine from this generic bootstrap.

Markdown and plain-text research require no optional parser. PDF organization
requires the exact optional `pypdf==6.14.2` artifact. If it is absent or has a
different version, explain its BSD-3-Clause record and native-text-only limits,
then ask the user for explicit approval before running
`python -m pip install -e ".[pdf]"`. Never install it as a side effect of
startup, intake, scan, or build.

Public Git research uses the already required local Git executable and needs no
plugin or Python dependency. Capture only after the user authorizes network
access and supplies a credential-free HTTPS URL, explicit branch or tag ref,
and full expected commit. The adapter must verify the commit, preserve tree and
blob lineage, enforce bounded `.md`/`.txt`/`.pdf` selection, and perform no
checkout, hooks, code execution, submodule, Git LFS, issue, pull-request, or
release acquisition.
