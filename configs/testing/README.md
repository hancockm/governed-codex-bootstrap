# Testing Configuration

## Purpose

This directory separates test-selection policy from the test runner so the
repository can review execution and impact behavior as versioned evidence.

## Contents

- `execution_v1.json` divides the suite into parallel-safe and exclusive
  serial surfaces and fixes the worker cap and distribution strategy.
- `test_impact_v1.json` maps changed source/configuration paths to focused and
  broad test boundaries. Unknown runtime paths fail closed to the broad suite.

## Change Discipline

Do not mark a test parallel-safe without checking shared filesystem, database,
port, process, environment, Git, and cache behavior. Every new maintained
source surface must have an impact-map disposition.
