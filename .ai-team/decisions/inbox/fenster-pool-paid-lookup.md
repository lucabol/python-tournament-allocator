# Decision: Pool card paid status uses registration data lookup

**Date:** 2025-01-20
**Author:** Fenster (Frontend)

## Context
Pool cards in `teams.html` checked `pool_data.paid_teams` for paid status, but this field never exists in the pool data model. Pools are `{teams: [str], advance: int}` — no `paid_teams` key. Paid status lives exclusively in `registrations.teams[].paid`.

## Decision
Build a `paid_team_names` lookup list from `registrations` data using Jinja2 filters (`selectattr('paid') | map(attribute='team_name')`) and use it in pool card team checkboxes instead of the non-existent `pool_data.paid_teams`.

## Rationale
- Single source of truth: paid status is managed via `/api/toggle-paid` which updates `registrations.yaml`, so the template must read from the same source.
- No backend changes needed — `registrations` is already passed to the template.
- The Jinja2 `selectattr` + `map` pattern is idiomatic and efficient for building lookups.

## Impact
- Pool card paid checkboxes now correctly reflect each team's paid status on page load.
- `togglePaid()` API calls persist correctly across page reloads.
