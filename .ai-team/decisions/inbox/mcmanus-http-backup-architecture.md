### 2026-02-14: HTTP backup/restore architecture with API key authentication

**By:** McManus  
**What:** Replaced Azure CLI SSH-based backup with HTTP routes secured by API key. Backup and restore operations now accessible via HTTP without requiring SSH access to the Azure container.

**Why:** The original CLI-based backup scripts (`backup-data.ps1`, `restore-data.ps1`) required SSH access to the Azure container using App Service credentials. This created operational friction — every backup/restore required looking up SSH credentials, enabling SSH on the App Service, and using `az webapp ssh` commands. HTTP-based backup allows:

1. **Simpler automation** — backup scripts can use standard HTTP tools (curl, PowerShell Invoke-WebRequest) without Azure CLI dependencies
2. **No SSH required** — reduces attack surface by not enabling SSH on production containers
3. **Scriptable from CI/CD** — GitHub Actions, scheduled tasks, or monitoring systems can trigger backups via HTTP without container access
4. **Same security model** — API key stored in Azure App Service application settings, timing-attack-safe comparison via `hmac.compare_digest()`

**Implementation details:**
- Export: `GET /api/admin/export` returns entire `DATA_DIR` as timestamped ZIP
- Import: `POST /api/admin/import` accepts ZIP upload, validates structure, backs up existing data before restoring
- Auth: `@require_backup_key` decorator checks `Authorization: Bearer <token>` header against `BACKUP_API_KEY` environment variable
- Security: Path traversal protection, ZIP validation, size limits (50MB), timing-attack-safe key comparison
- Backup on import: Creates `backups/pre-restore-{timestamp}/` copy before extracting uploaded ZIP

**Migration path:**
1. Generate API key: `python -c "import secrets; print(secrets.token_urlsafe(32))"`
2. Set in Azure: `az webapp config appsettings set --settings BACKUP_API_KEY='...'`
3. Update backup scripts to use HTTP instead of SSH
4. Optionally disable SSH on App Service once HTTP backup is verified

**Related files:**
- `src/app.py` — Flask routes and decorator
- `docs/http-backup-api.md` — API documentation
- `test_backup_routes.py` — Local testing script
- `scripts/backup-data.ps1`, `scripts/restore-data.ps1` — CLI scripts (can be updated to use HTTP)
