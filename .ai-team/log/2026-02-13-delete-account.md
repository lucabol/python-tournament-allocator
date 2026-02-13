# Delete Account Session

**Date:** 2026-02-13  
**Requested by:** Luca Bolognese

## Summary

Implemented user account deletion feature with confirmation dialog and comprehensive test coverage.

## Work Breakdown

### McManus - Backend Implementation
- Added `POST /api/delete-account` route to `src/app.py`
- Blocks admin deletion (admins cannot delete themselves via API)
- Removes user from `users.yaml`
- Deletes user's data directory
- Clears Flask session on successful deletion

### Fenster - Frontend UI
- Added "Delete Account" danger zone section to `src/templates/constraints.html`
- Red button with distinctive styling
- Uses typed-confirmation pattern: user must type "DELETE" in a `prompt()` dialog (not just click OK)
- Mirrors the site export/import danger-zone UX pattern

### Hockney - Test Coverage
- Wrote 5 tests in `TestDeleteAccount` class
- Test cases:
  1. Successful deletion of regular user account
  2. Multi-tournament cleanup (all user tournaments deleted)
  3. Admin deletion blocked (cannot delete own admin account)
  4. Login required (unauthenticated requests rejected)
  5. Other users unaffected (deletion doesn't impact other users in system)

## Results

- ✅ All 249 tests passed
- ✅ Committed as: `3b35d7b: "feat: add delete account with confirmation dialog and 5 tests"`

## Files Modified

- `src/app.py` — Added `/api/delete-account` route
- `src/templates/constraints.html` — Added danger zone section
- `tests/test_app.py` — Added `TestDeleteAccount` test class
