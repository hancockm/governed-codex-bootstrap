# Agent Governance Bundle

## Purpose

This bundle defines reusable, public development-governance data. It does not
define product runtime behavior or external provider behavior.

## Contents

| File | Significance |
| --- | --- |
| [component_manifest_v1.json](component_manifest_v1.json) | Declares the public bundle identity and the deterministic verifier. |
| [dependency_profile_v1.json](dependency_profile_v1.json) | Records exact development-only default tools and optional audit trials. |

## Change Discipline

Keep artifact identities exact. The bundle permits no network egress and does
not contain installation commands. The controlled development environment
selects any artifact location outside this bundle.
