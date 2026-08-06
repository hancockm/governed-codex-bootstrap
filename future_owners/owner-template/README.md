# Future Owner Template

## Purpose

This inactive scaffold shows every owner dependency without granting a role,
namespace, capability, or write authority.

## Contents

- `ROLE.md` defines the future owner's scope and prohibitions.
- `BOOTSTRAP.md` defines its cold-start sequence.
- `owner_profile.json` maps dependencies, public contracts, and owned paths.
- `orchestration_profile.json` binds owner-scoped development lanes.
- `continuity/` contains the required continuity MOC scaffold.

## Change Discipline

Do not activate this template in place. Create a uniquely named owner package,
replace every placeholder, validate it while inactive, obtain owner adoption,
and let Core integrate and activate it.
