### 2026-02-14: Court constraint tests for bracket scheduling
**By:** Hockney
**What:** Created `tests/test_schedule_validity.py` with 3 tests validating court constraints: `test_bracket_respects_court_hours` (matches within court operating hours), `test_minimum_break_on_same_court` (gap between matches >= min_break_between_matches_minutes), and `test_no_court_double_booking` (no overlapping matches on same court).
**Why:** Bracket scheduling must respect court availability and break requirements just like pool play scheduling. These tests validate the constraint checking formulas in isolation before integration with the full scheduling system. Tests execute in < 1 second and use the same datetime-based overlap logic as `AllocationManager._check_court_availability()`.
