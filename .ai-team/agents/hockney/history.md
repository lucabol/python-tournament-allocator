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
