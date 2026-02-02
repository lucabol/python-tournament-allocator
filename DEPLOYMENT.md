# Deploying to Azure Container Apps

This guide walks you through deploying the Python Tournament Allocator application to Azure Container Apps, a fully managed serverless container service.

## Prerequisites

Before you begin, ensure you have:

1. **Azure Account**: An active Azure subscription ([create one for free](https://azure.microsoft.com/free/))
2. **Azure CLI**: Install the [Azure CLI](https://docs.microsoft.com/cli/azure/install-azure-cli)
3. **Docker**: Install [Docker Desktop](https://www.docker.com/products/docker-desktop) (optional, for local testing)
4. **Git**: The repository cloned locally

## Deployment Methods

You can deploy using one of these methods:

### Method 1: Direct Deployment from Local Source (Recommended)

This method builds the container image in Azure and deploys it directly.

#### Step 1: Login to Azure

```bash
az login
```

#### Step 2: Set Your Subscription (if you have multiple)

```bash
# List available subscriptions
az account list --output table

# Set the subscription you want to use
az account set --subscription "Your-Subscription-Name-or-ID"
```

#### Step 3: Create a Resource Group

```bash
# Set variables
RESOURCE_GROUP="tournament-allocator-rg"
LOCATION="eastus"  # Choose a location near you

# Create resource group
az group create --name $RESOURCE_GROUP --location $LOCATION
```

#### Step 4: Create an Azure Container Apps Environment

```bash
ENVIRONMENT="tournament-allocator-env"

az containerapp env create \
  --name $ENVIRONMENT \
  --resource-group $RESOURCE_GROUP \
  --location $LOCATION
```

#### Step 5: Deploy the Application

```bash
APP_NAME="tournament-allocator"

az containerapp up \
  --name $APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --environment $ENVIRONMENT \
  --source . \
  --target-port 8080 \
  --ingress external \
  --query properties.configuration.ingress.fqdn
```

This command will:
- Build your Docker image in the cloud
- Create an Azure Container Registry (if needed)
- Push the image to the registry
- Create and deploy the container app
- Return the public URL where your app is accessible

The deployment typically takes 3-5 minutes. Once complete, you'll see the URL where your application is running.

### Method 2: Using Azure Container Registry

This method gives you more control over the container image.

#### Step 1-3: Same as Method 1

Follow steps 1-3 from Method 1.

#### Step 4: Create an Azure Container Registry

```bash
# Must be globally unique across Azure (lowercase alphanumeric only, 5-50 characters)
ACR_NAME="tournamentallocator$(date +%s)"

az acr create \
  --resource-group $RESOURCE_GROUP \
  --name $ACR_NAME \
  --sku Basic \
  --admin-enabled true
```

**Note**: The ACR name must be globally unique and can only contain lowercase alphanumeric characters. If using the GitHub Actions workflow, you'll need to update the `ACR_NAME` environment variable in `.github/workflows/azure-container-apps.yml.example` with your actual ACR name.

#### Step 5: Build and Push Image to ACR

```bash
# Build and push the image using ACR build
az acr build \
  --registry $ACR_NAME \
  --image tournament-allocator:latest \
  --file Dockerfile \
  .
```

#### Step 6: Create Container Apps Environment

```bash
ENVIRONMENT="tournament-allocator-env"

az containerapp env create \
  --name $ENVIRONMENT \
  --resource-group $RESOURCE_GROUP \
  --location $LOCATION
```

#### Step 7: Deploy to Container Apps

```bash
APP_NAME="tournament-allocator"
ACR_LOGIN_SERVER=$(az acr show --name $ACR_NAME --query loginServer --output tsv)
ACR_USERNAME=$(az acr credential show --name $ACR_NAME --query username --output tsv)
ACR_PASSWORD=$(az acr credential show --name $ACR_NAME --query passwords[0].value --output tsv)

az containerapp create \
  --name $APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --environment $ENVIRONMENT \
  --image $ACR_LOGIN_SERVER/tournament-allocator:latest \
  --target-port 8080 \
  --ingress external \
  --registry-server $ACR_LOGIN_SERVER \
  --registry-username $ACR_USERNAME \
  --registry-password $ACR_PASSWORD \
  --cpu 0.5 \
  --memory 1.0Gi \
  --min-replicas 1 \
  --max-replicas 3 \
  --query properties.configuration.ingress.fqdn
```

### Method 3: Using GitHub Actions (CI/CD)

For automated deployments on every commit, see the GitHub Actions deployment section below.

## Configuration

### Environment Variables

You can set environment variables for your application:

```bash
az containerapp update \
  --name $APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --set-env-vars \
    FLASK_SECRET_KEY=your-secret-key-here \
    FLASK_ENV=production
```

### Scaling Configuration

Azure Container Apps automatically scales based on HTTP traffic. You can adjust scaling rules:

```bash
az containerapp update \
  --name $APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --min-replicas 0 \
  --max-replicas 5
```

Setting `--min-replicas 0` enables scale-to-zero, which can reduce costs when the app is not in use.

### Custom Domains and SSL

To add a custom domain with automatic SSL:

```bash
az containerapp hostname add \
  --name $APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --hostname your-domain.com
```

## Local Testing

Before deploying, you can test the Docker container locally:

```bash
# Build the image
docker build -t tournament-allocator:local .

# Run the container
docker run -p 8080:8080 tournament-allocator:local

# Access the application at http://localhost:8080
```

## Monitoring and Logs

### View Application Logs

```bash
# Stream logs in real-time
az containerapp logs show \
  --name $APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --follow

# View recent logs
az containerapp logs show \
  --name $APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --tail 100
```

### View Metrics

```bash
# View replica count and CPU/memory usage
az containerapp show \
  --name $APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --query properties.template
```

You can also view metrics in the Azure Portal:
1. Navigate to your Container App
2. Click "Metrics" in the left menu
3. Add metrics like HTTP requests, CPU usage, memory usage, etc.

## Updating Your Application

### Update with New Code

After making changes to your code:

```bash
# If using Method 1 (direct deployment)
az containerapp up \
  --name $APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --source .

# If using Method 2 (ACR)
az acr build --registry $ACR_NAME --image tournament-allocator:latest --file Dockerfile .
az containerapp update \
  --name $APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --image $ACR_LOGIN_SERVER/tournament-allocator:latest
```

### Revisions and Traffic Splitting

Container Apps support multiple revisions with traffic splitting:

```bash
# Create a new revision with a label
az containerapp update \
  --name $APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --revision-suffix v2

# Split traffic between revisions (e.g., 80% to latest, 20% to v2)
az containerapp ingress traffic set \
  --name $APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --revision-weight latest=80 v2=20
```

## GitHub Actions Deployment

For automated CI/CD, create `.github/workflows/deploy.yml`:

```yaml
name: Deploy to Azure Container Apps

on:
  push:
    branches: [ main ]
  workflow_dispatch:

env:
  RESOURCE_GROUP: tournament-allocator-rg
  CONTAINER_APP_NAME: tournament-allocator
  ACR_NAME: tournamentallocatoracr

jobs:
  build-and-deploy:
    runs-on: ubuntu-latest
    
    steps:
    - uses: actions/checkout@v3
    
    - name: Login to Azure
      uses: azure/login@v1
      with:
        creds: ${{ secrets.AZURE_CREDENTIALS }}
    
    - name: Build and push to ACR
      run: |
        az acr build \
          --registry ${{ env.ACR_NAME }} \
          --image tournament-allocator:${{ github.sha }} \
          --image tournament-allocator:latest \
          --file Dockerfile \
          .
    
    - name: Deploy to Container Apps
      run: |
        az containerapp update \
          --name ${{ env.CONTAINER_APP_NAME }} \
          --resource-group ${{ env.RESOURCE_GROUP }} \
          --image ${{ env.ACR_NAME }}.azurecr.io/tournament-allocator:${{ github.sha }}
```

To set up GitHub Actions:

1. Create a service principal:
```bash
az ad sp create-for-rbac --name "github-actions-tournament-allocator" \
  --role contributor \
  --scopes /subscriptions/{subscription-id}/resourceGroups/$RESOURCE_GROUP \
  --sdk-auth
```

2. Copy the JSON output and add it as a secret named `AZURE_CREDENTIALS` in your GitHub repository settings.

## Data Persistence

By default, any data stored in the container (like uploaded files) will be lost when the container restarts. For persistent storage:

### Option 1: Azure Files

Mount an Azure Files share to persist data:

```bash
# Create a storage account
STORAGE_ACCOUNT="tournamentdata$(date +%s)"
az storage account create \
  --name $STORAGE_ACCOUNT \
  --resource-group $RESOURCE_GROUP \
  --location $LOCATION \
  --sku Standard_LRS

# Create a file share
az storage share create \
  --name tournament-data \
  --account-name $STORAGE_ACCOUNT

# Get storage key
STORAGE_KEY=$(az storage account keys list \
  --account-name $STORAGE_ACCOUNT \
  --query [0].value -o tsv)

# Create a storage mount in Container App
az containerapp env storage set \
  --name $ENVIRONMENT \
  --resource-group $RESOURCE_GROUP \
  --storage-name tournament-storage \
  --azure-file-account-name $STORAGE_ACCOUNT \
  --azure-file-account-key $STORAGE_KEY \
  --azure-file-share-name tournament-data \
  --access-mode ReadWrite

# Update app to use the storage
az containerapp update \
  --name $APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --storage-mount tournament-storage=/app/data
```

### Option 2: Azure Database

For structured data, consider using Azure Database for PostgreSQL or MySQL.

## Cost Optimization

To minimize costs:

1. **Enable scale-to-zero** for development environments:
```bash
az containerapp update \
  --name $APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --min-replicas 0
```

2. **Use consumption-based billing**: Container Apps charge only for the resources you use.

3. **Delete unused resources**:
```bash
az group delete --name $RESOURCE_GROUP --yes --no-wait
```

## Troubleshooting

### Common Issues

**Issue**: Container fails to start
- **Solution**: Check logs with `az containerapp logs show` and ensure all dependencies are in `requirements.txt`

**Issue**: Application not accessible
- **Solution**: Verify ingress is set to `external` and the target port is `8080`

**Issue**: Out of memory errors
- **Solution**: Increase memory allocation:
```bash
az containerapp update \
  --name $APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --memory 2.0Gi
```

**Issue**: Build failures
- **Solution**: Test the Docker build locally first with `docker build -t test .`

### Get Application URL

```bash
az containerapp show \
  --name $APP_NAME \
  --resource-group $RESOURCE_GROUP \
  --query properties.configuration.ingress.fqdn \
  --output tsv
```

## Additional Resources

- [Azure Container Apps Documentation](https://docs.microsoft.com/azure/container-apps/)
- [Azure CLI Reference](https://docs.microsoft.com/cli/azure/containerapp)
- [Pricing Calculator](https://azure.microsoft.com/pricing/calculator/)
- [Best Practices](https://docs.microsoft.com/azure/container-apps/overview#best-practices)

## Security Best Practices

1. **Use managed identities** instead of storing credentials in environment variables
2. **Enable HTTPS only** for production deployments
3. **Use Azure Key Vault** for sensitive configuration
4. **Implement authentication** using Azure AD or other identity providers
5. **Regular updates**: Keep the base image and dependencies up to date

## Support

For issues specific to this application, please open an issue in the GitHub repository.
For Azure Container Apps issues, refer to [Azure Support](https://azure.microsoft.com/support/).
