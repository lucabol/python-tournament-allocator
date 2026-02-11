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
