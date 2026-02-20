# Session: Team Setup & Design Review

**Date:** 2026-02-11
**Requested by:** Luca Bolognese

## Team Created

| Agent | Role |
|-------|------|
| Verbal | Lead |
| McManus | Backend |
| Fenster | Frontend |
| Hockney | Tester |

## Ceremony: Design Review — Multi-Tournament Support

Facilitator: Verbal. All agents participated.

## Architectural Decisions Made

1. Tournament data stored as subdirectories under `data/tournaments/<slug>/`
2. Tournaments identified by user-chosen name converted to filesystem slug
3. Session-based active tournament routing (not URL-prefixed)
4. Legacy data auto-migrated to "default" tournament on first startup
5. File paths parameterized via `g.data_dir` and `_file_path()` helper
