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

### 2026-02-11: Fixed first-deploy race condition in deploy.ps1
- **Problem**: `az webapp config set` and `az webapp config appsettings set` each trigger a container restart. When these ran BEFORE `az webapp deploy`, the container would boot mid-Oryx-build, find no artifacts, and crash. Second boot ~5 min later succeeded because the build had finished.
- **Fix**: Moved all three config blocks (startup command, app settings, SECRET_KEY) to AFTER the zip deploy retry loop. Removed the pre-deploy propagation sleep and added a post-deploy one instead. Updated retry loop comment to remove stale reference to config-triggered restarts.
- **Files changed**: `deploy.ps1`

### 2026-02-11: Separated config data from runtime data for Azure deploys
- **Problem**: Deploying the app to Azure overwrote user tournament data because `data/` was bundled in the zip package and lived under `/home/site/wwwroot/data`.
- **Fix**: Three surgical changes:
  1. `src/app.py`: `DATA_DIR` now reads from `TOURNAMENT_DATA_DIR` env var (falls back to `../data` for local dev). Moved `BASE_DIR`/`DATA_DIR` definitions above `_get_or_create_secret_key()` call so the function can use `DATA_DIR` for `.secret_key` path.
  2. `deploy.ps1`: Added `TOURNAMENT_DATA_DIR=/home/data` to Azure app settings. Removed the line that copied `data/` into the deploy zip.
  3. `startup.sh`: Added `mkdir -p` for the data dir before app startup.
- **Effect**: On Azure, runtime data lives in `/home/data` (persistent across deploys). Locally, behavior is unchanged — `DATA_DIR` defaults to `../data`.

### 2026-02-12: Tournament CRUD corner case fixes
- **Fix 1 — No-tournament guard**: Added a guard in `set_active_tournament()` that redirects logged-in users with no tournaments (and no active tournament) to the `/tournaments` page. Whitelisted endpoints: `tournaments`, `api_create_tournament`, `api_delete_tournament`, `api_switch_tournament`, `logout`, `api_export_tournament`, `api_import_tournament`.
- **Fix 2 — Session sync on delete**: When deleting the active tournament, the session's `active_tournament` is now set to the next available tournament instead of always being popped. Prevents stale session state when other tournaments exist.
- **Fix 3 — YAML error handling**: Wrapped `yaml.safe_load()` in `load_tournaments()` and `load_users()` with try/except. Corrupt YAML files now log a warning and return safe defaults instead of crashing.
- **Pattern**: Guard logic in `before_request` uses a set of whitelisted endpoint names — easy to extend when new tournament-management routes are added.
