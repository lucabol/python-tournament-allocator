### 2026-02-15: Pre-restore backup location (server-side)
**By:** lucabol (via Copilot)
**What:** The pre-restore backup created by the Flask import route should be stored in `backups/` directory, not `/tmp`
**Why:** User preference — consistent with client-side backup location directive, improves visibility and Windows compatibility for all backup artifacts
