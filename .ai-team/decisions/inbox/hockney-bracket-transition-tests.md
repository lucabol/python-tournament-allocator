### 2026-02-14: Bracket phase transition tests implemented
**By:** Hockney
**What:** Created `TestBracketPhaseTransitions` class with 3 test methods validating pool-to-bracket timing constraints
**Why:** System needs validation that bracket phases respect pool completion and configurable delays before tournament execution

**Tests added:**
1. `test_pool_to_bracket_delay_enforced` — Bracket starts after specified `pool_to_bracket_delay_minutes` from pool end
2. `test_bracket_starts_after_pools_complete` — All pool matches must finish before bracket starts (handles multi-pool staggered completion)
3. `test_no_placeholders_in_scheduled_bracket` — Scheduled matches contain only concrete teams, not placeholders like "#1 Pool A" or "Winner W1-M1"

**Key constraint:** `pool_to_bracket_delay_minutes` from `constraints.yaml` (default: 0, test uses 60)

**Test execution:** All 12 tests in `test_schedule_validity.py` pass in 1.01s
