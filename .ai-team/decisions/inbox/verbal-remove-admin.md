### 2026-02-19: Remove Admin User Concept

**By:** Verbal

**What:** Removed all privileged "admin" user logic from the codebase. No more admin accounts, ADMIN_PASSWORD env vars, admin-only routes, or admin migration logic.

**Why:** 
- Multi-user architecture already supports per-user tournament management; no privileged admin needed
- Site-wide export/import (`/api/export/site`, `/api/import/site`) was admin-only and not used
- Simplified codebase: removed `_ensure_admin_user_exists()`, `_migrate_to_admin_user()`, `is_admin()` checks
- Each user can export/import their own tournaments; no need for admin-level access

**Changes:**
- **Deleted functions:** `is_admin()`, `_ensure_admin_user_exists()`, `_migrate_to_admin_user()`
- **Deleted routes:** `/api/export/site`, `/api/import/site` (admin-only site backup/restore)
- **Deleted env var:** `ADMIN_PASSWORD` — no longer used
- **Deleted template logic:** Admin-only section from `tournaments.html`
- **Deleted tests:** `TestSiteExportImport` class (16 tests), `test_delete_account_admin_prevented`, migration tests
- **Updated:** `ensure_tournament_structure()` now just ensures directories exist; all migration logic removed
- **Updated:** `api_delete_account()` now allows all users to delete their own account (no admin exception)

**Verification:**
- 450 of 457 tests pass (7 failures in unrelated backup script tests)
- User-scoped tournament export/import (`/api/export/user`, `/api/import/user`) works fine
- No admin references remain in codebase (verified with grep)
- App syntax valid; no import errors
