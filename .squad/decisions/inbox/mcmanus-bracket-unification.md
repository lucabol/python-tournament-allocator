# Decision: Bracket Result Keys Unified on match_code

**By:** McManus (Backend Dev)
**Date:** 2025-07-22
**Status:** Implemented

## Context

Three different key formats existed for the same bracket match:
- `match_code` (e.g. `W1-M1`) — used by schedule and bracket generators
- `match_key` (e.g. `winners_Winners Quarterfinal_1`) — used by result storage
- `round_name` internal (e.g. `Winners Quarterfinal_1`) — used by advancement tracking

The `enrich_schedule_with_results()` function used a fragile `derive_match_code()` heuristic to translate between formats. This caused recurring bugs where the Bracket tab and Schedule tab showed different data.

## Decision

**`match_code` is now the canonical key for bracket results.**

- `save_bracket_result()` stores under `match_code` as primary key
- `api_generate_random_bracket_results()` stores under `match_code` as primary key
- Both still store under old `match_key` format as secondary entry for backward compat
- `enrich_schedule_with_results()` does direct `match_code` lookup (no heuristic)
- `derive_match_code()` and `round_indices` mapping removed

## Impact

- Existing bracket results saved under old keys still work (backward compat via team-pair fallback + old key still in resolved_teams dict)
- New results are findable by both key formats
- ~30 lines of fragile translation logic removed from enrichment
- 3 new integration tests added to catch future regressions

## Files Changed

- `src/app.py` — save_bracket_result, api_generate_random_bracket_results, enrich_schedule_with_results
- `tests/test_app.py` — TestBracketScheduleRoundTrip class (3 tests)
- `.ai-team/agents/mcmanus/history.md` — updated
