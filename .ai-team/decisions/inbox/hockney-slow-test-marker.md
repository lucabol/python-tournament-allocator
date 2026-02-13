### 2026-02-13: pytest `slow` marker for OR-Tools solver tests
**By:** Hockney
**What:** Added `@pytest.mark.slow` marker to `TestLargeTournament` class (2 tests in `test_integration.py`). Created `pytest.ini` with marker registration. Fast subset runs via `pytest tests/ -m "not slow"` (~21s vs ~137s full suite). Usage documented in `conftest.py` docstring.
**Why:** Full suite takes ~2.3 minutes, almost entirely due to two OR-Tools CP-SAT solver tests that hit the 60-second timeout. For small changes (button colors, template tweaks), waiting 2+ minutes is unnecessary friction. The fast subset covers 274 of 276 tests including all route, model, bracket, and auth tests.
