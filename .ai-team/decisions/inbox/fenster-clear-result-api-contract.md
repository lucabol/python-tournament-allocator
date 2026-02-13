### Clear result button expects POST /api/clear-result endpoint
**By:** Fenster
**Date:** 2026-02-14
**What:** The tracking page (`tracking.html`) now has a "✕" clear button on each completed match. It calls `POST /api/clear-result` with JSON body `{"match_key": "<match_key>"}` where `match_key` is the same key format used in `results.yaml` (e.g., `TeamA_vs_TeamB_Pool1`). The endpoint should remove the result entry from `results.yaml` and return `{"success": true}`. McManus needs to implement this endpoint.
**Why:** Tournament managers need to correct mistakes — clearing a result is simpler than re-entering scores. The frontend is ready; only the backend route is missing.
