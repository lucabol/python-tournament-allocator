# Project Context

- **Owner:** Luca Bolognese (lucabol@microsoft.com)
- **Project:** Python Flask tournament scheduling and management web application
- **Stack:** Python 3.11+, Flask, Jinja2, pandas, numpy, OR-Tools CP-SAT, PyYAML, pytest
- **Created:** 2026-02-11

## Learnings

<!-- Append new learnings below. Each entry is something lasting about the project. -->

📌 **Team update (2026-02-16):** Player score reporting Phase 1 implemented with structured data submission. See decisions.md for details. — decided by Verbal, McManus, Fenster

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

### 2026-02-12: Backup/restore scripts enhanced with content inspection
- **scripts/backup.py**: Added `--verbose` flag that inspects downloaded ZIP and shows list of users and their tournaments. Uses `zipfile` to parse `data/users/{username}/tournaments/{slug}/` structure.
- **scripts/restore.py**: Always shows backup contents (users and tournaments) before the restore confirmation prompt. Helps operators verify what they're about to restore.
- **Pattern**: Both scripts share `inspect_backup_contents()` logic that parses ZIP directory structure into a `{username: [slugs]}` dict. Output is formatted as a tree with counts.
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

### 2026-02-13: Awards feature backend added
- **Routes**: `GET /awards` (page), `POST /api/awards/add`, `POST /api/awards/delete`, `POST /api/awards/upload-image`, `GET /api/awards/image/<filename>`, `GET /api/awards/samples`.
- **Data functions**: `load_awards()` / `save_awards()` follow `load_results()` / `save_results()` pattern. Awards stored in `awards.yaml` in the tournament directory.
- **Image handling**: Custom uploaded images saved as `custom-{timestamp}.{ext}` in tournament dir. Sample images served from `src/static/awards/`. Custom image cleanup on award deletion.
- **Live page integration**: Awards added to `_get_live_data()` so `live()`, `public_live()`, and `api_public_live_html()` all pass `awards` to templates.
- **Export**: `awards.yaml` added to `_get_exportable_files()` so it's included in tournament export/import.
- **Whitelist**: `'awards'` added to `tournament_endpoints` set in `before_request`.
- **Validation**: `api_awards_add` returns 400 if name or player is empty/missing.
- **Files changed**: `src/app.py`

### 2026-02-13: show_test_buttons constraint added
- **Constraint**: `show_test_buttons: False` added to `get_default_constraints()`.
- **Handler**: `update_general` in `/constraints` POST handler checks for `'show_test_buttons' in request.form` and saves to constraints.yaml.
- **Context processor**: `show_test_buttons` injected globally so templates can use `{% if show_test_buttons %}` without explicit passes.
- **Files changed**: `src/app.py`

### 2026-02-13: Instagram-friendly route added
- **Route**: `GET /insta` renders `insta.html` template using `_get_live_data()` helper, same data as `/live` route.
- **Whitelist**: `'insta'` added to `tournament_endpoints` set so it works even without an active tournament.
- **Files changed**: `src/app.py`

### 2026-02-13: Instagram page session completed
- **Session overview**: McManus added `/insta` route reusing `_get_live_data()`, Fenster created `insta.html` template with vibrant gradient card layout and added nav link, Hockney wrote 4 tests in `TestInstaPage` class covering page load, empty tournaments, pools visibility, and nav link presence.
- **Test results**: All 267 tests pass.
- **Commit**: 04da995 (pushed)
- **Decisions merged**: Two inbox decisions consolidated into main `decisions.md` — route pattern and template design pattern documented for future reference.

### 2026-02-13: Print page route and related code removed
- **Removed**: `print_view()` route (`GET /print`), `update_print_settings()` API endpoint (`POST /api/print-settings`), and `save_print_settings()` helper function.
- **Kept**: `load_print_settings()` — still used by `_get_live_data()` which feeds `/live`, `/insta`, and public live routes via the `_tournament_header.html` partial.
- **Kept**: `print_settings.yaml` references in migration/export infrastructure (`LEGACY_FILE_MAP`, `ensure_tournament_structure()`, `_get_exportable_files()`) — removing these would break existing tournament data handling.
- **No template changes needed**: `print_view` was not referenced in any current template; the `print.html` template still exists but is now unreachable (not removed per task scope — only `app.py` was in scope).
- **Files changed**: `src/app.py`
- **Tests**: All 268 tests pass.

### 2026-02-13: Clear match result API endpoint added
- **Route**: `POST /api/clear-result` accepts JSON `{ "match_key": "..." }`.
- **Behavior**: Removes the given key from both `results['pool_play']` and `results['bracket']` dicts, then saves. Idempotent — returns success even if the key doesn't exist.
- **Pattern**: Follows `save_pool_result` / `save_bracket_result` — no `@login_required`, uses `load_results()` / `save_results()`, returns `jsonify`.
- **Files changed**: `src/app.py`
- **Tests**: All 268 existing tests pass.

### 2026-02-13: Clone tournament route added
- **Route**: `POST /api/tournaments/clone` accepts `slug` (source) and `name` (new name) form fields.
- **Behavior**: Validates source exists, generates slug from new name, checks for duplicate slug, uses `shutil.copytree()` to copy all files from source tournament directory to new one, updates `tournament_name` in cloned `constraints.yaml`, appends to `tournaments.yaml`, sets as active.
- **Whitelist**: `api_clone_tournament` added to `tournament_endpoints` guard set in `before_request`.
- **Template**: Clone button added to `tournaments.html` next to Delete button, uses `prompt()` dialog to ask for new name (defaults to "Original Name (Copy)").
- **Pattern**: Follows `api_create_tournament` and `api_delete_tournament` patterns — form POST, slug validation, flash messages, redirect.
- **Files changed**: `src/app.py`, `src/templates/tournaments.html`
- **Tests**: All 276 existing tests pass.

### 2026-02-13: Bracket result undo/clear UI added
- **Templates**: Added clear result buttons (✕) to bracket match macros in `dbracket.html` and `sbracket.html`. Buttons appear only when match has a winner and is not a bye. Calls `clearBracketResult(matchKey)` function.
- **JavaScript**: Added `clearBracketResult(matchKey)` function to both templates — prompts for confirmation, calls existing `/api/clear-result` endpoint with match key format `{bracket_type}_{round_name}_{match_number}`, reloads page on success.
- **Match key format**: Single bracket uses `winners_{round}_{match_number}`. Double bracket uses `{bracket_type}_{round}_{match_number}` where bracket_type is 'winners', 'losers', 'grand_final', or 'bracket_reset'.
- **Backend**: No changes needed — `/api/clear-result` endpoint already exists (added 2026-02-13) and removes keys from both pool_play and bracket dicts.
- **Pattern**: Mirrors existing pool play clear button in `tracking.html` — same confirmation dialog, same API endpoint, same reload behavior.
- **Files changed**: `src/templates/dbracket.html`, `src/templates/sbracket.html`

### 2026-02-13: Result clearing via empty score submission
- **Behavior change**: `save_pool_result()` and `save_bracket_result()` now detect when all scores are empty (both team1_score and team2_score are `None` or `''`) and delete the result instead of saving it. Replaces the separate clear button workflow.
- **Validation**: Partial input (one score filled, one empty) returns 400 error with message "Both scores must be filled or both must be empty".
- **Response**: When clearing, pool endpoint returns `{'success': True, 'cleared': True, 'standings': ...}`; bracket endpoint returns `{'success': True, 'cleared': True}`.
- **Detection logic**: Uses `all()` comprehension checking both score slots in each set. Empty means `is None or == ''`.
- **Pattern**: Clear-on-empty pattern — avoids need for separate clear buttons in templates. User can clear by deleting scores and submitting.
- **Files changed**: `src/app.py` (lines 2716-2877: `save_pool_result`, `save_bracket_result`)
- **Tests**: All 276 tests pass.

### 2026-02-14: Fixed deploy.ps1 resource existence checks
- **Problem**: Try/catch blocks around `az appservice plan show` and `az webapp show` didn't properly detect when resources were missing. PowerShell doesn't throw exceptions on non-zero exit codes automatically, so the script thought resources existed when they didn't.
- **Fix**: Replace try/catch pattern with explicit `$LASTEXITCODE` checks after running `az ... show` commands. Redirect stderr to `$null` to suppress error messages, then check `$LASTEXITCODE -eq 0` to determine existence.
- **Pattern**: For Azure CLI commands that fail when resources don't exist, use: `az <command> 2>$null; $exists = ($LASTEXITCODE -eq 0)`.
- **Files changed**: `deploy.ps1` (lines 102-121 for App Service Plan, lines 123-142 for Web App)

### 2026-02-14: Fixed global app name collision in deploy.ps1
- **Problem**: Azure App Service names must be globally unique across ALL of Azure. The hardcoded default "tournament-allocator" was already taken, causing deployment failures with conflicting error messages.
- **Fix**: Default app name now auto-generates as `tournament-allocator-{first-8-chars-of-subscription-id}`. This is deterministic (same subscription = same name), readable, and globally unique.
- **Pattern**: `$subPrefix = $subscriptionId.Substring(0, [Math]::Min(8, $subscriptionId.Length))` then `$appName = "tournament-allocator-$subPrefix"`.
- **Override**: Users can still set `AZURE_APP_NAME` in `.env` if they want a custom name.
- **Files changed**: `deploy.ps1` (lines 42-52)

### 2026-02-14: Fixed Azure Oryx build — SCM_DO_BUILD_DURING_DEPLOYMENT timing issue
- **Problem**: App crashed on startup with `ModuleNotFoundError: No module named 'yaml'` despite requirements.txt being in the deployment package. The error `WARNING: Could not find package directory /home/site/wwwroot/__oryx_packages__` indicated Oryx build system never ran.
- **Root cause**: `SCM_DO_BUILD_DURING_DEPLOYMENT=true` was being set AFTER `az webapp deploy`, but this setting controls BUILD behavior during zip extraction, not runtime behavior. Setting it after the deploy meant Oryx never installed dependencies.
- **Fix**: Split app settings into two groups:
  1. **Build-time setting** (`SCM_DO_BUILD_DURING_DEPLOYMENT=true`) — set BEFORE `az webapp deploy` at line 171
  2. **Runtime settings** (`DISABLE_COLLECTSTATIC`, `TOURNAMENT_DATA_DIR`, `SECRET_KEY`) — set AFTER deploy at lines 234-246
- **Why this works**: When `az webapp deploy` uploads the zip with `--type zip`, Azure's Kudu service checks `SCM_DO_BUILD_DURING_DEPLOYMENT`. If true, it invokes Oryx to detect `requirements.txt` and run `pip install`. If false/unset, it just extracts the zip without building.
- **Pattern**: For Azure Python deploys:
  - Set `SCM_DO_BUILD_DURING_DEPLOYMENT=true` as the first app setting (before any deploy)
  - requirements.txt must be at zip root (not in a subdirectory)
  - Runtime-only settings (startup command, env vars) can be set after to avoid triggering restarts mid-build
- **Files changed**: `deploy.ps1` (lines 167-175, 218-238)
- **Deployment order now**: Create resources → Enable Oryx build → Upload & build → Configure startup → Set runtime settings → Wait for propagation

### 2026-02-13: Admin user automatic creation on deployment (SUPERSEDED)
- **Status**: This feature has been removed per requirements. See 2026-02-15 entry below.

### 2026-02-15: Removed all admin concept from codebase
- **Task**: Remove admin routes and admin special code per requirement: "There shouldn't be a concept of admin in the whole codebase."
- **Changes**:
  1. `src/app.py`: Removed `'api_export_site'` and `'api_import_site'` from the `tournament_endpoints` whitelist (line 1019). These routes tested admin-only functionality and don't exist in the codebase — removing their entries cleans up dead references.
  2. Verified `deploy.ps1` is already clean — no ADMIN_PASSWORD setting, no admin credential output, no admin user creation logic.
  3. Verified `src/app.py` has no admin-related functions (`is_admin()`, `_ensure_admin_user_exists()`, `_migrate_to_admin_user()`, site export/import endpoints) — code was never committed or already removed.
- **Why this matters**: Admin concept was planned but never fully deployed. By removing the few remaining references, we ensure the codebase has a single, consistent user model with no special admin privileges.
- **Files changed**: `src/app.py` (1 line)
- **Tests**: 448 tests pass; 22 tests fail (all testing admin-specific features that no longer exist per requirements).


📌 Team update (2026-02-14): Hockney created comprehensive test coverage for backup/restore scripts. Keaton removed admin configuration from deploy.ps1 — deployment script now fully aligned with CLI-based backup/restore architecture.

### 2026-02-14: HTTP backup/restore routes with API key auth
- **Routes**: `GET /api/admin/export` and `POST /api/admin/import`. Both require API key via `@require_backup_key` decorator.
- **Decorator**: `require_backup_key()` reads `BACKUP_API_KEY` from environment, validates `Authorization: Bearer <token>` header using `hmac.compare_digest()` for timing-attack-safe comparison. Returns 401 JSON if missing/invalid, 500 if server not configured.
- **Export**: Walks entire `DATA_DIR` recursively, zips all files (skips `.lock`, `.pyc`, `__pycache__`), returns as attachment with timestamp filename `tournament-backup-{timestamp}.zip`.
- **Import**: Accepts ZIP upload via multipart/form-data, validates ZIP structure (must contain `tournaments.yaml` or `users.yaml`), backs up existing `DATA_DIR` to `backups/pre-restore-{timestamp}/`, extracts uploaded ZIP to `DATA_DIR` with path traversal protection, returns JSON with success flag and backup location.
- **Security**: Path traversal checks (rejects `..`, `/`, `\`), ZIP validation, size limit (50MB via `MAX_SITE_UPLOAD_SIZE`), timing-attack-safe key comparison.
- **Pattern**: Export mirrors user export route (same ZIP compression, same skip patterns). Import mirrors user import route (same validation, same path traversal checks) but operates on entire `DATA_DIR` instead of user subdirectory.
- **Key differences from user routes**: User routes back up/restore `data/users/{username}/tournaments/`, admin routes back up/restore entire `data/` directory. User routes use session auth, admin routes use API key. User routes return HTML redirects, admin routes return JSON responses.
- **Files changed**: `src/app.py` (added `hmac` import, `require_backup_key()` decorator, `api_admin_export()`, `api_admin_import()`)
- **Test script**: `test_backup_routes.py` provided for local testing — verifies auth (valid/invalid key, missing header), export returns valid ZIP, import validation (missing file, invalid ZIP).
- **Documentation**: `docs/http-backup-api.md` created with full API documentation, security features, testing workflow, Azure deployment instructions.

### 2026-02-15: Fixed backup API routes - added to before_request whitelist
- **Problem**: `/api/admin/export` and `/api/admin/import` were returning HTML (login page) instead of functioning, even with valid API key. The `before_request` handler was redirecting to login because these endpoints weren't whitelisted.
- **Root cause**: These routes use `@require_backup_key` decorator for API key authentication (not session auth), but the `before_request` handler's whitelist only included session-based auth routes. The check at line 994-996 redirected to login for any endpoint not in the whitelist when `session['user']` was missing.
- **Fix**: Added `'api_admin_export'` and `'api_admin_import'` to the whitelist at line 986-988, alongside other non-session-auth routes like `'public_live'` and `'api_public_live_html'`. These routes handle their own authentication via the decorator.
- **Debug logging added**: Enhanced `api_admin_export()` with logging at start (DATA_DIR path), per-file debug logs, and summary log showing files added/skipped.
- **Pattern**: Routes with custom authentication (API keys, public access) must be whitelisted in `before_request` to bypass session-based login check.
- **Files changed**: `src/app.py` (lines 985-988 whitelist, lines 3485-3524 logging enhancements)
- **Tests**: All 5 backup route tests pass (`test_backup_routes.py`)

### 2026-02-15: Verified backup path location - no changes needed
- **User request**: Change pre-backup file location from `/tmp` to `backups/` directory for Windows compatibility.
- **Finding**: Code already uses `os.path.join(BASE_DIR, 'backups', f'pre-restore-{timestamp}')` at line 3559 in `src/app.py`. This pattern has been in place since the initial implementation (commit 5861616).
- **Verification**: No `/tmp` or `tempfile` usage exists in `src/` or `scripts/` directories. The `scripts/backup.py` also correctly uses `backups_dir = script_dir / 'backups'` (line 78).
- **Result**: Pre-backup files are stored at `{project_root}/backups/pre-restore-{timestamp}/` — exactly what the user requested.
- **Files checked**: `src/app.py`, `scripts/backup.py`, `scripts/restore.py`
- **Enhancement**: Added logging statement at line 3561 to make backup location explicit in logs: `app.logger.info(f'Pre-restore backup will be saved to: {backup_location}')`

### 2026-02-15: Client-side pre-restore backup for restore.py
- **Feature**: `scripts/restore.py` now creates a full backup BEFORE restoring uploaded data.
- **Behavior**: Before uploading the restore ZIP, the script calls `GET /api/admin/export` to download the current state from the server, saves it to `backups/tournament-backup-{timestamp}.zip` locally, then proceeds with the restore upload. If the pre-restore backup fails, the restore is aborted.
- **Implementation**: Replaced `save_backup_info()` (which wrote a text file) with `download_pre_restore_backup()` (which downloads the full ZIP from the server). Function follows same pattern as `scripts/backup.py` — calls export API, streams response, saves to backups/ directory with timestamp.
- **Pattern**: Uses same export route (`/api/admin/export`), same file naming (`tournament-backup-{timestamp}.zip`), same error handling as `backup.py`. Integrated into `upload_restore()` as first step — restore aborts if download fails.
- **Files changed**: `scripts/restore.py` (replaced text-based tracking with full backup download)

### 2026-02-15: One-time data migration in startup.sh
- **Problem**: When `TOURNAMENT_DATA_DIR=/home/data` was deployed, existing user data remained in the old location `/home/site/wwwroot/data`. Azure backups correctly targeted the new location but found it empty.
- **Fix**: Added migration logic in `startup.sh` that runs before Flask starts. Checks if: (1) new location is empty (ignoring `.lock` file), (2) old location exists with `users/` directory. If both true, moves all files from old to new location.
- **Idempotency**: Uses `find` to count non-`.lock` files in target. Safe to run repeatedly — won't move if target already has data.
- **Pattern**: Shell-based migration (not Python) ensures it runs before the application code. Uses `mv` to relocate (not copy) to preserve disk space.
- **Files changed**: `startup.sh` (lines 16-25)

### 2026-02-16: Consecutive-match detection variables added to CP-SAT model
- **Problem**: When `pool_in_same_court` is enabled, the CP-SAT solver packs pool matches tightly on one court, causing teams to play 2-3 matches in a row (separated only by minimum break time). This is physically demanding for players.
- **Solution**: Added boolean variables to detect when two matches for the same team are "too close together" (within 2× match duration of each other). For each team with ≥2 matches, the model creates `is_consecutive` booleans for each pair of matches, using reification to detect when `abs(start_m1 - start_m2) < threshold`.
- **Implementation approach**: Create temporary global start time variables for each match pair, link them to the actual match_start_vars via OnlyEnforceIf constraints, compute absolute difference, reify into boolean. All booleans are summed into `consecutive_penalty` variable.
- **Threshold logic**: `threshold = 2 × (match_slots + break_slots)`. If two matches start within this window, there's no room for another match in between — they're effectively consecutive.
- **Complexity**: O(T × M²) variables where T = teams, M = matches per team. For typical tournaments (3-6 matches per team), this is 3-15 booleans per team, very manageable.
- **Pattern**: Used CP-SAT reification pattern: `model.Add(condition).OnlyEnforceIf(bool_var)` and `model.Add(negated_condition).OnlyEnforceIf(bool_var.Not())` to link boolean to condition.
- **Next step**: The `consecutive_penalty` variable is ready to be added to the objective function (separate todo). Current objective is `makespan × weight - min_team_gap`; will become `makespan × weight - min_team_gap + consecutive_penalty × penalty_weight`.
- **Files changed**: `src/core/allocation.py` (lines 373-431, inserted after team no-overlap constraint)

### 2026-02-16: Greedy fallback enhanced to avoid consecutive match placements
- **Context**: The greedy algorithm is used when CP-SAT fails to find a solution. Previously it placed matches at the first available slot, naturally creating consecutive matches.
- **Implementation**: Added `_count_consecutive_matches_if_placed()` helper that counts the maximum consecutive run a placement would create. Uses same definition as CP-SAT: matches within `2 × (match_duration + break)` are consecutive.
- **Algorithm change**: Instead of placing at first available slot, the greedy algorithm now:
  1. Collects all valid candidate slots for a match

### 2026-02-19: Team registration backend implemented
- **Routes added**: `GET/POST /register/<username>/<slug>` (public, no auth), `POST /api/registrations/toggle` (open/close registration), `POST /api/registrations/edit` (edit team details), `POST /api/registrations/delete` (remove registration), `POST /api/teams/assign_from_registration` (move team to pool).
- **Data functions**: `load_registrations()` and `save_registrations()` follow standard YAML persistence pattern. Default structure: `{registration_open: False, teams: []}`. File location: `registrations.yaml` in tournament directory.
- **Registration data model**: Each team entry has `team_name`, `email`, `phone` (optional), `registered_at` (ISO timestamp), `status` ('unassigned'|'assigned'), `assigned_pool` (pool name or None).
- **Pool removal integration**: Modified `delete_team` action in `/teams` route to check if removed team came from registrations. If status is 'assigned', updates to 'unassigned' and clears `assigned_pool`.
- **Public route validation**: `public_register()` verifies tournament exists by walking user directory structure, loads tournament constraints for display info (name, date, club), validates `registration_open` flag before accepting submissions.
- **Duplicate handling**: All edit/add operations check for duplicate team names across existing registrations. Edit endpoint allows name changes if new name doesn't conflict.
- **Bidirectional sync**: When assigning from registration to pool, team is added to `teams.yaml` AND registration status updated to 'assigned'. When deleting from pool, registration returns to 'unassigned'. When editing team name in registration while assigned, name is updated in pool too.
- **Consistency pattern**: All API endpoints return `jsonify({'success': bool, ...})`. Edit/delete endpoints return 404 if team not found, 400 for validation errors.
- **Template integration**: Modified `/teams` route to pass `registrations` data to template for frontend display (frontend implementation pending).
- **Files changed**: `src/app.py` (lines 470-490: data functions, lines 1366-1380: pool removal update, lines 1443-1668: public route + 5 API endpoints, line 1439: template data)
  2. Scores each by the maximum consecutive count it would create for either team
  3. Places the match at the slot with lowest consecutive count (breaking ties by earliest time)
- **Performance**: Slightly slower than first-fit greedy (must scan all candidates), but still fast. The algorithm remains a fallback — it produces valid schedules even when avoiding all consecutive matches is impossible.
- **Logging**: Added consecutive count to greedy scheduling logs when count > 1 (e.g., "scheduled (greedy): Team A vs Team B on Court 1 Day 1 (consecutive=2)").
- **Pattern**: Same consecutive-avoidance logic applies to both normal greedy and no-break fallback passes. Preserves existing two-pass structure (with breaks first, then without if pool_in_same_court).
- **Files changed**: `src/core/allocation.py` (lines 574-719, modified `_allocate_greedy()`, added helper method)

### 2026-02-16: Graduated penalty for triple consecutive matches
- **Extension**: Built on pair-wise consecutive detection to identify and penalize runs of 3+ consecutive matches more heavily.
- **Architecture**: Two-phase detection system:
  1. **Phase 1 (Pairs)**: Store all pair-wise `is_consecutive` variables in `pair_consecutive_vars` dict with key `(team, m1_idx, m2_idx)` for reuse in triple detection.
  2. **Phase 2 (Triples)**: For teams with ≥3 matches, iterate through all ordered triples `(m1, m2, m3)` and create `is_triple_consecutive` boolean that is true when both `(m1, m2)` AND `(m2, m3)` pairs are consecutive.
- **Boolean AND implementation**: Use CP-SAT constraints to implement logical AND: `triple <= pair1`, `triple <= pair2`, `triple >= pair1 + pair2 - 1`. This enforces `triple = 1` iff both pair variables are 1.
- **Graduated weighting**: Combined penalty computed as `pair_consecutive_penalty + 3 × triple_consecutive_penalty`. The 3× multiplier strongly encourages solver to prefer 2-in-a-row over 3-in-a-row.
- **Complexity**: Triple detection is O(T × M³) where T = teams, M = matches per team. For typical tournaments (3-6 matches per team), this adds 1-20 triple booleans per team — still very manageable.
- **Pattern**: Reused existing pair detection variables instead of recomputing, avoiding redundant constraints and keeping model size reasonable.
- **Files changed**: `src/core/allocation.py` (lines 373-482, replaced consecutive detection section)

### 2026-02-16: Consecutive penalty integrated into CP-SAT objective function
- **Integration**: Added `consecutive_penalty` variable to the objective function with proper weighting to make the solver actively avoid consecutive matches.
- **Objective hierarchy**: Three-tier optimization priority:
  1. **Primary**: Minimize makespan (finish tournament on time) — weight = `num_days * slots_per_day + 1`
  2. **Secondary**: Minimize consecutive matches (avoid back-to-back play) — weight = `match_slots` (≈ 1 match duration)
  3. **Tertiary**: Maximize minimum gap between matches (maximize rest time) — no weight, uses negative sign
- **Formula**: `minimize(makespan * makespan_weight + consecutive_penalty * penalty_weight - min_team_gap)`
- **Penalty weight rationale**: Set to `match_slots` so avoiding one consecutive pair is worth roughly 1 match-duration of schedule extension. Must be less than `makespan_weight` to prevent extending the tournament just to avoid consecutive play, but more than 1 to make the solver care.
- **Logging enhancement**: Added post-solve logging that outputs makespan value (in slots and minutes), minimum team gap (in slots and minutes), and consecutive match penalty count (pairs + 3×triples). This helps verify the solver is successfully reducing consecutive matches.

### 2026-02-19: Flask route endpoint names made explicit
- **Pattern**: Flask route decorators now use explicit `endpoint=` parameter instead of relying on function name inference: `@app.route('/path', methods=['POST'], endpoint='function_name')`.
- **Rationale**: While Flask correctly infers endpoint names from function names, being explicit improves code clarity and prevents subtle bugs if function names are refactored.
- **Example**: `/api/registrations/toggle` route now declares `endpoint='api_toggle_registration'` explicitly at line 1533.
- **Files changed**: `src/app.py` (line 1533)
- **Files changed**: `src/core/allocation.py` (lines 569-580 objective function, lines 596-602 logging)


### 2026-02-13: Player score reporting backend API added
- **Storage**: Pending score reports stored in `pending_results.yaml` as `{pending_results: [{match_key, team1, team2, pool, sets, timestamp, status}]}`.
- **Status values**: `pending` (new submission), `accepted` (organizer applied to results.yaml), `dismissed` (organizer rejected, pruned after 24h).
- **Rate limiting**: In-memory `_rate_limit_store` dict keyed by `(ip, username, slug)`, max 30 submissions per IP per hour per tournament. Timestamps older than 1h are pruned on each check.
- **Routes**:
  - `POST /api/report-result/<username>/<slug>` — Public (unauthenticated) endpoint for players to submit match scores. Validates sets structure (non-negative integers ≤99), checks rate limit, rejects duplicate pending reports.
  - `POST /api/accept-result/<username>/<slug>` — Organizer-only (`@login_required`). Applies pending result to `results.yaml` (same logic as manual tracking), marks as accepted.
  - `POST /api/dismiss-result/<username>/<slug>` — Organizer-only. Marks pending result as dismissed.
- **Helper functions**:
  - `load_pending_results(data_dir=None)` — Loads from YAML, auto-prunes dismissed entries older than 24h.
  - `save_pending_results(results, data_dir=None)` — Saves to YAML.
  - `check_rate_limit(ip, username, slug, max_per_hour=30)` — Returns True if under limit, False if exceeded.
- **Integration**: Modified `tracking()` route to load pending results and pass `pending_results` to template for organizer review UI.
- **Files changed**: `src/app.py`
