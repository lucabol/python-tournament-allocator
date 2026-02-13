### 2026-02-13: User directive
**By:** Luca Bolognese (via Copilot)
**What:** Always use the fast tests (`pytest -m "not slow"`) unless there is a change to the scheduling algorithm. Only run the full suite (`pytest tests/`) when allocation/scheduling code in src/core/allocation.py is modified.
**Why:** User request — fast feedback loop for non-scheduling changes. Captured for team memory.
