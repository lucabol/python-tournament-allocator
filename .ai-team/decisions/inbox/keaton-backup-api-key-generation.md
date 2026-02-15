### 2026-02-15: Auto-generate backup API key in deployment script
**By:** Keaton
**What:** Added automatic BACKUP_API_KEY generation to deploy.ps1 that checks Azure App Settings, generates a 32-byte random hex key if missing, sets it in Azure, and writes it to the local .env file.
**Why:** Ensures backup/restore HTTP endpoints are always secured with an API key without requiring manual key management. The script generates a cryptographically secure 64-character hex key on first deploy and syncs it between Azure and local environment. Subsequent deploys preserve the existing key to maintain access to backup operations.
