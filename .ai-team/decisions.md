# Decisions

> Shared decision log. All agents read this before starting work. Scribe maintains it.

<!-- Decisions are appended below. Each entry starts with ### -->

---

## Multi-Tournament Architecture (2026-02-11)

### Tournament data stored as subdirectories under data/tournaments/
**By:** Verbal
**What:** Each tournament gets its own subdirectory (`data/tournaments/<slug>/`) containing the same set of files (`teams.yaml`, `courts.csv`, `constraints.yaml`, `results.yaml`, `schedule.yaml`, `print_settings.yaml`, `logo.*`). A top-level `data/tournaments.yaml` tracks the list of tournaments and the currently active one.
**Why:** Keeps the existing file-based architecture. Each tournament is self-contained, directly exportable as a ZIP (matches existing export/import feature), and requires no database. Simplest approach that works.

### Tournaments identified by user-chosen name converted to filesystem slug
**By:** Verbal
**What:** Users provide a display name. The system generates a filesystem-safe slug (lowercase, hyphens, no special chars) used as the directory name and internal identifier. Duplicate slugs are rejected at creation time.
**Why:** Human-readable, filesystem-safe, simple. UUIDs would be opaque and unfriendly. The display name is already stored in `constraints.yaml` as `tournament_name`.

### Session-based active tournament (not URL-prefixed)
**By:** Verbal
**What:** The active tournament slug is stored in the Flask session. All existing routes stay unchanged — a `@app.before_request` hook sets `g.data_dir` to the active tournament's directory. New routes added only for tournament management (`/tournaments`, `/api/tournaments/*`).
**Why:** URL-prefixing every route (`/tournament/<slug>/teams`, etc.) would require rewriting ~30 route decorators, every `url_for()` in every template, and every test. Session-based requires one hook, parameterized file paths, and a few new routes — estimated 10x less code churn. Trade-off: no bookmarkable tournament URLs, acceptable for single-organizer use case.

### Legacy data auto-migrated to "default" tournament on first startup
**By:** Verbal
**What:** On first startup with new code, if `data/` contains old-format flat files, automatically move them into `data/tournaments/default/` and create `data/tournaments.yaml`. Zero manual migration required.
**Why:** Zero-disruption upgrade path. Existing users keep their data without any manual steps.

### File paths parameterized via g.data_dir and _file_path() helper
**By:** Verbal
**What:** Replace module-level file path constants (`TEAMS_FILE`, `COURTS_FILE`, etc.) with a `_file_path(filename)` function that resolves against `g.data_dir`. The `before_request` hook sets `g.data_dir` from the session's active tournament.
**Why:** Minimal change to existing `load_*/save_*` functions — each swaps a constant for a function call, no signature changes. Tests can monkeypatch `g.data_dir` instead of 8+ individual constants.

### Multi-tournament backend — test fixture pattern
**By:** McManus
**What:** Implemented multi-tournament infrastructure in `src/app.py`: `_file_path()` helper, `_tournament_dir()`, `ensure_tournament_structure()` migration, `@app.before_request` hook setting `g.data_dir`, tournament CRUD routes, and `@app.context_processor` for template context. The `temp_data_dir` test fixture must pre-create `tournaments.yaml` with `{'active': None, 'tournaments': []}` so `ensure_tournament_structure()` skips migration; without this, migration moves test data files into `tournaments/default/`, breaking flat-file test layout.
**Why:** Documents the required test setup pattern. All 191 tests pass with this fixture.

---

## UI Decisions (2026-02-11)

### Tournament link placement in navbar
**By:** Fenster
**What:** "Tournaments" nav link is placed first (before Dashboard) since it's the entry point for selecting which tournament to work on. The nav brand text dynamically shows the active tournament name via the `tournament_name` context variable, falling back to "Tournament Allocator" when none is set.
**Why:** Users need to see at a glance which tournament they're working on. Putting the selector first makes it discoverable and the brand text makes it always visible.
**Affected files:** `src/templates/base.html`, `src/static/style.css`

---

## Deployment & Infrastructure (2026-02-11)

### DATA_DIR configurable via TOURNAMENT_DATA_DIR env var
**By:** McManus
**What:** `DATA_DIR` in `src/app.py` is sourced from the `TOURNAMENT_DATA_DIR` environment variable, falling back to `os.path.join(BASE_DIR, 'data')` for local development. On Azure, `deploy.ps1` sets `TOURNAMENT_DATA_DIR=/home/data` and no longer bundles `data/` in the deploy zip. `startup.sh` ensures the directory exists on first boot.
**Why:** Deploys were overwriting user tournament data. Azure's `/home` filesystem is persistent across deploys, but `/home/site/wwwroot` is replaced on each deploy. Moving runtime data to `/home/data` keeps it safe.
**Impact:** Local dev unchanged. Azure data at `/home/data`. First deploy after this change starts with empty data dir — migration code creates the default tournament automatically.

### deploy.ps1: Config calls moved after zip deploy
**By:** McManus
**Date:** 2026-02-12
**What:** Reordered `deploy.ps1` so that all `az webapp config set` / `az webapp config appsettings set` calls run after `az webapp deploy` succeeds, not before. Deploy order is now: create resources → zip package → upload & build → configure → propagation wait → cleanup.
**Why:** Each config change triggers an async container restart on Azure App Service. On first deploy, the Oryx remote build takes several minutes. If config triggers a restart before the build completes, the container boots with no artifacts and crashes. Moving config after deploy ensures build artifacts exist when the first config-triggered restart happens.

---

## CRUD Corner Cases (2026-02-12)

### Tournament CRUD corner case fixes
**By:** McManus
**What:** Three surgical fixes in `src/app.py`: (1) Guard in `set_active_tournament()` redirects users with no tournaments to `/tournaments` page, whitelisting only tournament-management and auth endpoints. (2) `api_delete_tournament()` now syncs the session to the next available tournament instead of always clearing it. (3) `load_tournaments()` and `load_users()` wrap `yaml.safe_load()` in try/except to handle corrupt YAML gracefully.
**Why:** Without fix 1, users with no tournaments could navigate to any route and hit errors from missing `g.data_dir`. Without fix 2, deleting the active tournament when others exist left the session stale — the user appeared to have no active tournament until page refresh. Without fix 3, a single corrupt YAML file could crash the entire app on any request.

---

## Public Live Tournament Routes (2026-02-12)

### Public (unauthenticated) routes for spectators at /live/<username>/<slug>
**By:** McManus
**Date:** 2026-02-12
**What:** Added `_resolve_public_tournament_dir()` helper, 3 public route handlers (`public_live`, `api_public_live_html`, `api_public_live_stream`), updated `before_request` whitelist, added `public_mode` flag to existing `/live` route, added `share_url` to `/tracking` template context. No new files created — reuses existing `live.html` and `live_content.html` templates with the `public_mode` flag for conditional rendering.
**Why:** Spectators and players need to follow a tournament in real time without needing an account. URL pattern `/<username>/<slug>` is simple, shareable, and bookmarkable. Path validation mirrors the existing `api_delete_tournament` pattern to prevent traversal attacks. The SSE stream builds file paths directly to avoid coupling to the auth-gated `g.data_dir` flow.
**Impact:** Read-only access only. Three new endpoints bypass `before_request` auth check. `public_mode` variable available in `live.html`. 228 existing tests pass.

---

## User Export/Import (2026-02-12)

### User-level export/import uses additive merge for tournaments.yaml
**By:** McManus
**Date:** 2026-02-12
**What:** `POST /api/import/user` merges the imported `tournaments.yaml` with the existing one additively — new tournament slugs are appended, existing slugs get their `name` and `created` fields updated, and tournaments not present in the ZIP are preserved. This differs from the single-tournament import which is a full replace.
**Why:** Full replace would silently delete tournaments the user has locally but didn't include in the ZIP. Additive merge is safer for a bulk operation — you can import a subset without losing data. The trade-off is that there's no "clean import" path, but that can be achieved by deleting tournaments manually first.

### User export/import endpoints added to before_request whitelist
**By:** McManus
**Date:** 2026-02-12
**What:** `api_export_user` and `api_import_user` are added to the `tournament_endpoints` guard set in `set_active_tournament()`. These routes work even when the user has no active tournament (since they operate on the user-level tournaments registry, not a specific tournament).
**Why:** Without whitelisting, users with no tournaments would be redirected to `/tournaments` before these routes could execute. The export route needs to work even with zero tournaments (returns an empty zip with just the registry), and the import route is how a user would restore tournaments.

---

## Site Export/Import (2026-02-13)

### Site-wide export/import uses full replace strategy
**By:** McManus
**Date:** 2026-02-13
**What:** `POST /api/import/site` does a full replace of `users/`, `users.yaml`, and `.secret_key` in DATA_DIR before extracting the ZIP. After import, the Flask session is cleared and the user is redirected to the login page. This differs from user-level import which does additive merge.
**Why:** Site export/import is for platform migration — you want an exact copy of the source site, not a merge. Full replace is the only thing that makes sense when you're moving the entire platform. Clearing the session forces re-login because user credentials and secret key may have changed. The 50MB size limit (vs 10MB for user imports) accounts for multi-user data.

### Site admin backup/restore UI uses typed-confirmation pattern
**By:** Fenster
**Date:** 2026-02-13
**What:** The site-level import (replace all data) requires the user to type "REPLACE" in a `prompt()` dialog, not just click OK in a `confirm()`. This is a deliberate UX escalation — the action destroys all user data site-wide, so the friction should match the severity. The section is gated behind `{% if current_user == 'admin' %}` and visually distinct with a red danger-zone border.
**Why:** A simple confirm dialog is too easy to click through accidentally. Typing a specific word forces the admin to pause and read. This pattern should be reused for any future site-wide destructive action.
**Affected files:** `src/templates/tournaments.html`, `src/static/style.css`

### Site export/import test pattern: admin login helper
**By:** Hockney
**Date:** 2026-02-13
**What:** `TestSiteExportImport._login_as_admin()` is the canonical pattern for tests that need admin privileges. It adds admin to `users.yaml`, creates the admin user directory tree, writes `.secret_key` to `DATA_DIR`, and switches the client session to `'admin'`. Future admin-only endpoint tests should reuse this pattern rather than inventing their own setup.
**Why:** The existing `client` fixture always logs in as `testuser`. Admin-gated endpoints need a repeatable way to escalate. Centralizing in one helper avoids duplication and makes it easy to update if the admin detection logic changes (e.g., if `is_admin()` evolves beyond a simple username check).

---

## User Account Deletion (2026-02-13)

### User account deletion with typed-confirmation dialog
**By:** McManus, Fenster, Hockney
**Date:** 2026-02-13
**What:** Implemented `POST /api/delete-account` route that blocks admin self-deletion, removes user from `users.yaml`, deletes user's data directory, and clears session. Frontend adds "Delete Account" danger zone in `constraints.html` with red button requiring user to type "DELETE" in a `prompt()` dialog.
**Why:** Users need a way to remove their accounts. Admin protection prevents accidental self-deletion via API. Typed-confirmation UX matches the site export/import pattern, forcing deliberate action for a destructive operation.
**Test Coverage:** 5 tests in `TestDeleteAccount` class — success case, multi-tournament cleanup, admin blocked, login required, other users unaffected. All tests pass.
**Impact:** User deletion is permanent and cascading (removes all tournaments). 249 tests pass.

---

## Changelog Tracking (2026-02-13)

### Track all features in CHANGELOG.md
**By:** Luca Bolognese (via Copilot directive)
**Date:** 2026-02-13
**What:** From now on, all features are tracked in `CHANGELOG.md` following semantic versioning conventions.
**Why:** User request — centralized feature documentation for users and stakeholders.

---

## Show Test Buttons (2026-02-13)

### Conditional test buttons via show_test_buttons constraint
**By:** Fenster, Hockney
**Date:** 2026-02-13
**What:** Added `show_test_buttons: False` constraint (stored in `constraints.yaml`). Test buttons on 4 templates (`teams.html`, `courts.html`, `tracking.html`, `dbracket.html`) are now conditional on this setting. Settings page (`constraints.html`) has checkbox to toggle. Context processor injects `show_test_buttons` globally so templates don't need individual passes. Default is `False` — test buttons hidden unless explicitly enabled.
**Why:** Tournament managers sometimes forget test buttons are visible and accidentally include them in production exports. Hiding by default reduces mistakes. The 5-test suite (`TestShowTestButtons`) validates the full lifecycle including toggle persistence and conditional rendering.
**Impact:** All 249 tests pass. Test buttons remain discoverable for developers via Settings checkbox.

---

## Awards Feature (2026-02-13)

### Awards backend: API endpoints and data persistence
**By:** McManus
**Date:** 2026-02-13
**What:** Added awards feature backend in `src/app.py`:
- `load_awards()` / `save_awards()` — YAML persistence following `load_results()` pattern
- `GET /awards` — page route rendering `awards.html`
- `POST /api/awards/add` — creates award with auto-generated `award-{timestamp}` ID
- `POST /api/awards/delete` — removes award by ID and cleans up custom image files
- `POST /api/awards/upload-image` — accepts multipart file upload, validates against `ALLOWED_LOGO_EXTENSIONS`
- `GET /api/awards/image/<filename>` — serves custom images from tournament directory with path validation
- `GET /api/awards/samples` — lists files in `src/static/awards/`
- Awards data integrated into `_get_live_data()` for live/public-live routes
- `awards.yaml` added to `_get_exportable_files()` for export/import
- `'awards'` added to `tournament_endpoints` whitelist
**Why:** New feature requested: tournament managers need to assign awards to players. Follows existing patterns for data persistence and image upload.

### Awards frontend: UI and templates
**By:** Fenster
**Date:** 2026-02-13
**What:** Created `awards.html` template with image picker UI, added 10 SVG award icons in `src/static/awards/`, integrated "Awards" nav link in `base.html`, added awards section in `live_content.html` for live tournament display, applied CSS styling. Frontend expects API contract: `GET /awards`, `POST /api/awards/add`, `POST /api/awards/delete`, `GET /api/awards/samples`, `POST /api/awards/upload-image`, `GET /api/awards/image/<filename>`.
**Why:** Tournament managers need an intuitive interface to manage and assign awards. The live page should display current awards to spectators.
**Affected files:** `src/templates/awards.html`, `src/templates/base.html`, `src/templates/live_content.html`, `src/static/style.css`, `src/static/awards/*.svg`

### Awards tests comprehensive coverage (TestAwards)
**By:** Hockney
**Date:** 2026-02-13
**What:** Wrote 9 proactive tests in `TestAwards` class covering default empty awards, award creation with validation, award deletion and image cleanup, image upload and serving, live data injection, sample list retrieval. All tests pass.
**Why:** Awards feature is new and complex with file uploads and live integration. Test-first approach catches issues early. Tests serve as documentation of expected behavior.

---

## Instagram Friendly Tournament Summary (2026-02-13)

### Instagram summary route reuses _get_live_data()
**By:** McManus
**Date:** 2026-02-13
**What:** Added `GET /insta` route that renders `insta.html` with the full `_get_live_data()` payload (pools, standings, schedule, results, bracket_data, silver_bracket_data, awards, constraints). Added `'insta'` to the `tournament_endpoints` whitelist so it works without an active tournament.
**Why:** Follows the same pattern as `/live` — reuses the existing data-gathering helper rather than duplicating logic. Template rendering is delegated to Fenster's `insta.html`.

### Instagram summary page design: dark gradient card with inline styles
**By:** Fenster
**Date:** 2026-02-13
**What:** The Insta page (`insta.html`) uses a self-contained inline `<style>` block rather than adding to `style.css`. The card is a 480px-max dark gradient (purple → blue) designed for phone screenshots. All CSS classes are prefixed with `insta-` to avoid collisions. The template reuses `_get_live_data()` for its context, keeping it consistent with the live page data. Added "Insta" nav link in `base.html` between Awards and Live.
**Why:** Inline styles keep the page self-contained and avoid bloating the shared stylesheet with single-use classes. The `insta-` prefix prevents any accidental cascade into other pages. Using `_get_live_data()` means the Insta page always shows the same data as the live page — no drift, no separate data pipeline.
**Affected files:** `src/templates/insta.html` (new), `src/templates/base.html` (nav link added)

### Instagram tests comprehensive coverage (TestInstaPage)
**By:** Hockney
**Date:** 2026-02-13
**What:** Wrote 4 tests in `TestInstaPage` class covering page load (200), empty tournament (200), pools visible in response, and nav link presence. All tests pass.
**Why:** Insta page is a new route with conditional rendering. Tests verify the route is accessible and the template renders correctly with live data.
**Test Coverage:** 4 tests in `TestInstaPage` — all passing.
**Impact:** All 267 tests pass. Insta page feature complete with route, template, and comprehensive tests.

### Instagram page enhanced with bracket results (2026-02-13)
**By:** Fenster
**Date:** 2026-02-13
**What:** Added condensed bracket results section to `insta.html` displaying Gold Bracket (winners, losers, grand final, bracket reset) and Silver Bracket with same structure. Bracket display is compact: `Team A v Team B` with winner highlighted in green, scores as `X / Y` on right side. Byes skipped, no match codes or playability indicators. Uses CSS classes: `insta-bracket-match`, `insta-bracket-round`, `insta-bracket-sub`, `insta-grand-final`, `insta-match-done`, `insta-winner`, `insta-vs`, `insta-score`.
**Why:** Instagram snapshots need complete tournament results for sharing. Brackets are critical — pool standings alone don't tell the full story.

### Print page route and related code removed (2026-02-13)
**By:** McManus
**Date:** 2026-02-13
**What:** Removed three route handlers from `src/app.py`: `print_view()` (GET /print), `update_print_settings()` (POST /api/print-settings), and `save_print_settings()` helper function. Kept `load_print_settings()` — still used internally by `_get_live_data()` to populate the tournament header on `/live`, `/insta`, and public live routes. Retained `print_settings.yaml` file references in migration and export infrastructure for backward compatibility with existing tournaments.
**Why:** Print view is deprecated in favor of the insta page. Removing dead route code reduces maintenance burden, but keeping data file support ensures existing tournaments don't break.

### Print page template and nav link removed (2026-02-13)
**By:** Fenster
**Date:** 2026-02-13
**What:** Deleted `src/templates/print.html` template, removed "Print" nav link from `base.html`, and updated broken `url_for('print_view')` references in `index.html` to point to `url_for('insta')` instead.
**Why:** Print page is deprecated; all traffic should redirect to the insta page which has richer content (bracket results, awards).
**Affected files:** `src/templates/print.html` (deleted), `src/templates/base.html` (nav link removed), `src/templates/index.html` (references updated)

### Print page test cleanup (2026-02-13)
**By:** Hockney
**Date:** 2026-02-13
**What:** Removed `assert b'Print View' in response.data` line from `TestEnhancedDashboard::test_dashboard_shows_export_bar` (was verifying the print page nav link existed). No dedicated test classes/methods for print route existed to remove. Added `TestInstaPage::test_insta_page_shows_bracket_data` to verify bracket rendering on insta page when pools are configured.
**Why:** Print page nav link is gone; the assertion would always fail. New test documents bracket rendering behavior on insta page.
**Impact:** All 268 tests pass. No print-route failures because route was already removed upstream.

---

## Model Selection & Performance Optimization (2026-02-13 to 2026-02-14, consolidated)

### User model selection directives (consolidated)
**By:** Luca Bolognese (via Copilot)
**What:** Evolution of model selection preferences across session:
1. (2026-02-13 12:08) Use Opus 4.6 (fast mode) for all team members and tasks
2. (2026-02-13 15:05) Revert to default model selection for each team member — remove session-wide override
3. (2026-02-13 15:06) Re-apply claude-opus-4.6-fast for all team members (preference confirmed)
**Why:** User experimentation with model speed/quality tradeoff. Final decision: claude-opus-4.6-fast preferred over default per-role selection.

### Fast test subset via pytest `slow` marker (2026-02-13)
**By:** Hockney
**What:** Added `@pytest.mark.slow` to 2 tests in `TestLargeTournament` (test_integration.py) that hit 60-second CP-SAT solver timeout. Created `pytest.ini` with marker registration. Fast subset runs via `pytest tests/ -m "not slow"` (~21s, 274/276 tests). Full suite: `pytest tests/` (~137s, 276 tests).
**Why:** Full suite takes 2+ minutes almost entirely due to OR-Tools solver tests. For small changes (UI, templates), the wait is unnecessary friction. Fast subset covers 99% of tests including all route, model, bracket, and auth tests.

### Always use fast tests unless changing scheduling algorithm (2026-02-14, consolidated)
**By:** Luca Bolognese (via Copilot)
**What:** Team guideline — run `pytest -m "not slow"` for non-scheduling changes. Only run full suite (`pytest tests/`) when allocation/scheduling code in `src/core/allocation.py` is modified.
**Why:** User request — fast feedback loop for 95% of changes. Captured for team memory.

---

## Result Clearing User Experience (2026-02-13 to 2026-02-14, consolidated)

### Clear result button API contract (2026-02-14)
**By:** Fenster
**What:** Tracking page clear buttons (✕) call `POST /api/clear-result` with JSON `{"match_key": "<key>"}`. Backend removes result from `results.yaml` and returns `{"success": true}`.
**Why:** Tournament managers need to correct mistakes. Frontend ready; backend implementation required.

### Result clearing via empty score submission (2026-02-13)
**By:** McManus
**What:** Score input endpoints (`/api/results/pool`, `/api/results/bracket`) now detect when all scores are empty and delete the result instead of rejecting. Partial input (one filled, one empty) still returns 400 error.
**Why:** Simpler UX — users clear results by deleting both scores naturally, no separate button needed.

### Clear result buttons removed from all result tracking UIs (2026-02-14)
**By:** Fenster
**What:** Removed all "Clear" (✕) buttons and JavaScript (`clearResult`, `clearBracketResult`) from tracking.html, sbracket.html, dbracket.html. Users now clear by deleting both score values.
**Why:** User request (Luca) — the explicit clear button added visual clutter. The natural workflow is already clearing scores anyway. The backend `/api/clear-result` endpoint remains for programmatic use.

---

## Azure Deployment & Infrastructure (2026-02-14, consolidated & expanded)

### Azure app name uniqueness via subscription prefix (2026-02-14)
**By:** McManus
**What:** Changed default app name from hardcoded "tournament-allocator" to `tournament-allocator-{8-char-subscription-id-prefix}`. Auto-generated, deterministic, globally unique. Users can override via `AZURE_APP_NAME` in `.env`.
**Why:** Azure requires globally unique app names. The hardcoded name was already taken, causing deployment collisions.

### PowerShell Azure CLI existence checks use $LASTEXITCODE (2026-02-14)
**By:** McManus
**What:** Resource existence checks for App Service Plan and Web App now use `$LASTEXITCODE` after `az ... show` commands instead of try/catch blocks. Pattern: `az <cmd> 2>$null; $exists = ($LASTEXITCODE -eq 0)`.
**Why:** PowerShell doesn't automatically throw exceptions on non-zero exit codes from external commands. Try/catch blocks don't catch CLI failures, causing false positives (script thinks resources exist when they don't). Checking `$LASTEXITCODE` is the correct pattern.

### Azure Oryx build timing — build settings before deploy (2026-02-14)
**By:** McManus
**What:** Split app settings into build-time and runtime groups:
1. **Build-time** (`SCM_DO_BUILD_DURING_DEPLOYMENT=true`) — set BEFORE `az webapp deploy`
2. **Runtime** (`TOURNAMENT_DATA_DIR`, `SECRET_KEY`, startup command) — set AFTER deploy
**Why:** Kudu checks build flag during zip extraction; setting it after deploy is too late. Oryx never runs → missing Python packages → ModuleNotFoundError. Splitting prevents race conditions and ensures build artifacts exist before runtime settings trigger restarts.

### GitHub Actions deployment incompatible with Azure B1 tier (2026-02-14, consolidated)
**By:** Keaton
**What:** GitHub Actions auto-deployment using `azure/webapps-deploy` action does NOT work on B1 (Basic) tier. The action assumes deployment slots are available (requires Standard tier+). Manual deployments via `deploy.ps1` continue to work fine.
**Why:** B1 tier doesn't support slots. Multiple workaround attempts failed due to action's internal assumptions. To enable GitHub Actions, upgrade to Standard tier (~$55/month vs ~$13/month for B1).
**Impact:** GitHub Actions CI/CD currently disabled. Use `deploy.ps1` for deployments.

### GitHub Actions deployment via deploygh.ps1 (2026-02-14)
**By:** Keaton
**What:** Created `deploygh.ps1` script that provisions App Service and configures GitHub Actions for automatic deployment on git push. Generates `.github/workflows/azure-deployment.yml`, sets up publish profile credentials as GitHub secrets, configures same runtime settings as `deploy.ps1`.
**Why:** Manual deployment requires running script every time code changes. GitHub Actions automation enables zero-touch deployments on push. Script is idempotent and follows Azure best practices.

---

## Admin User & Deployment Security (2026-02-14)

### Admin user automatic initialization (2026-02-14)
**By:** McManus
**What:** Admin user now auto-created on fresh deployment and ensured to exist on every startup. Password sourced from `ADMIN_PASSWORD` environment variable (defaults to "admin"). Implementation: new `_ensure_admin_user_exists()` helper (idempotent), updated `_migrate_to_admin_user()` to read env var, modified `ensure_tournament_structure()` migration logic, added `ADMIN_PASSWORD` app setting to `deploy.ps1`.
**Why:** Fresh Azure deploys had no way to access the app (no users existed). Zero-friction deployment pattern. Admin credentials displayed in deployment output so deployer knows how to log in immediately.

---

## Azure Backup/Restore & Multi-User Cleanup (2026-02-14–2026-02-15)

### 2026-02-14: Comprehensive Azure backup/restore test coverage

**By:** Hockney

**What:** Created 67 tests across 3 files (`test_backup_script.py`, `test_restore_script.py`, `test_backup_restore_integration.py`) covering Azure App Service backup/restore scripts with comprehensive mocking.

**Why:** The backup/restore scripts (`scripts/backup.py`, `scripts/restore.py`) are critical for production data safety but had zero test coverage. Tests validate all workflows (CLI checks, remote operations, ZIP handling, error conditions, exit codes) without requiring actual Azure infrastructure. Mock all `az` CLI calls via `unittest.mock.patch('subprocess.run')`. Security validations include directory traversal detection and absolute path rejection in ZIP files. Round-trip integration tests verify data integrity through full backup → restore → verify cycles.

### 2026-02-14: Removed admin configuration from deployment script

**By:** Keaton

**What:** Removed all ADMIN_PASSWORD environment variable settings, admin user references, and admin login documentation from deploy.ps1

**Why:** Multi-user authentication system is being removed from the application. The deployment script no longer needs to configure admin users or passwords. This simplifies deployment and removes unnecessary security configuration for a single-user tournament management tool.

### 2026-02-15: CLI-based backup/restore strategy for Azure

**By:** McManus

**What:** Tournament data backup and restore now uses Azure CLI scripts (`scripts/backup.py`, `scripts/restore.py`) instead of web-based admin routes. Data lives in `/home/data` on Azure and is persistent across deployments.

**Why:** 
- **Scriptable**: Backup/restore operations can be automated in CI/CD pipelines or local cron jobs without web UI intervention
- **No admin privileges**: Removes need for special admin credentials or web-based admin panels
- **Auditable**: All operations are plain-text CLI commands (easily logged and reviewed)

---

## Recent Feature Development (2026-02-15 to 2026-02-16)

### 2026-02-14: HTTP backup/restore architecture with API key authentication

**By:** McManus  
**What:** Replaced Azure CLI SSH-based backup with HTTP routes secured by API key. Backup and restore operations now accessible via HTTP without requiring SSH access to the Azure container.

**Why:** The original CLI-based backup scripts (`backup-data.ps1`, `restore-data.ps1`) required SSH access to the Azure container using App Service credentials. This created operational friction — every backup/restore required looking up SSH credentials, enabling SSH on the App Service, and using `az webapp ssh` commands. HTTP-based backup allows:

1. **Simpler automation** — backup scripts can use standard HTTP tools (curl, PowerShell Invoke-WebRequest) without Azure CLI dependencies
2. **No SSH required** — reduces attack surface by not enabling SSH on production containers
3. **Scriptable from CI/CD** — GitHub Actions, scheduled tasks, or monitoring systems can trigger backups via HTTP without container access
4. **Same security model** — API key stored in Azure App Service application settings, timing-attack-safe comparison via `hmac.compare_digest()`

**Implementation details:**
- Export: `GET /api/admin/export` returns entire `DATA_DIR` as timestamped ZIP
- Import: `POST /api/admin/import` accepts ZIP upload, validates structure, backs up existing data before restoring
- Auth: `@require_backup_key` decorator checks `Authorization: Bearer <token>` header against `BACKUP_API_KEY` environment variable
- Security: Path traversal protection, ZIP validation, size limits (50MB), timing-attack-safe key comparison
- Backup on import: Creates `backups/pre-restore-{timestamp}/` copy before extracting uploaded ZIP

**Migration path:**
1. Generate API key: `python -c "import secrets; print(secrets.token_urlsafe(32))"`
2. Set in Azure: `az webapp config appsettings set --settings BACKUP_API_KEY='...'`
3. Update backup scripts to use HTTP instead of SSH
4. Optionally disable SSH on App Service once HTTP backup is verified

**Related files:**
- `src/app.py` — Flask routes and decorator
- `docs/http-backup-api.md` — API documentation
- `test_backup_routes.py` — Local testing script
- `scripts/backup-data.ps1`, `scripts/restore-data.ps1` — CLI scripts (can be updated to use HTTP)

### 2026-02-15: Backup API routes must bypass session authentication

**By:** McManus

**What:** The `/api/admin/export` and `/api/admin/import` routes have been added to the `before_request` whitelist so they can use API key authentication instead of session-based login.

**Why:** These routes use the `@require_backup_key` decorator which validates a `BACKUP_API_KEY` from environment variables. They're designed for automated backup/restore operations that can't use browser sessions. By adding them to the whitelist (alongside other non-session routes like public live views), they bypass the "redirect to login if no session" check and handle their own authentication.

**Pattern:** Any route that uses custom authentication (API keys, public access, etc.) should be added to the `before_request` whitelist at the top of `set_active_tournament()`. Session-based routes stay off the whitelist and get the default "require login" behavior.

### 2026-02-15: One-time data migration from old location to TOURNAMENT_DATA_DIR

**By:** McManus

**What:** Added shell-based migration logic in `startup.sh` that moves user data from the legacy location (`/home/site/wwwroot/data`) to the new persistent location (`/home/data`) on first startup.

**Why:** When we deployed the `TOURNAMENT_DATA_DIR` change (2026-02-11), existing Azure deployments had all their user data in `/home/site/wwwroot/data`. The backup system correctly targets `/home/data`, but that directory was empty on existing sites. This one-time migration runs before Flask starts, detects the situation, and relocates the data automatically.

**Pattern:**
- Migration runs in `startup.sh` BEFORE Flask starts (not in Python)
- Checks if target is empty (ignoring `.lock` file)
- Checks if source exists with `users/` directory
- Uses `mv` (not `cp`) to relocate files
- Idempotent — safe to run multiple times
- Logs when migration runs for debugging

**Decision:** Shell-based migrations for filesystem changes belong in `startup.sh`, not in Python `before_request` hooks. This ensures the filesystem is in the correct state before any application code runs.

### 2026-02-15: Auto-generate backup API key in deployment script

**By:** Keaton

**What:** Added automatic BACKUP_API_KEY generation to deploy.ps1 that checks Azure App Settings, generates a 32-byte random hex key if missing, sets it in Azure, and writes it to the local .env file.

**Why:** Ensures backup/restore HTTP endpoints are always secured with an API key without requiring manual key management. The script generates a cryptographically secure 64-character hex key on first deploy and syncs it between Azure and local environment. Subsequent deploys preserve the existing key to maintain access to backup operations.

### 2026-02-15: Pre-restore backup file location (VERIFIED)

**By:** McManus

**What:** Pre-backup files are already stored in `backups/` directory within the project root using Windows-compatible paths via `os.path.join(BASE_DIR, 'backups', f'pre-restore-{timestamp}')`.

**Why:** The implementation at line 3559 in `src/app.py` has always used the proper `backups/` directory. No `/tmp` usage exists in the backup/restore code. This was verified by checking both current code and git history (commit 5861616 initial implementation).

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

### 2026-02-20: Consecutive matches should be avoided via soft CP-SAT penalty

**By:** Verbal

**What:** When `pool_in_same_court` is enabled, the solver should add soft penalties to the objective function discouraging teams from playing consecutive matches. Use graduated penalties: 2-in-a-row penalized lightly, 3-in-a-row penalized heavily. This is a soft constraint (penalty in objective), not a hard constraint, to preserve schedule feasibility. No new UI setting needed — always active.

**Why:** The current model packs matches tightly to minimize makespan, causing teams to play 3 matches in a row. A soft penalty lets the solver find better interleaving when possible, while still producing valid schedules under tight time constraints. The greedy fallback should also prefer non-consecutive placements.

### 2026-02-16: Consecutive match detection approach

**By:** McManus

**What:** Added boolean variables to the CP-SAT model in `src/core/allocation.py` that detect when two matches for the same team are scheduled too close together (within 2× match duration). Each team with ≥2 matches gets `is_consecutive` booleans for each pair of matches. All booleans are summed into a `consecutive_penalty` variable ready for use in the objective function.

**Why:** When `pool_in_same_court` is enabled, the solver packs pool matches sequentially on one court, causing teams to play 2-3 matches in a row with only the minimum break between them. This is physically taxing for players. The detection variables enable a future soft penalty in the objective function that will discourage (but not prohibit) consecutive matches. Using a soft penalty instead of a hard constraint ensures the model remains feasible even in tight schedules.

**Implementation details:**
- Threshold: `2 × (match_slots + break_slots)` — if two matches start within this window, they're too close
- Uses CP-SAT reification: `model.Add(abs_diff < threshold).OnlyEnforceIf(is_consecutive)`
- Complexity: O(T × M²) boolean variables, where T = teams and M = matches per team (typically 3-6)
- Location: After team no-overlap constraint (line 373), before pool-in-same-court constraint
- Next step: Add `consecutive_penalty × penalty_weight` to objective function (separate task)

**Pattern for other agents:**
When adding soft constraints to CP-SAT models:
1. Create detection variables using reification (boolean linked to a condition)
2. Sum detection variables into a penalty term
3. Add penalty term to objective with appropriate weight (less than makespan_weight to preserve priorities)

### 2026-02-16: Test Structure for Consecutive Match Feature

**By:** Hockney

**What:** Created dedicated test file `tests/test_consecutive.py` with 10 test cases validating the consecutive match avoidance feature. Tests use monkey-patching to inject custom match lists, following the pattern from `tests/test_integration.py`.

**Why:** 
- Separate file keeps consecutive match tests isolated and easy to maintain
- Monkey-patching `_generate_pool_play_matches()` gives precise control over match scenarios
- Tests verify both the optimization goal (avoid 3-in-a-row) and the soft constraint property (still feasible when unavoidable)
- 20-minute threshold in `count_consecutive_runs()` accounts for typical match+break duration (30min + 15min break = 45min window)
- Tests are written against intended behavior, so they guide implementation and serve as acceptance criteria

**Impact:**
- McManus can implement the CP-SAT penalty knowing exactly what behavior is expected
- Tests will fail until penalty is implemented, then pass when feature is complete
- Future changes to scheduling algorithm have regression protection
- **Azure-native**: Uses Azure CLI (`az webapp ssh`) for secure, direct container access

**Usage:**
```bash
# Backup
python scripts/backup.py --app-name <app> --resource-group <rg>

# Restore (with safety checks)
python scripts/restore.py backup.zip --app-name <app> --resource-group <rg>
```

**Documentation:** See `docs/CLI_BACKUP_RESTORE.md` for:
- Detailed CLI usage examples
- Automated backup scheduling (Task Scheduler, cron, Azure Pipelines)
- Disaster recovery procedures
- Troubleshooting common Azure CLI issues

**Impact:** No admin user type in codebase. All backups and restores are user-initiated CLI operations with pre-restore safety backups created automatically.
**Security:** Password never hardcoded in source. Env var pattern matches existing `SECRET_KEY` handling. First-deploy only — won't overwrite password on subsequent deploys.

---

## UI & Frontend Patterns (2026-02-14, consolidated)

### Tournament page button colors use existing CSS class modifiers (2026-02-14)
**By:** Fenster
**What:** Tournaments page buttons styled using existing `.btn-*` classes: Switch → `.btn-success` (green), Clone → `.btn-primary` (blue), Delete → `.btn-danger` (red). No new CSS added.
**Why:** Project already has proper `.btn-success`, `.btn-primary`, `.btn-danger` with hover states and dark mode support. Reusing classes is more maintainable than inline styles, keeps template consistent.

### Dark mode uses CSS custom properties with [data-theme="dark"] selector (2026-02-14)
**By:** Fenster
**What:** Dark mode implemented client-side via CSS custom properties. `:root` defines light colors, `[data-theme="dark"]` overrides them. Frontend script applies saved theme from localStorage before rendering. Theme toggle in navbar. New CSS with hardcoded colors must include dark overrides.
**Why:** CSS variables allow entire app to switch without JS DOM manipulation. Head script prevents FOUC on dark-mode page loads. Pattern enforces discipline — agents adding new UI must add dark overrides or risk visual inconsistencies.

### Auto-activate first tournament on navigation (2026-02-14)
**By:** Fenster
**What:** When user has tournaments but none is set active (session expired or corrupted tournaments.yaml), `set_active_tournament()` before_request hook automatically activates the first tournament. Updates both tournaments.yaml and session, continues normal request.
**Why:** User-friendly recovery from stale session state. Prevents "no tournaments exist" redirects when tours actually exist. Safe pattern — validates directory exists before activating.

---

## Tournament CRUD Operations (2026-02-13 to 2026-02-14)

### Clone tournament uses shutil.copytree (2026-02-13)
**By:** McManus
**What:** `POST /api/tournaments/clone` endpoint copies entire source tournament directory (all YAML, CSV, logos, awards) using `shutil.copytree()` to new slug directory. Patches `tournament_name` in cloned constraints.yaml. Added to `tournament_endpoints` whitelist.
**Why:** `copytree` is simplest — no need to maintain list of copy-able files. Future file types automatically included in clones. No special handling needed.

---

## Decisions From User Directives (2026-02-13)

### Track all features in CHANGELOG.md (2026-02-13)
**By:** Luca Bolognese (via Copilot directive)
**What:** All features tracked in `CHANGELOG.md` following semantic versioning conventions.
**Why:** User request — centralized feature documentation for users and stakeholders.

---

## Git Workflow & User Directives (2026-02-14)

### User directive on git workflow
**By:** Luca Bolognese (via Copilot)
**Date:** 2026-02-14
**What:** Always check in your changes, but push them just if they are small changes non dangerous
**Why:** User request — captured for team memory. Preference for cautious pushing strategy: commit locally always, but only push to remote when changes are small and safe.

---

## Azure Data Management Scripts (2026-02-14)

### Azure restore script implementation approach
**By:** Fenster
**Date:** 2026-02-14
**What:** Created `scripts/restore.py` for restoring Tournament Allocator data to Azure App Service from backup ZIP. Script uses base64-encoded chunked upload through `az webapp ssh` to transfer files, stops the app during restore to prevent corruption, and validates remotely after extraction. Pre-restore backup is created automatically (calls `backup.py`) unless `--no-backup` flag is used. Requires `users.yaml` and `.secret_key` in backup ZIP. Typed confirmation prompt (must type "RESTORE") unless `--force` flag.
**Why:** Azure App Service's `az webapp ssh` has command-length limits, making direct binary uploads unreliable. Base64 encoding with 50KB chunks solves this. Stopping the app during restore prevents file corruption from concurrent writes. Pre-restore backup provides rollback capability. ZIP validation before upload catches corrupt backups early. Remote validation after extraction ensures data integrity.

### Azure backup uses SSH tar streaming approach
**By:** Keaton
**Date:** 2026-02-14
**What:** `scripts/backup.py` uses `az webapp ssh` to create a remote tar archive of `/home/data`, downloads it via SSH stdout redirection, extracts locally, and creates a timestamped ZIP. This approach avoids Kudu/SCM APIs and works directly with the Linux container filesystem.
**Why:** Azure App Service on Linux mounts persistent storage at `/home/`, but doesn't provide a direct API for bulk directory downloads. The `az webapp ssh` command gives direct shell access to the container. By creating a tar archive remotely and streaming it through SSH stdout, we can download the entire directory structure in one operation without needing to know the file tree in advance. This is more reliable than FTP (which Azure is deprecating) and simpler than recursively downloading files via Kudu API.
**Trade-offs:**
- Requires `tar` command available locally (native on Linux/macOS, needs WSL/Git Bash on Windows)
- Backup is point-in-time only (no incremental support)
- Depends on SSH access being enabled (default on Linux App Service)

---

## Test Architecture & Coverage (2026-02-14)

### Bracket scheduling validation — Phase 2 test suite
**By:** Hockney
**Date:** 2026-02-14
**What:** Implemented comprehensive bracket scheduling validation tests across 3 areas:
1. **Bracket phase transitions** (`TestBracketPhaseTransitions`) — 3 tests validating pool-to-bracket timing constraints, enforcing `pool_to_bracket_delay_minutes` and ensuring bracket starts after pools complete
2. **Court constraints for bracket** (`tests/test_schedule_validity.py`) — 3 tests validating bracket matches respect court hours, minimum breaks, and no court double-booking
3. **Grand final scheduling** (`TestGrandFinalScheduling`) — 3 tests validating complex timing dependencies: Grand Final must wait for both Winners Final AND Losers Final; Bracket reset conditional on losers champ winning GF
**Why:** Bracket scheduling must respect the same court and timing constraints as pool play. Grand finals have complex interdependencies not previously tested. Phase 2 establishes foundational test coverage for bracket constraints before Phase 3 integration tests.
**Test execution:** 12 Phase 2 tests total, all passing in <2 seconds.
**Key Constraint:** `pool_to_bracket_delay_minutes` from `constraints.yaml` (default: 0).

### Schedule validation helper functions
**By:** Hockney
**Date:** 2026-02-14
**What:** Created three reusable schedule validation helpers in `tests/test_helpers_validation.py`:
1. **validate_no_premature_scheduling(schedule, dependencies, match_codes)** — Validates teams aren't scheduled before prerequisite matches complete
2. **validate_team_availability(schedule, team_name)** — Validates teams aren't double-booked (no overlapping matches)
3. **validate_bracket_dependencies(schedule, bracket_structure)** — Validates bracket match dependencies are respected

Each helper returns `List[str]` of clear, actionable violation messages (empty list = valid).
**Why:** Phase 2 schedule validity tests and upcoming Phase 3 integration tests need common validation logic. Helpers eliminate duplication and provide reusable, well-tested validation building blocks. All helpers are pure functions with comprehensive test coverage (24 tests covering valid/invalid/edge cases).
**API Design Notes:**
- `validate_no_premature_scheduling` requires `match_codes` dict mapping teams tuple to match code
- Schedule format: `Dict[str, List[Tuple[int, datetime, datetime, Tuple[str, str]]]]` (court name → list)
- All helpers handle edge cases: empty schedules, missing matches, cross-day dependencies, midnight crossing

---

### 2026-02-16: Greedy fallback prefers non-consecutive match placements

**By:** McManus

**What:** Updated the greedy scheduling fallback to actively avoid placing teams in consecutive matches. The algorithm now scans all valid candidate slots, scores them by how many consecutive matches they would create, and picks the best option (fewest consecutive, then earliest time).

**Why:** When CP-SAT times out or fails, the greedy algorithm provides the fallback schedule. The old first-fit approach naturally created consecutive matches (teams playing 2-3 in a row with only minimum break). This change makes greedy smarter about interleaving matches from different teams.

**How it works:**
- New helper `_count_consecutive_matches_if_placed()` calculates consecutive run length
- Uses same threshold as CP-SAT: matches within `2 × (match_duration + break)` are consecutive
- Greedy collects all valid slots, sorts by `(consecutive_count, start_time)`, picks best
- Falls back to any valid slot if avoiding consecutive matches is impossible (preserves feasibility)

**Impact:**
- Better schedules when greedy is triggered (tight tournaments, complex constraints)
- Slightly slower than old first-fit, but still fast enough for fallback use
- No UI changes — behavior is automatic

### 2026-02-16: Consecutive match penalty weight calibration

**By:** McManus

**What:** Set penalty_weight = match_slots for the consecutive_penalty term in the CP-SAT objective function.

**Why:** This calibration creates a meaningful tradeoff where avoiding one consecutive match pair is worth approximately one match-duration of schedule extension. The weight must be less than makespan_weight (to prevent extending the tournament just to avoid consecutive play) but more than 1 (to make the solver actually care about it). Using match_slots provides an intuitive, self-scaling value that adapts to match duration — shorter matches get proportionally less weight, longer matches get more.

**Impact:** The solver now actively balances three priorities: (1) finish on time, (2) avoid consecutive play, (3) maximize rest between matches. This should significantly reduce back-to-back scheduling when `pool_in_same_court` is enabled.

### 2026-02-16: Graduated penalty system for consecutive match runs

**By:** McManus

**What:** Implemented two-tier penalty detection in the CP-SAT scheduler: pair-wise consecutive matches (2 in a row) and triple consecutive matches (3+ in a row), with triple penalties weighted 3× higher than pair penalties.

**Why:** 
- The solver was creating schedules where teams played 3+ matches back-to-back when `pool_in_same_court` was enabled
- Simply penalizing all consecutive pairs equally didn't differentiate between "2 in a row" (tolerable) and "3 in a row" (very demanding)
- Graduated weighting gives the solver flexibility: it can choose some pairs if needed, but will strongly avoid triples
- The 3× multiplier means a single triple (penalty = 3) costs more than one pair (penalty = 1), so the solver will break up triple runs when possible

**Pattern:**
- Store pair detection results in a dict `pair_consecutive_vars[(team, m1_idx, m2_idx)]` for reuse
- Triple detection reuses pair booleans via AND constraints: `triple <= pair1`, `triple <= pair2`, `triple >= pair1 + pair2 - 1`
- Combined penalty: `pair_penalty + 3 × triple_penalty`
- This pattern can extend to 4+ consecutive runs if needed (weight 5×, 7×, etc.)

**Files:** `src/core/allocation.py` (lines 373-482)
