# Coordination Receipts

## Purpose

This directory is the non-vault storage boundary for content-addressed
coordination receipts created by [agent_to_agent_plan_handoff.py](../../tools/agent_to_agent_plan_handoff.py) and related
workflow tools.

## Contents

Receipt files bind a request to its source content and requested owner action.
The maintained human reading surface remains the coordination vault.

## Change Discipline

Receipts are immutable evidence. Do not overwrite an existing identity or use
a receipt as canonical doctrine, user approval, or another owner's decision.
