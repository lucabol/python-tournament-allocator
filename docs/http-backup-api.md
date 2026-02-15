# HTTP Backup/Restore API

Flask routes for backing up and restoring the entire tournament data directory via HTTP.

## Authentication

All admin routes require the `BACKUP_API_KEY` environment variable to be set on the server.

**Header format:**
```
Authorization: Bearer <your-api-key>
```

The decorator uses `hmac.compare_digest()` for timing-attack-safe comparison.

## Routes

### GET `/api/admin/export`

Export the entire `DATA_DIR` as a timestamped ZIP file.

**Example:**
```bash
curl -H "Authorization: Bearer your-key-here" \
     http://localhost:5000/api/admin/export \
     -o tournament-backup.zip
```

**Response:**
- Success: ZIP file download with name `tournament-backup-{timestamp}.zip`
- 401: Invalid or missing API key
- 404: Data directory doesn't exist
- 500: Server not configured (BACKUP_API_KEY not set)

### POST `/api/admin/import`

Restore the entire `DATA_DIR` from an uploaded ZIP file.

**Creates a backup** of existing data before restoring to `backups/pre-restore-{timestamp}/`

**Example:**
```bash
curl -H "Authorization: Bearer your-key-here" \
     -F "file=@tournament-backup.zip" \
     http://localhost:5000/api/admin/import
```

**Response:**
```json
{
  "success": true,
  "backup_location": "/path/to/backups/pre-restore-20240101_120000",
  "message": "Data restored successfully. Previous data backed up to /path/to/backups/pre-restore-20240101_120000"
}
```

**Error responses:**
- 400: No file, file too large (>50MB), invalid ZIP, unsafe paths, or missing required files
- 401: Invalid or missing API key
- 500: Server not configured

## Security Features

1. **HMAC comparison** - Timing-attack-safe key validation
2. **Path traversal protection** - Rejects ZIPs with `..`, `/`, or `\` in paths
3. **ZIP validation** - Verifies uploaded file is a valid ZIP before processing
4. **Structural validation** - Ensures ZIP contains `tournaments.yaml` or `users.yaml`
5. **Size limit** - Maximum 50MB upload (configurable via `MAX_SITE_UPLOAD_SIZE`)

## Testing

Use the provided test script:

```bash
# Set the API key
export BACKUP_API_KEY='test-key-12345'

# Start Flask (in one terminal)
python src/app.py

# Run tests (in another terminal)
export BACKUP_API_KEY='test-key-12345'
python test_backup_routes.py
```

The test script verifies:
- ✅ Authentication (valid key, invalid key, missing header)
- ✅ Export returns valid ZIP file
- ✅ Import validation (missing file, invalid ZIP)

## Differences from User Routes

| Feature | User Routes | Admin Routes |
|---------|------------|--------------|
| **Scope** | `data/users/{username}/tournaments/` | Entire `data/` directory |
| **Auth** | Session-based (`@login_required`) | API key (`@require_backup_key`) |
| **Route prefix** | `/api/export/user`, `/api/import/user` | `/api/admin/export`, `/api/admin/import` |
| **Response type** | HTML redirect with flash messages | JSON response |

## Implementation Details

- **Compression:** `zipfile.ZIP_DEFLATED` (same as user routes)
- **Skip patterns:** `.lock`, `.pyc`, `__pycache__` excluded from archives
- **Backup location:** `{BASE_DIR}/backups/pre-restore-{timestamp}/`
- **Path resolution:** Uses existing `DATA_DIR` and `BASE_DIR` globals
- **Error handling:** Returns JSON errors with appropriate HTTP status codes

## Local Testing Workflow

1. Generate an API key:
   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```

2. Set it in your environment:
   ```bash
   export BACKUP_API_KEY='your-generated-key'
   ```

3. Start Flask:
   ```bash
   python src/app.py
   ```

4. Test export:
   ```bash
   curl -H "Authorization: Bearer your-generated-key" \
        http://localhost:5000/api/admin/export \
        -o backup.zip
   ```

5. Verify ZIP contents:
   ```bash
   unzip -l backup.zip
   ```

6. Test import:
   ```bash
   curl -H "Authorization: Bearer your-generated-key" \
        -F "file=@backup.zip" \
        http://localhost:5000/api/admin/import
   ```

## Azure Deployment

When deploying to Azure App Service, set the API key via:

```bash
az webapp config appsettings set \
  --resource-group <group> \
  --name <app-name> \
  --settings BACKUP_API_KEY='<your-key>'
```

Or via the Azure Portal: App Service → Configuration → Application settings → New application setting
