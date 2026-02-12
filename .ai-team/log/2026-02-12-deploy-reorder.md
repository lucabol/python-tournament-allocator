# 2026-02-12 — Deploy Reorder & Data Separation

**Requested by:** Luca Bolognese

## Summary

McManus reordered `deploy.ps1` configuration calls to fix a first-deploy race condition. Previously, `az webapp config set` and `az webapp config appsettings set` calls ran before `az webapp deploy`, triggering async container restarts during the Oryx remote build. On first deploy, this caused crash-loops because build artifacts didn't exist yet.

### Changes

- **Config after deploy:** Startup command, app settings, and `SECRET_KEY` configuration blocks moved to run after the zip deploy succeeds. Deploy order is now: create resources → zip package → upload & build → configure → propagation wait → cleanup.
- **Data separation (prior work):** `TOURNAMENT_DATA_DIR` environment variable added so Azure runtime data lives at `/home/data` (persistent) instead of `/home/site/wwwroot/data` (overwritten on deploy). Local dev is unaffected — env var defaults to `../data`.

### Verification

- 214 tests pass
- Committed and pushed to main
