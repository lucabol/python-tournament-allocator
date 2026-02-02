# Azure App Service Deployment Guide

This guide explains how to deploy the Tournament Allocator Flask application to Azure App Service.

## Prerequisites

- Azure subscription
- Azure CLI installed (`az cli`) or access to Azure Portal
- Git installed locally

## Option 1: Deploy via Azure Portal (Easiest)

### Step 1: Create an App Service

1. Go to [Azure Portal](https://portal.azure.com)
2. Click "Create a resource" → Search for "Web App"
3. Fill in the details:
   - **Subscription**: Select your subscription
   - **Resource Group**: Create new or select existing
   - **Name**: Choose a unique name (e.g., `tournament-allocator-app`)
   - **Publish**: Code
   - **Runtime stack**: Python 3.11
   - **Operating System**: Linux
   - **Region**: Choose closest to your location
   - **Pricing Plan**: 
     - For testing: F1 (Free) - Limited resources, may be slow with ortools
     - Recommended: B1 (Basic) - $13/month, better performance
     - For production: S1 (Standard) - $70/month, includes auto-scaling

4. Click "Review + Create" → "Create"

### Step 2: Configure Deployment

After the App Service is created:

1. Go to your App Service in the Portal
2. Navigate to "Deployment Center" in the left menu
3. Choose your deployment source:
   - **GitHub**: Connect your repository (recommended for continuous deployment)
   - **Local Git**: Deploy from local Git repository
   - **Azure DevOps**: Use Azure Pipelines

#### For GitHub Deployment:
1. Select "GitHub" as source
2. Authorize Azure to access your GitHub account
3. Select:
   - **Organization**: Your GitHub username/org
   - **Repository**: `python-tournament-allocator`
   - **Branch**: `main` or your preferred branch
4. Click "Save"

Azure will automatically deploy your code and run builds.

### Step 3: Configure Startup Command

1. In your App Service, go to "Configuration" → "General settings"
2. Set **Startup Command**: 
   ```bash
   chmod +x /home/site/wwwroot/startup.sh && /home/site/wwwroot/startup.sh
   ```
3. Click "Save"

### Step 4: Configure Application Settings (Optional)

If you need to customize settings:

1. Go to "Configuration" → "Application settings"
2. Add new application settings as needed:
   - `FLASK_ENV`: `production`
   - `SECRET_KEY`: Generate a secure random key
   - Any other environment variables your app needs

### Step 5: Monitor Deployment

1. Go to "Deployment Center" → "Logs" to see deployment progress
2. Once deployed, visit your app at: `https://<your-app-name>.azurewebsites.net`

## Option 2: Deploy via Azure CLI

### Prerequisites
```bash
# Install Azure CLI if not already installed
# For Windows: Download from https://aka.ms/installazurecliwindows
# For Mac: brew install azure-cli
# For Linux: curl -sL https://aka.ms/InstallAzureCLIDeb | sudo bash

# Login to Azure
az login
```

### Step 1: Create Resource Group
```bash
az group create --name tournament-rg --location eastus
```

### Step 2: Create App Service Plan
```bash
# For Basic tier (B1) - Recommended
az appservice plan create \
  --name tournament-plan \
  --resource-group tournament-rg \
  --sku B1 \
  --is-linux

# For Free tier (F1) - For testing only
az appservice plan create \
  --name tournament-plan \
  --resource-group tournament-rg \
  --sku F1 \
  --is-linux
```

### Step 3: Create Web App
```bash
az webapp create \
  --resource-group tournament-rg \
  --plan tournament-plan \
  --name <your-unique-app-name> \
  --runtime "PYTHON|3.11"
```

### Step 4: Configure Startup Command
```bash
az webapp config set \
  --resource-group tournament-rg \
  --name <your-app-name> \
  --startup-file "chmod +x /home/site/wwwroot/startup.sh && /home/site/wwwroot/startup.sh"
```

### Step 5: Deploy from GitHub (Recommended)
```bash
# Configure GitHub deployment
az webapp deployment source config \
  --name <your-app-name> \
  --resource-group tournament-rg \
  --repo-url https://github.com/<your-username>/python-tournament-allocator \
  --branch main \
  --manual-integration
```

### Step 6: Deploy from Local Git
```bash
# Get deployment credentials
az webapp deployment user set \
  --user-name <your-username> \
  --password <your-password>

# Configure local git deployment
az webapp deployment source config-local-git \
  --name <your-app-name> \
  --resource-group tournament-rg

# This will output a Git URL, add it as a remote
git remote add azure <git-url-from-above>

# Deploy
git push azure main
```

## Option 3: Deploy via VS Code

1. Install the "Azure App Service" extension in VS Code
2. Sign in to your Azure account
3. Right-click on your project folder
4. Select "Deploy to Web App..."
5. Follow the prompts to create or select an App Service
6. VS Code will handle the deployment automatically

## Important Considerations

### 1. Data Persistence

**⚠️ WARNING**: By default, App Service file storage is **ephemeral** - files written to the filesystem may be lost during restarts or scale operations.

For production use, consider one of these options:

#### Option A: Azure Files Mount (Recommended)
Mount an Azure Files share to persist the `data/` directory:

```bash
# Create storage account
az storage account create \
  --name tournamentstg \
  --resource-group tournament-rg \
  --sku Standard_LRS

# Create file share
az storage share create \
  --name tournamentdata \
  --account-name tournamentstg

# Mount to App Service
az webapp config storage-account add \
  --resource-group tournament-rg \
  --name <your-app-name> \
  --custom-id TournamentData \
  --storage-type AzureFiles \
  --share-name tournamentdata \
  --account-name tournamentstg \
  --access-key <storage-key> \
  --mount-path /home/site/wwwroot/data
```

#### Option B: Azure Blob Storage
Modify the application to use Azure Blob Storage instead of local files:
- Store YAML/CSV files as blobs
- Requires code changes to use Azure SDK

#### Option C: Azure Database
Convert data storage to use Azure SQL Database or Cosmos DB:
- Better for production use
- Requires significant code refactoring

### 2. Performance

The `ortools` package is large (~100MB) and may take time to install. Consider:
- Using at least B1 tier for acceptable performance
- Enabling "Always On" in Configuration → General settings (available in Basic tier and above)

### 3. Logging

View application logs:

```bash
# Via Azure CLI
az webapp log tail --name <your-app-name> --resource-group tournament-rg

# Via Portal
# Go to App Service → Monitoring → Log stream
```

Enable detailed logging:
```bash
az webapp log config \
  --name <your-app-name> \
  --resource-group tournament-rg \
  --application-logging filesystem \
  --detailed-error-messages true \
  --failed-request-tracing true \
  --web-server-logging filesystem
```

### 4. Environment Variables

Set environment variables (application settings) via CLI:
```bash
az webapp config appsettings set \
  --resource-group tournament-rg \
  --name <your-app-name> \
  --settings FLASK_ENV=production SECRET_KEY=your-secret-key
```

Or via Portal:
- Navigate to Configuration → Application settings → New application setting

### 5. Custom Domain (Optional)

To use a custom domain:

```bash
# Add custom domain
az webapp config hostname add \
  --webapp-name <your-app-name> \
  --resource-group tournament-rg \
  --hostname <your-domain.com>

# Enable HTTPS
az webapp config ssl bind \
  --certificate-thumbprint <thumbprint> \
  --ssl-type SNI \
  --name <your-app-name> \
  --resource-group tournament-rg
```

### 6. Scaling

Enable auto-scaling (Standard tier and above):
```bash
az monitor autoscale create \
  --resource-group tournament-rg \
  --resource <your-app-name> \
  --resource-type Microsoft.Web/serverfarms \
  --name autoscale-plan \
  --min-count 1 \
  --max-count 3 \
  --count 1
```

## Troubleshooting

### App doesn't start
1. Check deployment logs in Deployment Center
2. View application logs: `az webapp log tail`
3. Verify startup command is set correctly
4. Check that requirements.txt includes all dependencies

### Slow performance
1. Upgrade from Free (F1) to Basic (B1) or higher
2. Enable "Always On" setting
3. Consider using Azure CDN for static files

### Data loss issues
1. Implement Azure Files mount for persistent storage
2. Consider using a database instead of file storage

### Import errors
1. Ensure all dependencies are in requirements.txt
2. Check Python version compatibility (3.11)
3. Verify build logs show successful package installation

## Testing Locally Before Deployment

Test the startup script locally:
```bash
# Make startup script executable
chmod +x startup.sh

# Test it (will fail if gunicorn not installed)
./startup.sh

# Or test with Python development server
cd src
python app.py
```

Test with gunicorn locally:
```bash
pip install gunicorn
cd src
gunicorn --bind=0.0.0.0:8000 --workers=2 app:app
```

## Cost Estimation

- **Free (F1)**: $0/month - Limited, shared resources, no SLA
- **Basic (B1)**: ~$13/month - Dedicated resources, good for development/small production
- **Standard (S1)**: ~$70/month - Auto-scaling, staging slots, better performance
- **Premium (P1V2)**: ~$100/month - Enhanced performance, more memory

Additional costs:
- Azure Files storage: ~$0.06 per GB per month
- Bandwidth: Outbound data transfer charges may apply

## Next Steps

After successful deployment:
1. Test all application features
2. Set up continuous deployment from GitHub
3. Configure persistent storage for data files
4. Set up monitoring and alerts
5. Configure custom domain (if needed)
6. Enable HTTPS (automatic with azurewebsites.net domain)

## Support Resources

- [Azure App Service Documentation](https://docs.microsoft.com/azure/app-service/)
- [Python on Azure App Service](https://docs.microsoft.com/azure/app-service/quickstart-python)
- [Azure CLI Reference](https://docs.microsoft.com/cli/azure/)
