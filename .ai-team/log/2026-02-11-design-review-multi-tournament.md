# Design Review: Multi-Tournament Support

**Date:** 2026-02-11
**Facilitator:** Verbal (Lead)
**Participants:** McManus (Backend), Fenster (Frontend), Hockney (Tester)
**Requested by:** Luca Bolognese

---

## Context

The app currently manages a single tournament — one set of flat files in `data/`. Luca wants support for creating, deleting, and switching between multiple tournaments. The codebase is a monolithic ~2700-line `app.py` with ~30 routes, 6 pairs of `load_*/save_*` functions, and module-level constants pointing at file paths. There is no file locking.

---

## Key Decisions

### 1. Disk Organization: Subdirectories per Tournament

**Decision:** Each tournament gets its own subdirectory under `data/tournaments/<slug>/`, containing the same files (`teams.yaml`, `courts.csv`, `constraints.yaml`, `results.yaml`, `schedule.yaml`, `print_settings.yaml`, `logo.*`). A metadata file `data/tournaments.yaml` tracks the list of tournaments and the currently active one.

**Why:** This is the lowest-friction approach. We keep the file-based architecture, every tournament is self-contained and exportable, and the existing ZIP export/import maps directly to directory ↔ archive. No database needed.

**Structure:**
```
data/
  tournaments.yaml          # {active: "summer-classic", tournaments: [{slug, name, created}]}
  tournaments/
    summer-classic/
      teams.yaml
      courts.csv
      constraints.yaml
      results.yaml
      schedule.yaml
      print_settings.yaml
      logo.png
    winter-open/
      ...
```

### 2. Tournament Identification: User-Chosen Name → Filesystem Slug

**Decision:** Users provide a display name (e.g., "Summer Classic 2026"). The system generates a filesystem-safe slug (`summer-classic-2026`) using simple transliteration (lowercase, replace spaces/special chars with hyphens, dedup). The slug is the directory name and the internal identifier. Duplicate slugs are rejected at creation time.

**Why:** UUIDs are ugly and meaningless to users. Slugs are human-readable, filesystem-safe, and simple. The display name is stored in the tournament's `constraints.yaml` as `tournament_name` (already exists).

### 3. URL Routing Strategy: Session-Based Active Tournament

**Decision:** Store the active tournament slug in the Flask session. All existing routes stay unchanged — they resolve to data in the active tournament's directory. A `@app.before_request` hook sets `g.data_dir` from the session. New routes added only for tournament management:

- `GET /tournaments` — list/create/delete tournaments (new page)
- `POST /api/tournaments/create` — create new tournament
- `POST /api/tournaments/delete` — delete a tournament
- `POST /api/tournaments/switch` — switch active tournament

**Why:** The alternative — URL-prefixing every route with `/tournament/<slug>/` — would require rewriting all ~30 route decorators, every `url_for()` call in every template, and every test. Session-based is a surgical change: one `before_request` hook, parameterized file paths, a few new routes. Estimated 10x less code churn.

**Trade-off acknowledged:** Session-based means you can't bookmark a specific tournament's URL, and sharing links between users doesn't carry tournament context. This is acceptable for v1 — the app is typically used by one organizer at a time. URL-prefixing can be added later if multi-user sharing becomes a requirement.

### 4. Migration: Existing Data Becomes "Default" Tournament

**Decision:** On first startup with new code, if `data/` contains old-format flat files (no `tournaments.yaml`), automatically migrate them:
1. Create `data/tournaments/default/`
2. Move all data files into it
3. Create `data/tournaments.yaml` with `active: default`

If `data/` is empty (fresh install), create a "default" tournament with empty files.

**Why:** Zero-disruption upgrade. Existing users keep their data. No manual migration step needed.

### 5. Implementation: Parameterize File Paths via `g.data_dir`

**Decision:** Replace module-level file path constants with a function pattern:

```python
def _tournament_dir():
    """Return the data directory for the active tournament."""
    return getattr(g, 'data_dir', DATA_DIR)

def _file_path(filename):
    """Return full path to a data file in the active tournament."""
    return os.path.join(_tournament_dir(), filename)
```

The `load_*/save_*` functions replace their hardcoded paths with `_file_path('teams.yaml')`, etc. The `@app.before_request` hook resolves the active tournament and sets `g.data_dir`.

**Why:** Minimal change to existing functions — each just swaps a constant for a function call. No signature changes. Tests can still monkeypatch `g.data_dir`.

---

## Participant Perspectives

### McManus (Backend Dev)

**Scope of changes to `app.py`:**
1. Add `@app.before_request` hook to resolve `g.data_dir` from session
2. Add `_tournament_dir()` and `_file_path()` helper functions
3. Replace ~30 references to `TEAMS_FILE`, `COURTS_FILE`, etc. with `_file_path(...)` calls
4. Add 4 new routes for tournament CRUD + switch
5. Add `ensure_migration()` startup function
6. Update export/import to work with tournament directories

**Risks identified:**
- The `EXPORTABLE_FILES` dict is module-level and references constants. Needs to become a function.
- `_find_logo_file()` and `_delete_logo_file()` reference `LOGO_FILE_PREFIX` — must be parameterized.
- Test data loading (`api_load_test_data`) and reset (`api_reset_all`) must scope to active tournament.

**Locking:** No change needed. Per-tournament directories actually reduce contention if multiple organizers were ever running simultaneously.

### Fenster (Frontend Dev)

**Template changes (minimal):**
1. `base.html` — Add active tournament name display in navbar (small badge or text next to brand). Add a link to `/tournaments`.
2. New `tournaments.html` template — List of tournaments with create/delete actions, switch buttons.
3. All other templates — No changes. They already render whatever data the routes provide.

**UX flow:**
- First visit → redirected to `/tournaments` if no active tournament
- `/tournaments` page: see list, create new, delete, switch
- After switching → redirected to dashboard
- Tournament name visible in navbar at all times for orientation

### Hockney (Tester)

**Test impact:**
- `temp_data_dir` fixture: needs to create tournament subdirectory structure and set `g.data_dir`
- Existing tests: should work with minimal changes if monkeypatch targets the right path resolution
- New tests needed:
  - `TestTournamentCRUD`: create, delete, switch, list
  - `TestTournamentMigration`: legacy flat-file migration on startup
  - `TestTournamentEdgeCases`: delete active tournament, create with duplicate name, empty name, special characters in name
  - `TestTournamentIsolation`: changes in one tournament don't affect another
- Existing route tests: should pass unchanged if fixture properly sets up tournament context

---

## Action Items

| # | Who | Task | Priority |
|---|-----|------|----------|
| 1 | McManus | Implement `_tournament_dir()`, `_file_path()`, and `@app.before_request` hook | P0 |
| 2 | McManus | Replace all module-level file path references with `_file_path()` calls | P0 |
| 3 | McManus | Add tournament CRUD routes (`/tournaments`, `/api/tournaments/*`) | P0 |
| 4 | McManus | Implement `ensure_migration()` for legacy data upgrade | P0 |
| 5 | McManus | Update export/import to work with tournament context | P1 |
| 6 | Fenster | Create `tournaments.html` template (list/create/delete UI) | P0 |
| 7 | Fenster | Add tournament indicator to `base.html` navbar | P0 |
| 8 | Hockney | Update `temp_data_dir` fixture for tournament subdirectory structure | P0 |
| 9 | Hockney | Write tests for tournament CRUD and migration | P0 |
| 10 | Hockney | Write edge case tests (delete active, duplicates, isolation) | P1 |

---

## Risks & Concerns

1. **Scope creep:** Multi-user tournament sharing, permissions, and URL-based tournament selection are explicitly out of scope for v1. Session-based is the pragmatic choice now.
2. **Test churn:** The `temp_data_dir` fixture monkeypatches 8+ module-level constants. After this change, it should only need to set `g.data_dir`. Net simplification.
3. **Concurrent access:** No file locking exists today, and we're not adding any. Per-tournament directories reduce (but don't eliminate) the risk of concurrent writes. Acceptable for the single-organizer use case.
4. **Slug collisions:** Simple slug generation could produce collisions for names that differ only in special characters. Mitigation: reject duplicates at creation time, suggest alternatives.
5. **Disk cleanup:** Deleting a tournament means `shutil.rmtree()` on its directory. Must validate slug to prevent path traversal (no `..`, no `/`).

---

## Out of Scope (Explicitly Deferred)

- Database storage (SQLite, etc.) — files work fine for this scale
- URL-prefixed routing (`/tournament/<slug>/teams`) — revisit if multi-user sharing needed
- Tournament archiving/read-only mode
- Tournament templates (create new from existing)
- Tournament permissions/ownership
