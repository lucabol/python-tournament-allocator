# Auto-activate First Tournament on Navigation

**By:** Fenster  
**Date:** 2026-02-14  
**Context:** Issue #7 — Navigation redirects to tournaments page even when tournaments exist

## Problem
When a user has tournaments but none is set as active (either in session or tournaments.yaml), clicking any nav link (Teams, Courts, etc.) redirected to `/tournaments` with "Please create a tournament first" message. This happened when:
- Session expired/cleared and tournaments.yaml had `active: null`
- User switched browsers/devices
- Tournaments.yaml got corrupted or manually edited

## Solution
Added auto-activation logic in `set_active_tournament()` before_request hook:
1. If no `active_slug` but tournaments exist in registry
2. Automatically activate the first tournament
3. Update both tournaments.yaml and session
4. Continue normal request processing

## Implementation
```python
# Auto-activate first tournament if none is active but tournaments exist
if not active_slug and tournaments.get('tournaments'):
    first_slug = tournaments['tournaments'][0]['slug']
    tournament_path = os.path.join(g.user_tournaments_dir, first_slug)
    if os.path.isdir(tournament_path):
        active_slug = first_slug
        tournaments['active'] = first_slug
        save_tournaments(tournaments)
        session['active_tournament'] = first_slug
```

## Why This Works
- Follows existing pattern from `api_import_user` route (line 3480-3484)
- User-friendly: automatically recovers from stale session state
- Predictable: always activates first tournament (alphabetically)
- Safe: verifies directory exists before activating

## Test Coverage
Added `TestNavigationWithStaleSession` class with 3 tests:
- Navigation with missing tournament directory → redirects gracefully
- Navigation with valid active tournament → works normally
- Navigation with null active but tournaments exist → auto-activates first

All 279 tests pass.
