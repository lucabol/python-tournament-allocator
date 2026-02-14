# CLI Backup & Restore for Azure App Service

This guide covers using Python CLI scripts to backup and restore Tournament Allocator data on Azure App Service deployments.

## Overview

The backup/restore approach uses **Azure CLI (az)** commands to SSH into your App Service container, create data archives, and manage recovery scenarios. This strategy is:

- **Scriptable** — automated scheduling via CI/CD pipelines or local cron/Task Scheduler
- **Safe** — pre-restore backups prevent accidental data loss
- **Flexible** — supports point-in-time recovery and multi-environment clones
- **CLI-first** — no web UI admin panel or special access credentials needed

Data lives in `/home/data` on Azure (persistent across deployments). The scripts target this directory directly.

## Prerequisites

### 1. Azure CLI Installation

Install [Azure CLI](https://learn.microsoft.com/en-us/cli/azure/install-azure-cli) for your OS:
- **Windows**: Download from https://aka.ms/InstallAzureCLI or use Chocolatey: `choco install azure-cli`
- **macOS**: `brew install azure-cli`
- **Linux**: Follow distro-specific instructions at the link above

Verify installation:
```bash
az --version
```

### 2. Azure Authentication

Log in with your Azure credentials:
```bash
az login
```

This opens a browser for interactive login. If you're in a headless environment, use:
```bash
az login --use-device-code
```

Verify authentication:
```bash
az account show
```

### 3. Have the App Service Details

You'll need:
- **App name** (e.g., `tournament-allocator-abc12345`)
- **Resource group** (e.g., `tournament-allocator-rg`)

Find these in the Azure Portal or via:
```bash
az webapp list --query "[].{name:name, group:resourceGroup}" -o table
```

## Backup Script Usage

**Location**: `scripts/backup.py`

### Basic Backup

Create a timestamped backup in the local `backups/` directory:
```bash
python scripts/backup.py \
  --app-name tournament-allocator-abc12345 \
  --resource-group tournament-allocator-rg
```

Output example:
```
Checking Azure CLI...
Verifying App Service: tournament-allocator-abc12345
Creating remote archive of /home/data...
Downloading archive from App Service...
Extracting archive...
Creating backup ZIP: backups/azure-backup-20260214-143022.zip
Backup created successfully: backups/azure-backup-20260214-143022.zip (2.34 MB)
```

### Custom Output Path

Specify where to save the backup:
```bash
python scripts/backup.py \
  --app-name tournament-allocator-abc12345 \
  --resource-group tournament-allocator-rg \
  --output /mnt/backup/my-backup.zip
```

### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Azure CLI not found or not authenticated |
| 2 | App Service connection failed or inaccessible |
| 3 | Backup write failure (disk full, permissions, etc.) |

## Restore Script Usage

**Location**: `scripts/restore.py`

### Standard Restore (with safety)

Restores a backup to the same App Service. Creates a pre-restore backup automatically:
```bash
python scripts/restore.py backups/azure-backup-20260214-143022.zip \
  --app-name tournament-allocator-abc12345 \
  --resource-group tournament-allocator-rg
```

This will:
1. Validate the ZIP file
2. Create a pre-restore backup (for safety)
3. Stop the App Service (prevents concurrent writes)
4. Upload and extract the backup
5. Validate all files were restored
6. Restart the App Service

Confirmation prompt:
```
⚠️  WARNING: This will replace all data on the App Service.
   Target: tournament-allocator-abc12345.azurewebsites.net

Type 'RESTORE' to continue:
```

Type `RESTORE` to proceed or any other text to cancel.

### Skip Pre-Restore Backup

If you're certain and don't want the extra backup:
```bash
python scripts/restore.py backups/azure-backup-20260214-143022.zip \
  --app-name tournament-allocator-abc12345 \
  --resource-group tournament-allocator-rg \
  --no-backup
```

**Not recommended** unless you've already created a manual backup.

### Force Restore (skip confirmation)

For unattended/scripted restores:
```bash
python scripts/restore.py backups/azure-backup-20260214-143022.zip \
  --app-name tournament-allocator-abc12345 \
  --resource-group tournament-allocator-rg \
  --force
```

### Exit Codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Invalid ZIP or Azure CLI not available |
| 2 | App Service connection failed |
| 3 | Restore operation failed (upload, extract, etc.) |
| 4 | Validation failed after restore |

## Common Scenarios

### 1. Disaster Recovery — Restore to Fresh Azure App Service

If the current App Service is corrupted, create a new one and restore data:

```bash
# 1. Deploy fresh app to new App Service (e.g., tournament-allocator-dr)
.\deploy.ps1  # Select new app name in .env

# 2. Wait for deployment to complete
# 3. Restore from backup
python scripts/restore.py backups/azure-backup-20260214-143022.zip \
  --app-name tournament-allocator-dr \
  --resource-group tournament-allocator-rg \
  --force
```

### 2. Staging Clone — Create Testing Environment

Backup production, restore to staging:

```bash
# 1. Backup production
python scripts/backup.py \
  --app-name tournament-allocator-prod \
  --resource-group tournament-allocator-rg \
  --output backups/prod-clone-$(Get-Date -Format "yyyyMMdd").zip

# 2. Restore to staging (pre-restore backup created automatically)
python scripts/restore.py backups/prod-clone-20260214.zip \
  --app-name tournament-allocator-staging \
  --resource-group tournament-allocator-rg
```

### 3. Scheduled Automated Backups

Use local Task Scheduler (Windows) or cron (Linux/macOS) to run backups daily.

#### Windows Task Scheduler

1. Create a batch script `C:\scripts\backup-tournament.bat`:
```batch
@echo off
cd C:\Users\lucabol\dev\python-tournament-allocator
python scripts/backup.py ^
  --app-name tournament-allocator-abc12345 ^
  --resource-group tournament-allocator-rg
```

2. Open Task Scheduler, create a basic task:
   - **Trigger**: Daily at 02:00 (off-hours)
   - **Action**: Run `C:\scripts\backup-tournament.bat`
   - **Repeat**: Every day

#### Linux/macOS Cron

Add to crontab (`crontab -e`):
```cron
# Daily backup at 2 AM
0 2 * * * cd /home/user/tournament-allocator && python scripts/backup.py \
  --app-name tournament-allocator-abc12345 \
  --resource-group tournament-allocator-rg
```

#### Azure DevOps Pipeline (Recommended)

Store backups to Azure Blob Storage for long-term retention:

```yaml
trigger:
  schedule:
    - cron: "0 2 * * *"
      displayName: Daily backup at 2 AM UTC
      branches:
        include:
        - main

jobs:
  - job: BackupTournamentData
    pool:
      vmImage: 'ubuntu-latest'
    steps:
      - checkout: self
      - task: UsePythonVersion@0
        inputs:
          versionSpec: '3.11'
      
      - script: python scripts/backup.py \
          --app-name $(APP_NAME) \
          --resource-group $(RESOURCE_GROUP) \
          --output $(Build.ArtifactStagingDirectory)/backup.zip
        displayName: 'Create backup'
        env:
          AZURE_DEVOPS_CLI_PAT: $(System.AccessToken)
      
      - task: AzureCLI@2
        inputs:
          azureSubscription: $(AZURE_SUBSCRIPTION)
          scriptType: bash
          scriptLocation: inlineScript
          inlineScript: |
            az storage blob upload \
              --account-name $(STORAGE_ACCOUNT) \
              --container-name backups \
              --name backup-$(date +%Y%m%d-%H%M%S).zip \
              --file $(Build.ArtifactStagingDirectory)/backup.zip
```

## Troubleshooting

### Error: "Azure CLI not found"
**Solution**: Install Azure CLI from https://aka.ms/InstallAzureCLI. Verify with `az --version`.

### Error: "Not authenticated with Azure CLI"
**Solution**: Run `az login` or `az login --use-device-code` to authenticate.

### Error: "Cannot access App Service"
**Causes**:
- Resource group or app name is wrong
- App Service doesn't exist in your subscription
- Your Azure account lacks permissions

**Solution**: Verify app and resource group exist:
```bash
az webapp list --query "[].{name:name, group:resourceGroup}" -o table
```

### Error: "Failed to create remote tar archive" or "Timeout while downloading"
**Causes**:
- App Service is very large (slow SSH connection)
- Network interruption
- App Service SSH is disabled (rare)

**Solution**: Try again after a few minutes, or manually SSH:
```bash
az webapp ssh --name tournament-allocator-abc12345 --resource-group tournament-allocator-rg
# Then run: tar -czf /tmp/data-backup.tar.gz -C /home data
```

### Error: "Invalid backup ZIP. Missing required files"
**Cause**: Backup ZIP is corrupted or from an older version.

**Solution**: Create a fresh backup using the latest `backup.py`.

### Error: "Validation failed: users.yaml not found after restore"
**Causes**:
- ZIP was corrupted during upload
- Disk space exhausted on App Service
- Extraction failed (permissions)

**Solution**: 
1. Check App Service storage: `az webapp log tail --name ... --resource-group ...`
2. Try restore again (or use pre-restore backup if interrupted)
3. Contact Azure support if persistent storage errors occur

### Restore Interrupted — App Service May Be in Inconsistent State
**If restore is interrupted (Ctrl+C), the App Service might have partial data.**

**Recovery**:
```bash
# Stop the service to prevent further writes
az webapp stop --name tournament-allocator-abc12345 --resource-group tournament-allocator-rg

# Restore from the pre-restore backup (created before the failed attempt)
python scripts/restore.py backups/pre-restore-*.zip \
  --app-name tournament-allocator-abc12345 \
  --resource-group tournament-allocator-rg \
  --force

# App will restart as part of the restore
```

## Migration from Admin Web Routes

**Prior approach** (deprecated): Web-based admin panel for backup/restore.

**New approach** (CLI-first): All backup/restore operations use the CLI scripts.

**Benefits**:
- No special admin credentials needed
- Works in CI/CD pipelines
- Scriptable and automatable
- Auditable (all commands are plain text)
- No web UI attack surface

**For existing users transitioning to CLI**:
1. Create a backup using the new `scripts/backup.py`
2. Test restore to a staging environment
3. Retire any web-based backup routes
4. Document backup/restore procedures using CLI scripts

## File Locations

| File | Purpose |
|------|---------|
| `scripts/backup.py` | Creates ZIP backup from `/home/data` |
| `scripts/restore.py` | Restores ZIP backup to `/home/data` |
| `backups/` | Local backup directory (created on first backup) |
| `/home/data` | App Service data directory (Azure only) |

## Security Best Practices

1. **Store backups securely**
   - Keep local backups in encrypted storage or cloud backup service
   - Don't store backups in source control
   - Rotate old backups (e.g., keep only last 30 days)

2. **Use strong Azure credentials**
   - Use `az login` with MFA-protected account
   - For unattended scripts, use managed identities or service principals
   - Never commit `.env` files with credentials to source control

3. **Test restores regularly**
   - Verify backups can be restored (don't just create them)
   - Test on staging before relying on production restores

4. **Monitor backup success**
   - Log backup output to a file: `backup.py ... > backup.log 2>&1`
   - Set up alerts if scheduled backups fail
   - Check backup file sizes (sudden drops may indicate problems)

## See Also

- [Azure CLI Documentation](https://learn.microsoft.com/en-us/cli/azure/)
- [Azure App Service Backup & Restore](https://learn.microsoft.com/en-us/azure/app-service/manage-backup)
- [Tournament Allocator README](../README.md)
