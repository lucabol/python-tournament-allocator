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
