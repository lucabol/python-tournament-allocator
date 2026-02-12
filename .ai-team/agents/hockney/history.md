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
