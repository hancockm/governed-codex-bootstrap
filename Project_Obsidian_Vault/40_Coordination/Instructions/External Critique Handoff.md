# External Critique Handoff

<!-- generated:breadcrumbs:start -->
<< Previous: [[40_Coordination/Instructions/Owner-Scoped Development Lanes]] | Up: [[40_Coordination/Instructions/README]] | Next: none >>
<!-- generated:breadcrumbs:end -->

## Purpose

An external critique provider can challenge a plan and write or return one
advisory record. It is not an implementation owner, canonical authority, or
substitute for repository evidence.

## Create The Handoff

```text
python tools/agent_to_agent_plan_handoff.py --topic <topic> --plan-file <path> --dry-run
python tools/agent_to_agent_plan_handoff.py --topic <topic> --plan-file <path> --apply
```

Optional configured invocation uses `--invoke agy`, `--invoke mmx`, or
`--invoke codex`. Installation alone does not authorize invocation.

## Completion Evidence

Success requires a valid critique with the shared headings in the assigned
atomic record. A zero exit code, empty stdout, quota message, authentication
message, or log file without a valid record is not completion.

## Failure And Fallback

Record the unavailable provider or malformed output safely. Use a configured
fallback only when policy permits it. If no provider succeeds, preserve the
handoff prompt and proceed only with already authorized work or user direction.

## Publication

The owning agent evaluates and disposes every substantive point. Core or the
authorized owner publishes indexes and canonical consequences. External agents
never edit unrelated files, shared indexes, or canonical documents.
