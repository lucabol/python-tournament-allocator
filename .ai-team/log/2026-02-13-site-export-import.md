# Site Export/Import

**Date:** 2026-02-13
**Requested by:** Luca Bolognese

## What Happened

- **McManus** added `is_admin()` helper, `GET /api/export/site` and `POST /api/import/site` routes to `src/app.py`.
- **Fenster** added admin-only "Site Administration" section to `tournaments.html` with danger-zone styling.
- **Hockney** wrote 9 tests in `TestSiteExportImport` class (admin auth, export structure, import replace, security, session clear).
- **Coordinator** fixed `DATA_DIR` vs `site_root` mismatch — export/import now derives site root from `USERS_FILE` parent.
- **Coordinator** fixed Fenster's hardcoded URLs to use `url_for()`.

## Result

All 244 tests pass. Committed as `4d498a5`.
