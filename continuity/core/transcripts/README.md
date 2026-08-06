# Core Transcript Export Root

## Purpose

This directory receives complete bounded Core transcript exports produced by
`export_agent_thread_continuity.py` when an exact session source is available.

## Contents

Each generated task directory contains sanitized source records, display-safe
Markdown, chronological indexes, and a manifest binding the observed source
prefix to the output inventory. An empty root means no task has been exported.

## Change Discipline

Do not hand-author task directories or edit generated files. Dry-run the
exporter first, verify ownership and redaction, then apply and validate the
post-navigation manifest.
