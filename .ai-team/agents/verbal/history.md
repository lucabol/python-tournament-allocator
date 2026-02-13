# Project Context

- **Owner:** Luca Bolognese (lucabol@microsoft.com)
- **Project:** Python Flask tournament scheduling and management web application
- **Stack:** Python 3.11+, Flask, Jinja2, pandas, numpy, OR-Tools CP-SAT, PyYAML, pytest
- **Created:** 2026-02-11

## Learnings

<!-- Append new learnings below. Each entry is something lasting about the project. -->

### 2026-02-11: Multi-Tournament Design Review
- All data lives in flat files under `data/` with module-level constants (`DATA_DIR`, `TEAMS_FILE`, etc.)
- 6 pairs of `load_*/save_*` functions, ~30 routes, no file locking
- Export/import already uses ZIP archives — natural fit for tournament-as-directory
- Tests use `monkeypatch` to redirect 8+ module-level constants to temp dirs
- Decided: subdirectories per tournament (`data/tournaments/<slug>/`), session-based routing, `g.data_dir` parameterization
- Key trade-off: session-based (not URL-prefixed) to minimize code churn — revisit if multi-user sharing needed

### 2026-02-13: Improvement Brainstorm
- Full codebase review completed: ~40 routes, 11 nav items, 17 templates, 5 core modules
- Produced 22-idea brainstorm across UX/UI, New Features, Technical, and Mobile/Sharing categories
- Key themes: mobile navigation needs hamburger menu, tournament templates would save repeat setup, undo/edit for results is missing, dark mode requested
- See brainstorm output delivered to Luca for full list with effort estimates
