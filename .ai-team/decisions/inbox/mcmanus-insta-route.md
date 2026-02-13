### Instagram summary route reuses _get_live_data()
**By:** McManus
**Date:** 2026-02-13
**What:** Added `GET /insta` route that renders `insta.html` with the full `_get_live_data()` payload (pools, standings, schedule, results, bracket_data, silver_bracket_data, awards, constraints). Added `'insta'` to the `tournament_endpoints` whitelist so it works without an active tournament.
**Why:** Follows the same pattern as `/live` — reuses the existing data-gathering helper rather than duplicating logic. Template rendering is delegated to Fenster's `insta.html`.
