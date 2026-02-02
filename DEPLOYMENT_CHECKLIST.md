# Azure App Service Deployment Checklist

Use this checklist when deploying the Tournament Allocator to Azure App Service.

## Pre-Deployment

- [ ] Azure account created
- [ ] Azure CLI installed (if using CLI method) or access to Azure Portal
- [ ] Repository pushed to GitHub (for automated deployment)
- [ ] Review cost implications:
  - Free tier (F1): $0/month - testing only
  - Basic tier (B1): ~$13/month - recommended minimum
  - Standard tier (S1): ~$70/month - production with auto-scaling

## Azure Resource Creation

- [ ] Create Resource Group
  - Name: `tournament-rg` (or your preference)
  - Location: Choose closest region

- [ ] Create App Service Plan
  - Name: `tournament-plan` (or your preference)
  - OS: Linux
  - Runtime: Python 3.11
  - Pricing Tier: B1 or higher recommended

- [ ] Create Web App
  - Name: Choose unique name (e.g., `tournament-app-xyz`)
  - Runtime: Python 3.11
  - Region: Same as Resource Group

## App Service Configuration

- [ ] Set Startup Command:
  ```
  chmod +x /home/site/wwwroot/startup.sh && /home/site/wwwroot/startup.sh
  ```

- [ ] Configure Application Settings:
  - [ ] `FLASK_ENV=production`
  - [ ] `SECRET_KEY=<generate-secure-key>`
  - [ ] (Optional) Other environment variables from `.env.example`

- [ ] Enable Application Insights (optional but recommended):
  - Helps monitor performance and errors
  - Available in Azure Portal

## Deployment Setup

### Option A: GitHub Integration (Recommended)
- [ ] Go to Deployment Center in Azure Portal
- [ ] Select "GitHub" as source
- [ ] Authorize Azure to access GitHub
- [ ] Select repository: `lucabol/python-tournament-allocator`
- [ ] Select branch to deploy (e.g., `main`)
- [ ] Save configuration
- [ ] Verify first deployment completes successfully

### Option B: GitHub Actions
- [ ] Update `.github/workflows/azure-deploy.yml`:
  - [ ] Set `AZURE_WEBAPP_NAME` to your app name
- [ ] Get publish profile:
  - Go to App Service → Deployment Center → Manage publish profile → Download
- [ ] Add GitHub Secret:
  - Repository Settings → Secrets → New secret
  - Name: `AZURE_WEBAPP_PUBLISH_PROFILE`
  - Value: Contents of downloaded publish profile
- [ ] Push to main branch to trigger deployment

### Option C: Local Git
- [ ] Configure deployment credentials
- [ ] Get Git URL from Deployment Center
- [ ] Add remote: `git remote add azure <git-url>`
- [ ] Push: `git push azure main`

### Option D: Azure CLI
- [ ] Run deployment command:
  ```bash
  az webapp deployment source config \
    --name <app-name> \
    --resource-group tournament-rg \
    --repo-url https://github.com/lucabol/python-tournament-allocator \
    --branch main \
    --manual-integration
  ```

## Post-Deployment Verification

- [ ] Wait for deployment to complete (5-10 minutes for first deploy)
- [ ] Check deployment logs:
  - Portal: Deployment Center → Logs
  - CLI: `az webapp log tail --name <app-name> --resource-group tournament-rg`

- [ ] Verify app is running:
  - [ ] Visit `https://<app-name>.azurewebsites.net`
  - [ ] Check home page loads
  - [ ] Test navigation between tabs

- [ ] Test key functionality:
  - [ ] Teams page loads
  - [ ] Courts page loads
  - [ ] Can add test data (Load Test buttons)
  - [ ] Can generate schedule
  - [ ] Can view bracket

## Data Persistence (Important for Production!)

⚠️ **Default file storage is ephemeral** - data may be lost on restart.

### Option A: Azure Files Mount (Recommended)
- [ ] Create Storage Account:
  ```bash
  az storage account create \
    --name <unique-storage-name> \
    --resource-group tournament-rg \
    --sku Standard_LRS
  ```

- [ ] Create File Share:
  ```bash
  az storage share create \
    --name tournamentdata \
    --account-name <storage-name>
  ```

- [ ] Mount to App Service:
  ```bash
  az webapp config storage-account add \
    --resource-group tournament-rg \
    --name <app-name> \
    --custom-id TournamentData \
    --storage-type AzureFiles \
    --share-name tournamentdata \
    --account-name <storage-name> \
    --access-key <get-from-portal-or-cli> \
    --mount-path /home/site/wwwroot/data
  ```

- [ ] Restart app after mounting storage

### Option B: Backup Strategy
If using ephemeral storage, implement regular backups:
- [ ] Download data files periodically via FTP/FTPS
- [ ] Store in separate storage location
- [ ] Document restore procedure

## Performance Optimization

- [ ] Enable "Always On" (Basic tier and above):
  - Configuration → General settings → Always On: On
  - Prevents app from sleeping due to inactivity

- [ ] Configure Scale Up (if needed):
  - Scale up → Select higher tier for better performance

- [ ] Configure Scale Out (Standard tier and above):
  - Scale out → Add autoscale rules based on CPU/Memory

## Monitoring and Logging

- [ ] Enable detailed logging:
  - App Service logs → Application logging: File System
  - Detailed error messages: On
  - Failed request tracing: On

- [ ] Set up Application Insights (if not done earlier):
  - Monitoring → Application Insights → Turn on

- [ ] Configure alerts:
  - Monitor → Alerts → Create alert rule
  - Suggested alerts:
    - CPU usage > 80%
    - Memory usage > 80%
    - Response time > 5 seconds
    - HTTP 5xx errors

## Security

- [ ] Enable HTTPS only:
  - Configuration → General settings → HTTPS Only: On

- [ ] Configure authentication (optional):
  - Authentication → Add identity provider
  - Options: Azure AD, Microsoft, Google, Facebook, Twitter

- [ ] Review CORS settings (if needed):
  - CORS → Add allowed origins

- [ ] Configure IP restrictions (optional):
  - Networking → Access restrictions

## Custom Domain (Optional)

- [ ] Purchase/own a domain name
- [ ] Add custom domain in Azure:
  - Custom domains → Add custom domain
  - Follow DNS configuration steps
- [ ] Enable SSL:
  - TLS/SSL settings → Add certificate
  - Or use free App Service Managed Certificate

## Maintenance

- [ ] Set up backup schedule (if using Azure Files)
- [ ] Review logs regularly
- [ ] Monitor costs in Azure Cost Management
- [ ] Update dependencies periodically:
  - Update `requirements.txt`
  - Redeploy application
  
- [ ] Plan for Python runtime updates:
  - Azure periodically updates Python versions
  - Test with new versions before upgrading

## Troubleshooting Steps

If deployment fails:
- [ ] Check deployment logs in Deployment Center
- [ ] Verify startup command is set correctly
- [ ] Check application logs: `az webapp log tail`
- [ ] Verify all dependencies in requirements.txt
- [ ] Test locally with gunicorn before redeploying

If app is slow:
- [ ] Upgrade to B1 or higher tier
- [ ] Enable "Always On"
- [ ] Check Application Insights for bottlenecks
- [ ] Consider using Azure CDN for static files

If data is lost:
- [ ] Implement Azure Files mount (see Data Persistence section)
- [ ] Or migrate to Azure SQL Database

## Cost Management

- [ ] Review Azure Cost Management dashboard weekly
- [ ] Set up budget alerts:
  - Cost Management → Budgets → Add budget
  - Set threshold alerts (e.g., 80% of budget)

- [ ] Consider shutting down dev/test environments when not in use:
  - Stop: `az webapp stop --name <app-name> --resource-group tournament-rg`
  - Start: `az webapp start --name <app-name> --resource-group tournament-rg`

## Documentation

- [ ] Document app URL and access information
- [ ] Document deployment process for team
- [ ] Keep list of application settings/environment variables
- [ ] Document any custom configurations or changes

## Rollback Plan

In case of issues:
- [ ] Know how to rollback via Deployment Center
- [ ] Keep previous working commit hash documented
- [ ] Test rollback procedure

---

## Quick Reference

### View Logs
```bash
az webapp log tail --name <app-name> --resource-group tournament-rg
```

### Restart App
```bash
az webapp restart --name <app-name> --resource-group tournament-rg
```

### View Configuration
```bash
az webapp config show --name <app-name> --resource-group tournament-rg
```

### SSH into App Container
```bash
az webapp ssh --name <app-name> --resource-group tournament-rg
```

### Download Log Files
Portal: App Service → Development Tools → Advanced Tools (Kudu) → Debug console → LogFiles
