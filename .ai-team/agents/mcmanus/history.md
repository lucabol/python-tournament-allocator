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

### 2026-02-12: Public live tournament routes added
- **Routes**: Three new unauthenticated routes: `/live/<username>/<slug>`, `/api/live-html/<username>/<slug>`, `/api/live-stream/<username>/<slug>`. These allow spectators to view any tournament without logging in.
- **Helper**: `_resolve_public_tournament_dir(username, slug)` validates path components (no `..`, `/`, `\`) and checks directory existence under `USERS_DIR/<username>/tournaments/<slug>`.
- **Auth bypass**: Added `public_live`, `api_public_live_html`, `api_public_live_stream` to the `before_request` endpoint whitelist alongside `static`, `login_page`, `register_page`.
- **SSE stream**: Public stream builds watched file paths directly from `data_dir` instead of using `_file_path()` (which requires `g.data_dir` set by the auth flow).
- **Share URL**: The `/tracking` route now passes `share_url` to the template for organizers to copy/share.
- **Template flag**: Existing `/live` route now passes `public_mode=False`; public route passes `public_mode=True`, `public_username`, `public_slug` so the template can adjust (e.g., hide nav, change SSE URL).

### 2026-02-12: User-level export/import routes added
- **Routes**: `GET /api/export/user` and `POST /api/import/user`. Both require `@login_required`.
- **Export**: Reads `g.user_tournaments_file` to discover slugs, zips all tournament data (standard files + logos) into `<slug>/` subdirectories with `tournaments.yaml` at the root. Returns `user_export_{timestamp}.zip`.
- **Import**: Validates ZIP, reads `tournaments.yaml` from the root, extracts only `ALLOWED_IMPORT_NAMES` files and logos per slug into `g.user_tournaments_dir/<slug>/`. Merges the imported `tournaments.yaml` additively — new slugs are added, existing slugs get name/created updated, tournaments not in ZIP are preserved.
- **Whitelist**: Added `api_export_user` and `api_import_user` to the `tournament_endpoints` guard set in `before_request`.
- **Pattern**: Logo handling replicates the per-tournament pattern (glob for `logo.*`, delete old, extract new). Security checks mirror existing import route (path traversal, size limit).

### 2026-02-12: Site-wide export/import routes added
- **Routes**: `GET /api/export/site` and `POST /api/import/site`. Both require `@login_required` and `is_admin()` check (403 for non-admins).
- **Helper**: `is_admin()` returns `True` if `session.get('user') == 'admin'`. Placed near `login_required` decorator.
- **Export**: Walks `DATA_DIR` recursively, zips everything (`.secret_key`, `users.yaml`, `users/` directory) while skipping `__pycache__`, `.pyc`, and `.lock` files. Returns `site_export_{timestamp}.zip`.
- **Import**: Validates ZIP (path traversal, size ≤ 50MB, must contain `users.yaml`). Full replace: removes existing `users/` dir, `users.yaml`, `.secret_key`, then extracts ZIP into `DATA_DIR`. Clears Flask session and redirects to login page.
- **Whitelist**: Added `api_export_site` and `api_import_site` to the `tournament_endpoints` guard set in `before_request`.
- **Constants**: `MAX_SITE_UPLOAD_SIZE = 50MB`, `SITE_EXPORT_SKIP` set for filtering during walk.
- **Pattern**: Follows the same security checks as `api_import_user` (path traversal, zip validation, flash messages).

### 2026-02-13: Coordinator fix — site export/import derives site_root from USERS_FILE parent
- **Problem**: Export/import routes originally used `DATA_DIR` as the site root. When `DATA_DIR` pointed to a per-user or nested path, the export would miss `users.yaml` and `.secret_key` which sit at the site root.
- **Fix**: Both `api_export_site` and `api_import_site` now compute `site_root = os.path.dirname(USERS_FILE)` instead of using `DATA_DIR` directly.
- **Files changed**: `src/app.py`

### 2026-02-13: POST /api/delete-account route added
- **Route**: `POST /api/delete-account` with `@login_required`. Deletes the logged-in user's account, their data directory, and clears the session.
- **Admin guard**: Returns 403 if `session['user'] == 'admin'` to prevent admin self-deletion.
- **Data cleanup**: Uses `_data_lock` (FileLock) to atomically load/filter/save users list, then `shutil.rmtree` on `USERS_DIR/<username>`.
- **Whitelist**: Added `api_delete_account` to `tournament_endpoints` set in `before_request` so the route works even without an active tournament.
- **Files changed**: `src/app.py`
