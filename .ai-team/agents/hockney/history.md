# Project Context

- **Owner:** Luca Bolognese (lucabol@microsoft.com)
- **Project:** Python Flask tournament scheduling and management web application
- **Stack:** Python 3.11+, Flask, Jinja2, pandas, numpy, OR-Tools CP-SAT, PyYAML, pytest
- **Created:** 2026-02-11

## Learnings

<!-- Append new learnings below. Each entry is something lasting about the project. -->

- **2026-02-11 — Multi-tournament test suite created (`tests/test_tournaments.py`)**
  - 17 proactive tests across 6 test classes written from design spec before implementation.
  - Classes: `TestTournamentCreation` (5), `TestTournamentDeletion` (4), `TestTournamentSwitch` (2), `TestTournamentMigration` (3), `TestTournamentIsolation` (2), `TestTournamentList` (1).
  - Tests expect module-level attrs `TOURNAMENTS_DIR` and `TOURNAMENTS_REGISTRY` on `app` module, plus routes at `/tournaments`, `/api/tournaments/create`, `/api/tournaments/delete`, `/api/tournaments/switch`.
  - Registry format assumed: `{'tournaments': [{'name': ..., 'slug': ...}], 'active': '<slug>'}` stored in `data/tournaments.yaml`.
  - `base.html` already has a nav link to `url_for('tournaments')` — any test that renders a template will fail until McManus adds the route. This is a known pre-existing issue, not caused by the test file.
  - Existing `test_app.py` fixture pattern uses `monkeypatch.setattr` on module-level file-path constants (`DATA_DIR`, `TEAMS_FILE`, etc.) to redirect I/O to `tmp_path`.

- **2026-02-12 — Tournament CRUD corner-case tests added (`tests/test_app.py :: TestTournamentCRUDCornerCases`)**
  - 7 tests covering: no-tournament guard redirect (routes redirect to `/tournaments`), tournament management routes still accessible when empty, create-when-empty, session sync on delete (active switches to remaining), delete-last clears session, corrupted `tournaments.yaml` returns default, corrupted `users.yaml` returns empty list.
  - Tests use existing `client` + `temp_data_dir` fixtures and follow the `_delete_all_tournaments` / `_create_tournament` helper pattern for setup.
  - Corrupted-YAML tests write literal invalid YAML and call `load_tournaments()` / `load_users()` directly, expecting graceful fallback to defaults.
  - These tests are written ahead of McManus's implementation; they will fail until the 3 fixes land.

- **2026-02-12 — Public live page tests added (`tests/test_app.py :: TestPublicLive`)**
  - 7 tests covering the public (no-auth) live tournament endpoints: `/live/<username>/<slug>`, `/api/live-html/<username>/<slug>`, `/api/live-stream/<username>/<slug>`.
  - Tests use `app.test_client()` directly (not the `client` fixture) to verify anonymous access without login.
  - Covers: 200 on valid paths (3 endpoints), 404 for nonexistent user, 404 for nonexistent tournament, path traversal rejection, public_mode flag in rendered output.
  - Uses `temp_data_dir` fixture to set up monkeypatched `USERS_DIR` — the public URL `/live/testuser/default` maps to the fixture's `tmp_path/users/testuser/tournaments/default` directory.
  - Written ahead of McManus's implementation; tests will fail until the routes are added.

- **2026-02-12 — User-level export/import tests added (`tests/test_app.py :: TestUserExportImport`)**
  - 6 tests covering `/api/export/user` and `/api/import/user` endpoints.
  - Tests: valid ZIP export with tournaments.yaml + default/ entries, multi-tournament export coverage, import creates new tournament directory, import overwrites existing tournament files, path traversal rejection (security), preservation of unmentioned tournaments on import.
  - Uses module-level `_make_user_zip()` helper that builds ZIPs with `tournaments.yaml` + per-slug file entries.
  - Directory navigation: `temp_data_dir.parent` = tournaments dir, `.parent.parent` = user dir (where tournaments.yaml lives), `.parent.parent.parent` = USERS_DIR.
  - All 6 tests pass against current implementation (routes already exist). Unlike prior test batches, these are not written ahead — McManus had already implemented the routes.

- **2026-02-12 — Site-wide export/import tests added (`tests/test_app.py :: TestSiteExportImport`)**
  - 9 proactive tests for admin-only `GET /api/export/site` and `POST /api/import/site` endpoints.
  - Tests: non-admin forbidden (export + import), valid ZIP export, .secret_key inclusion, users data inclusion, full replace on import, path traversal rejection, missing users.yaml rejection, session clearing after import.
  - Uses `_make_site_zip()` module-level helper analogous to `_make_user_zip()`.
  - Introduces `_login_as_admin()` instance helper that: adds admin to users.yaml, creates admin user directory tree, writes `.secret_key` to `DATA_DIR`, switches client session to admin.
  - Admin check assumption: `is_admin()` returns True when `session['user'] == 'admin'`. Non-admin gets 302/303/403.
  - Directory layout for site export: `.secret_key` at `DATA_DIR/.secret_key`, `users.yaml` at `USERS_FILE`, user tree at `USERS_DIR`.
  - Written proactively before McManus implements the routes — tests will fail until endpoints are added.

- **2026-02-13 — Decision merged: `_login_as_admin()` is canonical admin test helper**
  - Per Hockney's decision (merged into `decisions.md`), future admin-only endpoint tests should reuse `TestSiteExportImport._login_as_admin()` rather than inventing their own setup.
  - If `is_admin()` logic evolves beyond `session['user'] == 'admin'`, update this single helper.

- **2026-02-13 — Delete account tests added (`tests/test_app.py :: TestDeleteAccount`)**
  - 5 tests covering `POST /api/delete-account`: success (user removed from users.yaml, directory deleted, session cleared), multi-tournament removal, admin prevention (403), unauthenticated redirect, and other-user isolation.
  - Admin setup follows canonical `_login_as_admin()` pattern from `TestSiteExportImport`.
  - Directory navigation: `USERS_DIR / "testuser"` for user dir, `USERS_FILE` for users.yaml.
  - Written proactively before McManus implements the route — tests will fail until the endpoint is added.

- **2026-02-13 — show_test_buttons constraint tests added (`tests/test_app.py :: TestShowTestButtons`)**
  - 5 tests covering the `show_test_buttons` boolean constraint: default False, toggle on via POST, toggle off (unchecked checkbox pattern), teams page hides test button by default, teams page shows test button when enabled.
  - Tests 1-3 validate constraint persistence through `load_constraints()` after form POSTs to `/constraints` with `action=update_general`.
  - Tests 4-5 check `loadTestTeams` presence/absence in `/teams` response HTML, depending on the constraint value.
  - McManus added `show_test_buttons: False` to `get_default_constraints()` and `'show_test_buttons' in request.form` to the `update_general` handler.
  - Fenster needs to wrap test buttons in `{% if show_test_buttons %}` in `teams.html` — test 4 will fail until that's done.

- **2026-02-13 — Awards feature tests added (`tests/test_app.py :: TestAwards`)**
  - 9 proactive tests covering the Awards CRUD lifecycle, image upload/serving, sample images endpoint, and export integration.
  - Tests: page loads (200), default empty (no `award-` ids in response), add award (JSON API + page verification), missing fields validation (400/422), delete by id, upload PNG via multipart form, serve uploaded image, samples list endpoint, awards.yaml in tournament ZIP export.
  - Uses `io.BytesIO` with minimal PNG byte sequences for image upload tests — no filesystem temp files needed.
  - Follows existing `client` + `temp_data_dir` fixture pattern; no new fixtures required.
  - Data model assumption: `awards.yaml` stored in tournament directory with `{'awards': [{'id': ..., 'name': ..., 'player': ..., 'image': ...}]}` structure.
  - API routes assumed: `GET /awards`, `POST /api/awards/add`, `POST /api/awards/delete`, `POST /api/awards/upload-image`, `GET /api/awards/image/<filename>`, `GET /api/awards/samples`.
  - Export test expects `awards.yaml` to appear in the ZIP returned by `GET /api/export/tournament`.
  - Written proactively before McManus implements the routes — tests will fail until endpoints are added.


- **2026-02-13 — show_test_buttons constraint tests added** (	ests/test_app.py :: TestShowTestButtons)
   - 5 tests covering the show_test_buttons boolean constraint: default False, toggle on via POST, toggle off (unchecked checkbox pattern), teams page hides test button by default, teams page shows test button when enabled.
   - Tests 1-3 validate constraint persistence through load_constraints() after form POSTs to /constraints with action=update_general.
   - Tests 4-5 check loadTestTeams presence/absence in /teams response HTML, depending on the constraint value.
   - McManus added show_test_buttons: False to get_default_constraints() and 'show_test_buttons' in request.form to the update_general handler.
   - Fenster needs to wrap test buttons in constraints.html.
