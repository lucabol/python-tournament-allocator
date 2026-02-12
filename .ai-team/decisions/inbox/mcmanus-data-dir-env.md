# Decision: DATA_DIR configurable via TOURNAMENT_DATA_DIR env var

**By:** McManus
**Date:** 2026-02-11

## What
`DATA_DIR` in `src/app.py` is now sourced from the `TOURNAMENT_DATA_DIR` environment variable, falling back to the original `os.path.join(BASE_DIR, 'data')` for local development.

On Azure, `deploy.ps1` sets `TOURNAMENT_DATA_DIR=/home/data` and no longer bundles `data/` in the deploy zip. `startup.sh` ensures the directory exists on first boot.

## Why
Deploys were overwriting user tournament data. Azure App Service's `/home` filesystem is persistent across deploys, but `/home/site/wwwroot` is replaced on each deploy. Moving runtime data to `/home/data` keeps it safe.

## Impact
- **Local dev**: Zero change. Env var is unset, so `DATA_DIR` resolves to `../data` as before.
- **Azure**: Data now lives at `/home/data`. First deploy after this change will start with an empty data dir — the migration code in `ensure_tournament_structure()` will create the default tournament automatically.
- **All agents**: If you add new file paths that depend on `DATA_DIR`, they'll automatically respect the env var. No action needed.
