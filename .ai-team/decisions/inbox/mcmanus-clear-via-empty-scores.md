### 2026-02-13: Result clearing via empty score submission

**By:** McManus  
**What:** Match result API endpoints (`/api/results/pool` and `/api/results/bracket`) now detect when all scores are empty/None and delete the result instead of treating it as invalid input. Partial input (one score filled, one empty) is still validated and rejected with a 400 error.  
**Why:** User preference — simpler UX. Instead of needing a separate "Clear Result" button, users can clear a result by deleting both scores and submitting the form. This is more intuitive and reduces UI clutter. The separate `/api/clear-result` endpoint remains available for programmatic use (e.g., the bracket clear buttons).  
**Impact:** All 276 tests pass. No breaking changes — existing clear buttons still work via `/api/clear-result`.
