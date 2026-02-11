# Project Context

- **Owner:** Luca Bolognese (lucabol@microsoft.com)
- **Project:** Python Flask tournament scheduling and management web application
- **Stack:** Python 3.11+, Flask, Jinja2, pandas, numpy, OR-Tools CP-SAT, PyYAML, pytest
- **Created:** 2026-02-11

## Learnings

<!-- Append new learnings below. Each entry is something lasting about the project. -->

### 2026-02-11: Multi-tournament infrastructure added
- **Architecture**: Tournament data lives in `data/tournaments/<slug>/` subdirectories. A top-level `data/tournaments.yaml` tracks the list and active tournament.
- **Path resolution**: All `load_*`/`save_*` functions use `_file_path(filename)` → `_tournament_dir()` → `g.data_dir` (set by `@app.before_request`). Fallback to `DATA_DIR` if outside request context.
- **Migration**: `ensure_tournament_structure()` runs in `before_request` (idempotent). Moves legacy flat files to `data/tournaments/default/`.
- **Testing pattern**: `temp_data_dir` fixture must create a stub `tournaments.yaml` to prevent migration from moving test files. Monkeypatch `TOURNAMENTS_FILE` and `TOURNAMENTS_DIR` alongside the legacy constants.
- **Key files**: `src/app.py` (all routes + infrastructure), `src/templates/tournaments.html` (CRUD UI), `src/templates/base.html` (nav includes tournament link + name).
- **CRUD routes**: `/tournaments` (list), `/api/tournaments/create|delete|switch` (POST). New tournaments get seeded with `constraints.yaml`, empty `teams.yaml`, and header-only `courts.csv`.
