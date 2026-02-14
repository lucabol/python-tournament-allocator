### 2026-02-14: Schedule validation helper functions

**By:** Hockney

**What:** Created three reusable schedule validation helpers in `tests/test_helpers_validation.py`:

1. **validate_no_premature_scheduling(schedule, dependencies, match_codes)** — Validates teams aren't scheduled before prerequisite matches complete
2. **validate_team_availability(schedule, team_name)** — Validates teams aren't double-booked (no overlapping matches)
3. **validate_bracket_dependencies(schedule, bracket_structure)** — Validates bracket match dependencies are respected

Each helper returns `List[str]` of clear, actionable violation messages (empty list = valid).

**Why:** Phase 2 schedule validity tests will need common validation logic to verify:
- Placeholder teams (e.g., "Winner M1") aren't scheduled before their defining matches complete
- No team plays two matches at once
- Bracket structure dependencies are honored

These helpers eliminate duplication across Phase 2 tests and provide reusable, well-tested validation building blocks. All helpers are pure functions with comprehensive test coverage (24 tests covering valid/invalid/edge cases).

**API Design Notes:**
- `validate_no_premature_scheduling` requires `match_codes` dict mapping teams tuple to match code, since schedule tuples don't carry match identifiers. Phase 2 tests should build this mapping during schedule generation.
- Schedule format: `Dict[str, List[Tuple[int, datetime, datetime, Tuple[str, str]]]]` (court name → list of (day, start, end, teams))
- All helpers handle edge cases: empty schedules, missing matches, cross-day dependencies, midnight crossing, back-to-back matches.
