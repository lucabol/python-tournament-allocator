# Decision: Paid checkboxes must use team-bound identifiers

**Date:** 2025-07-18
**Author:** Fenster
**Status:** Accepted

## Context

Paid checkboxes in the Unassigned Teams section and the Pools section lacked unique `id` and `name` attributes. Browsers restore form state by element position on `location.reload()`, so when a team was moved and the DOM shifted, the next team inherited the previous team's checked state.

## Decision

All paid checkboxes now get:
- A unique `id` tied to the team name (e.g., `paid-unreg-Team_A`)
- A matching `name` attribute
- `autocomplete="off"` to prevent browser form state restoration

This ensures checkbox state is always driven by server-rendered `{% if reg.paid %}checked{% endif %}`, never by stale browser cache.

## Consequences

Any future checkbox or form input that tracks per-entity state should follow the same pattern: unique `id`/`name` derived from the entity identifier, plus `autocomplete="off"`.
