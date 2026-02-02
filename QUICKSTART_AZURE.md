# Quick Start: Deploy to Azure App Service

This is a quick reference guide for deploying the Tournament Allocator to Azure App Service. For detailed instructions, see [AZURE_DEPLOYMENT.md](./AZURE_DEPLOYMENT.md).

## Fastest Method: Azure Portal with GitHub

### 1. Create the App Service (5 minutes)

1. Go to https://portal.azure.com
2. Click **"Create a resource"** → Search for **"Web App"**
3. Configure:
   - **Name**: `<your-unique-name>` (e.g., tournament-app-123)
   - **Runtime**: Python 3.11
   - **OS**: Linux
   - **Pricing**: B1 Basic ($13/month recommended) or F1 Free (for testing)
4. Click **"Review + Create"** → **"Create"**

### 2. Connect GitHub (2 minutes)

1. In your new App Service, go to **"Deployment Center"**
2. Select **"GitHub"** as source
3. Authorize and select:
   - **Repository**: `lucabol/python-tournament-allocator`
   - **Branch**: `main` (or your branch)
4. Click **"Save"**

### 3. Configure Startup (1 minute)

1. Go to **"Configuration"** → **"General settings"**
2. Set **Startup Command**:
   ```
   chmod +x /home/site/wwwroot/startup.sh && /home/site/wwwroot/startup.sh
   ```
3. Click **"Save"** → **"Continue"**

### 4. Access Your App

Visit: `https://<your-app-name>.azurewebsites.net`

First deployment takes 5-10 minutes (installing ortools is slow).

## Using Azure CLI (Alternative)

```bash
# Login
az login

# Create everything
az group create --name tournament-rg --location eastus

az appservice plan create --name tournament-plan --resource-group tournament-rg --sku B1 --is-linux

az webapp create --resource-group tournament-rg --plan tournament-plan --name <your-app-name> --runtime "PYTHON|3.11"

az webapp config set --resource-group tournament-rg --name <your-app-name> --startup-file "chmod +x /home/site/wwwroot/startup.sh && /home/site/wwwroot/startup.sh"

az webapp deployment source config --name <your-app-name> --resource-group tournament-rg --repo-url https://github.com/lucabol/python-tournament-allocator --branch main --manual-integration

# View logs
az webapp log tail --name <your-app-name> --resource-group tournament-rg
```

## Important Notes

⚠️ **Data Persistence**: By default, file storage is temporary. For production:
- Mount Azure Files for persistent storage (see full guide)
- Or migrate to Azure SQL Database

🐌 **First Deploy**: Takes 5-10 minutes due to ortools installation

💰 **Cost**: 
- Free (F1): $0 but limited and slow
- Basic (B1): ~$13/month - recommended minimum

📊 **Monitoring**: Enable "Always On" in Configuration (Basic tier+) for better performance

## Troubleshooting

**App not starting?**
```bash
az webapp log tail --name <your-app-name> --resource-group tournament-rg
```

**Slow performance?**
- Upgrade to B1 or higher tier
- Enable "Always On" setting

For detailed troubleshooting, see [AZURE_DEPLOYMENT.md](./AZURE_DEPLOYMENT.md#troubleshooting)
