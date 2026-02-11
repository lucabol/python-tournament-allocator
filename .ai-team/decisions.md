# Decisions

> Shared decision log. All agents read this before starting work. Scribe maintains it.

<!-- Decisions are appended below. Each entry starts with ### -->

### 2026-02-11: Tournament data stored as subdirectories under data/tournaments/
**By:** Verbal
**What:** Each tournament gets its own subdirectory (`data/tournaments/<slug>/`) containing the same set of files (`teams.yaml`, `courts.csv`, `constraints.yaml`, `results.yaml`, `schedule.yaml`, `print_settings.yaml`, `logo.*`). A top-level `data/tournaments.yaml` tracks the list of tournaments and the currently active one.
**Why:** Keeps the existing file-based architecture. Each tournament is self-contained, directly exportable as a ZIP (matches existing export/import feature), and requires no database. Simplest approach that works.

### 2026-02-11: Tournaments identified by user-chosen name converted to filesystem slug
**By:** Verbal
**What:** Users provide a display name. The system generates a filesystem-safe slug (lowercase, hyphens, no special chars) used as the directory name and internal identifier. Duplicate slugs are rejected at creation time.
**Why:** Human-readable, filesystem-safe, simple. UUIDs would be opaque and unfriendly. The display name is already stored in `constraints.yaml` as `tournament_name`.

### 2026-02-11: Session-based active tournament (not URL-prefixed)
**By:** Verbal
**What:** The active tournament slug is stored in the Flask session. All existing routes stay unchanged — a `@app.before_request` hook sets `g.data_dir` to the active tournament's directory. New routes added only for tournament management (`/tournaments`, `/api/tournaments/*`).
**Why:** URL-prefixing every route (`/tournament/<slug>/teams`, etc.) would require rewriting ~30 route decorators, every `url_for()` in every template, and every test. Session-based requires one hook, parameterized file paths, and a few new routes — estimated 10x less code churn. Trade-off: no bookmarkable tournament URLs, acceptable for single-organizer use case.

### 2026-02-11: Legacy data auto-migrated to "default" tournament on first startup
**By:** Verbal
**What:** On first startup with new code, if `data/` contains old-format flat files, automatically move them into `data/tournaments/default/` and create `data/tournaments.yaml`. Zero manual migration required.
**Why:** Zero-disruption upgrade path. Existing users keep their data without any manual steps.

### 2026-02-11: File paths parameterized via g.data_dir and _file_path() helper
**By:** Verbal
**What:** Replace module-level file path constants (`TEAMS_FILE`, `COURTS_FILE`, etc.) with a `_file_path(filename)` function that resolves against `g.data_dir`. The `before_request` hook sets `g.data_dir` from the session's active tournament.
**Why:** Minimal change to existing `load_*/save_*` functions — each swaps a constant for a function call, no signature changes. Tests can monkeypatch `g.data_dir` instead of 8+ individual constants.
