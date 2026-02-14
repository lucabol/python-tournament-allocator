# Azure Oryx Build Timing

**By:** McManus  
**Date:** 2026-02-14

## Decision

`SCM_DO_BUILD_DURING_DEPLOYMENT=true` must be set BEFORE running `az webapp deploy`, not after.

## Context

The Azure deployment was uploading the zip successfully (including requirements.txt at root), but the app crashed with `ModuleNotFoundError: No module named 'yaml'`. The Oryx build system was never running - evidenced by the error `WARNING: Could not find package directory /home/site/wwwroot/__oryx_packages__`.

## Root Cause

Azure's Kudu service checks the `SCM_DO_BUILD_DURING_DEPLOYMENT` app setting at the moment it receives the zip file via `az webapp deploy`. If the setting is true, Kudu invokes Oryx to detect the project type (Python) and run the build (`pip install -r requirements.txt`). If the setting is false or unset, Kudu just extracts the zip without building.

Our deploy.ps1 was setting this flag AFTER the deploy, which meant:
1. Deploy runs without the flag set → Oryx doesn't run
2. Flag gets set afterward → Too late, deploy already happened

## Solution Pattern

Split app settings into two timing groups:

1. **Build-time settings** (set BEFORE deploy):
   - `SCM_DO_BUILD_DURING_DEPLOYMENT=true`

2. **Runtime settings** (set AFTER deploy):
   - Startup command (`startup.sh`)
   - Environment variables (`TOURNAMENT_DATA_DIR`, `SECRET_KEY`)
   - Other runtime configs

## Why This Separation?

- Build-time settings control what happens during zip extraction — must be in place before upload
- Runtime settings trigger container restarts — better to set after build completes to avoid race conditions
- The original intent (avoid restarts mid-build) was correct, but `SCM_DO_BUILD_DURING_DEPLOYMENT` was miscategorized as runtime

## Files Changed

- `deploy.ps1` — moved `SCM_DO_BUILD_DURING_DEPLOYMENT` to before deploy, kept other settings after

## Future Deployments

When adding new Azure app settings, categorize them:
- Does it affect how the deployment package is processed? → Set BEFORE deploy
- Does it affect app runtime behavior? → Set AFTER deploy
