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
