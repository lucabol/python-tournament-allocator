# Backup/Restore Architecture Options

**Date:** 2025-07-15
**Requested by:** lucabol
**Status:** Analysis / Recommendation

---

## Current State

The existing `scripts/backup.py` uses Azure CLI SSH to tar/download `/home/data`. This approach is:
- Fragile on Windows (`az.cmd` subprocess issues)
- Complex (requires Azure CLI installed + authenticated)
- Unreliable (SSH piping of binary tar data through interactive shell)

**What already exists in the codebase:**
- Per-tournament export/import: `GET /api/export/tournament` → ZIP download, `POST /api/import/tournament` → ZIP upload
- Per-user export/import: `GET /api/export/user` → ZIP download, `POST /api/import/user` → ZIP upload
- Session-based auth with `login_required` decorator
- `SITE_EXPORT_SKIP`, `MAX_SITE_UPLOAD_SIZE` constants already defined (suggesting site-wide export was planned)
- Data structure: `data/users.yaml`, `data/users/{username}/tournaments/{slug}/*.yaml|csv`
- Typical size: < 50 MB

---

## Options (ranked by simplicity)

### Option 1: Web Route — Site-Wide ZIP Export/Import (Admin Route)

**Approach:** Add two Flask routes (`GET /api/export/site`, `POST /api/import/site`) that ZIP/unzip the entire `data/` directory. Protect with an admin check (e.g., first registered user, or a role flag in `users.yaml`). Operator downloads backup via browser or `curl`.

**Implementation complexity:** Low

**Security considerations:**
- Reuse existing session auth; add admin-only gate
- Path traversal checks on import (pattern already exists in `api_import_user`)
- Rate-limit or add CSRF token for the import endpoint
- ZIP bomb protection via `MAX_SITE_UPLOAD_SIZE` (already defined at 50 MB)

**Pros:**
- Minimal new code — follows the exact pattern of existing `/api/export/user` and `/api/import/user`
- No external dependencies (no Azure CLI, no Azure SDK, no FTP)
- Cross-platform: works from any browser or `curl`/`Invoke-WebRequest`
- Constants `SITE_EXPORT_SKIP` and `MAX_SITE_UPLOAD_SIZE` already exist
- Scriptable: `curl -b cookies.txt https://app/api/export/site -o backup.zip`

**Cons:**
- Requires the app to be running (can't backup a crashed app)
- Entire data dir in memory during ZIP creation (fine for < 50 MB)
- Must implement admin concept (currently no role system)

**Best for:** Day-to-day operational backups, migration between instances, most common use case.

---

### Option 2: Web Route with API Key (Token-Based, No Login)

**Approach:** Same ZIP export/import routes, but secured with a pre-shared API key set as an Azure App Setting (environment variable). No session/cookie needed — just `Authorization: Bearer <key>` header.

**Implementation complexity:** Low

**Security considerations:**
- API key stored as Azure App Setting (encrypted at rest)
- Key transmitted over HTTPS only (Azure enforces TLS)
- No session management needed — simpler auth surface
- Consider key rotation mechanism

**Pros:**
- Simplest possible scripting: `curl -H "Authorization: Bearer $KEY" https://app/api/export/site -o backup.zip`
- No need to implement admin roles or login flow
- Works from PowerShell, bash, Python, scheduled tasks — anything with HTTP
- Can be added alongside session-based routes (not mutually exclusive)

**Cons:**
- API key management (must be set in Azure portal or deploy script)
- Single key = all-or-nothing access (no per-user audit trail)
- Key in env var could leak via process listing (low risk on App Service)

**Best for:** Automated/scheduled backups, CI/CD pipelines, headless scripts.

---

### Option 3: Azure App Service Built-in Backup Feature

**Approach:** Use Azure's native App Service backup, which snapshots the app + `/home` persistent storage to an Azure Storage account. Configure via Azure Portal or ARM template.

**Implementation complexity:** Low (configuration only, no code changes)

**Security considerations:**
- Managed by Azure RBAC — inherits subscription security
- Backups stored in Azure Storage with encryption at rest
- Restore via Azure Portal (requires Azure subscription access)

**Pros:**
- Zero code changes
- Automatic scheduling (daily, hourly, etc.)
- Includes app configuration + data
- Point-in-time restore possible

**Cons:**
- Requires **Standard tier or higher** (not available on Basic/Free/Shared)
- Current deploy uses `B1` (Basic) — would need tier upgrade ($$$)
- Restore is all-or-nothing (replaces entire app)
- Cannot selectively restore just data files
- Requires Azure Portal access for restore (not scriptable for operators)
- Overkill for < 50 MB of YAML/CSV files

**Best for:** Enterprise deployments on Standard+ tier where full app snapshots are needed.

---

### Option 4: Azure Blob Storage Sync

**Approach:** Add a scheduled task or route that uploads the `data/` directory to Azure Blob Storage using the Azure Storage SDK (`azure-storage-blob`). Optionally mount blob storage as a filesystem.

**Implementation complexity:** Medium

**Security considerations:**
- Connection string stored as App Setting
- Blobs encrypted at rest (Azure default)
- SAS tokens for time-limited download access
- Container-level access policies

**Pros:**
- Versioned backups (blob snapshots or date-prefixed paths)
- Can be automated via Azure Functions timer or in-app scheduler
- Restore possible without app running (download from blob directly)
- Blob storage is cheap (~$0.02/GB/month)

**Cons:**
- New dependency: `azure-storage-blob` SDK
- Requires Azure Storage account provisioning
- More complex deploy script (storage account + connection string)
- Adds cloud coupling for a simple data backup need

**Best for:** Scenarios requiring off-app backup storage, regulatory retention, or backup-even-if-app-is-down guarantees.

---

### Option 5: FTPS to /home/data

**Approach:** Use Azure App Service's built-in FTPS access to directly download/upload files from `/home/data`. Credentials available in Azure Portal under Deployment Center.

**Implementation complexity:** Low (no code changes)

**Security considerations:**
- FTPS (TLS-encrypted) — Azure disables plain FTP by default
- Credentials are per-app deployment credentials
- Scoped to `/home` directory (can't escape)

**Pros:**
- Zero code changes
- Direct file access — can selectively backup/restore individual files
- Works with any FTP client (FileZilla, WinSCP, `lftp`, PowerShell)
- Azure provides this out of the box on all tiers

**Cons:**
- FTP client required (not as universal as `curl`)
- Credential management (deployment credentials in Azure Portal)
- No atomic backup (files copied one-by-one, possible inconsistency)
- Scripting FTP is more awkward than HTTP
- Doesn't create a single archive — user must zip manually

**Best for:** Ad-hoc file-level access, debugging, quick one-off downloads.

---

### Option 6: PowerShell/Python Script Using Azure REST API (Kudu API)

**Approach:** Replace `az webapp ssh` with direct HTTP calls to Kudu's VFS API (`https://<app>.scm.azurewebsites.net/api/vfs/data/`). Kudu exposes a REST API for file operations. Auth via deployment credentials (Basic auth over HTTPS).

**Implementation complexity:** Medium

**Security considerations:**
- Basic auth over HTTPS to Kudu SCM site
- Deployment credentials (not subscription-level — scoped to app)
- SCM site has its own auth gate

**Pros:**
- No Azure CLI dependency — pure HTTP requests
- Cross-platform (PowerShell `Invoke-WebRequest` or Python `requests`)
- Can download individual files or directory listings
- More reliable than SSH piping

**Cons:**
- Kudu VFS API returns files one-at-a-time (must iterate directory tree)
- No built-in "download entire directory as ZIP" in VFS API (must build it client-side)
- Kudu API can be slow for many small files
- Still requires Azure deployment credentials
- More complex than a single web route

**Best for:** When you need Azure-side backup without CLI but don't want to add routes to the app.

---

### Option 7: Hybrid — Web Route + Local Script Wrapper

**Approach:** Implement Option 1 or 2 (web routes) in the app, then provide a thin local script (`scripts/backup.py`) that wraps `curl`/`requests` to call those routes. The script handles timestamping, file naming, and credential prompting.

**Implementation complexity:** Low–Medium

**Security considerations:**
- Inherits security from the web route (session auth or API key)
- Script stores no credentials (prompts or reads from `.env`)
- HTTPS enforced by Azure

**Pros:**
- Best of both worlds: simple web routes + nice CLI UX
- Script can add local conveniences (auto-naming, backup rotation, progress bars)
- Replaces current `scripts/backup.py` cleanly
- Scriptable for cron/Task Scheduler

**Cons:**
- Two things to maintain (routes + script)
- Script needs `requests` or relies on `curl`

**Best for:** Power users who want CLI convenience backed by simple web infrastructure.

---

## Comparison Matrix

| Option | Complexity | Code Changes | Azure Dependencies | Works If App Down | Scriptable | Cross-Platform |
|--------|-----------|-------------|-------------------|------------------|------------|---------------|
| 1. Web Route (session) | Low | ~60 lines | None | ❌ | ⚠️ (cookies) | ✅ |
| 2. Web Route (API key) | Low | ~50 lines | App Setting | ❌ | ✅ | ✅ |
| 3. Azure Built-in Backup | Low | 0 lines | Standard tier+ | ✅ | ❌ | N/A |
| 4. Blob Storage Sync | Medium | ~100 lines | Storage account | ✅ (blobs) | ✅ | ✅ |
| 5. FTPS | Low | 0 lines | None | ❌ | ⚠️ (FTP client) | ✅ |
| 6. Kudu REST API | Medium | ~150 lines | Credentials | ❌ | ✅ | ✅ |
| 7. Hybrid (Route + Script) | Low–Med | ~80 lines | Depends on route | ❌ | ✅ | ✅ |

---

## Recommendation

**Primary: Option 2 (Web Route with API Key)** — optionally combined with **Option 7 (thin script wrapper)**.

### Rationale

1. **Fits the codebase perfectly.** The app already has `/api/export/user` and `/api/import/user` with ZIP logic, `SITE_EXPORT_SKIP` and `MAX_SITE_UPLOAD_SIZE` constants, and all required imports (`zipfile`, `send_file`, `io`). Adding site-wide routes is ~50 lines following the existing pattern.

2. **API key is simplest for scripting.** The current pain is Windows subprocess issues with `az.cmd`. An API key + HTTPS eliminates all Azure CLI, SSH, and subprocess dependencies. A backup becomes:
   ```powershell
   Invoke-WebRequest -Uri "https://app.azurewebsites.net/api/admin/export" `
     -Headers @{ Authorization = "Bearer $env:BACKUP_KEY" } `
     -OutFile "backup-$(Get-Date -Format yyyyMMdd).zip"
   ```

3. **Security is adequate.** The API key lives as an Azure App Setting (encrypted at rest, not in code). All traffic is HTTPS. The key can be rotated by changing the App Setting. For a tournament organizer app with < 50 MB of data, this is proportionate security.

4. **No new dependencies.** No Azure SDK, no FTP client, no Azure CLI. Just HTTP.

5. **Future-proof.** If you later want session-based admin access (Option 1), you can add it alongside the API key route — they're not mutually exclusive.

### Implementation Sketch

```python
BACKUP_API_KEY = os.environ.get('BACKUP_API_KEY', '')

def require_backup_key(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        auth = request.headers.get('Authorization', '')
        if not BACKUP_API_KEY or not auth.startswith('Bearer '):
            abort(401)
        if not hmac.compare_digest(auth[7:], BACKUP_API_KEY):
            abort(403)
        return f(*args, **kwargs)
    return decorated

@app.route('/api/admin/export')
@require_backup_key
def api_admin_export():
    """Export entire data directory as ZIP."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(DATA_DIR):
            dirs[:] = [d for d in dirs if d not in SITE_EXPORT_SKIP]
            for fname in files:
                if any(fname.endswith(s) for s in SITE_EXPORT_SKIP):
                    continue
                full = os.path.join(root, fname)
                arc = os.path.relpath(full, DATA_DIR)
                zf.write(full, arc)
    buffer.seek(0)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    return send_file(buffer, mimetype='application/zip',
                     as_attachment=True, download_name=f'site_backup_{ts}.zip')
```

### Migration Path

1. Add `BACKUP_API_KEY` to deploy script as an App Setting
2. Add export/import routes to `app.py` (~50 lines)
3. Replace `scripts/backup.py` with a thin HTTP wrapper
4. Delete the Azure CLI SSH backup code
