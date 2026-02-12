### deploy.ps1: Config calls moved after zip deploy

**By:** McManus
**Date:** 2026-02-11
**What:** Reordered `deploy.ps1` so that all `az webapp config set` / `az webapp config appsettings set` calls run AFTER `az webapp deploy` succeeds, not before.
**Why:** Each config change triggers an async container restart on Azure App Service. On first deploy, the Oryx remote build (installing numpy/pandas/ortools) takes several minutes. If config triggers a restart before the build completes, the container boots with no artifacts and crashes. Moving config after deploy ensures build artifacts exist when the first config-triggered restart happens.
**Impact:** No functional change to the app itself. Deploy order is now: create resources → zip package → upload & build → configure → propagation wait → cleanup. First deploys should no longer crash-loop.
