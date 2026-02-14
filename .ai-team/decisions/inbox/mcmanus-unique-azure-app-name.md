### 2026-02-14: Azure app name uniqueness via subscription prefix

**By:** McManus  
**What:** Changed `deploy.ps1` to generate app names as `tournament-allocator-{8-char-sub-id-prefix}` by default instead of hardcoded "tournament-allocator".  
**Why:** Azure App Service names must be globally unique across all Azure. The hardcoded name caused deployment collisions. Using subscription ID prefix makes the name deterministic, readable, and globally unique. Users can still override via `AZURE_APP_NAME` in `.env`.
