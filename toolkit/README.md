# Governance Toolkit

## Purpose

This directory contains public, reusable governance bundles. Each bundle is
data-only and has a deterministic verifier in [tools/](../tools/README.md).

## Contents

| File or directory | Significance |
| --- | --- |
| [agent_governance/](agent_governance/README.md) | Defines the public agent-governance bundle, its dependency profile, and its component manifest. |

## Change Discipline

Keep each bundle project-neutral. Do not add absolute paths, private source
identities, or environment-specific provenance. Update the bundle verifier,
tests, tool inventory, and impact mapping with every contract change.
