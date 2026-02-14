<#
.SYNOPSIS
    Configures Azure App Service for GitHub Actions continuous deployment.

.DESCRIPTION
    This script creates an Azure Resource Group, App Service Plan, and Web App,
    then configures GitHub Actions for automatic deployment on push to the repository.
    
    Unlike deploy.ps1, this script does NOT manually deploy code. Instead, it:
    - Sets up Azure infrastructure (same as deploy.ps1)
    - Configures the App Service for GitHub Actions deployment
    - Sets up all necessary app settings and runtime configuration
    
    After running this script, every push to the specified branch will trigger
    an automatic deployment via GitHub Actions.

.NOTES
    Prerequisites:
    - Azure CLI installed and logged in (run 'az login')
    - GitHub CLI installed and authenticated (run 'gh auth login')
    - .env file with AZURE_SUBSCRIPTION_ID set
    - Git repository with a remote named 'origin'
    
.PARAMETER Branch
    The branch to trigger deployments from. Defaults to 'main'.
    
.PARAMETER SkipLogin
    Skip Azure and GitHub login checks. Use when already authenticated.
#>

param(
    [string]$Branch = "main",
    [switch]$SkipLogin
)

$ErrorActionPreference = "Stop"

# Load environment variables from .env file
$envFile = Join-Path $PSScriptRoot ".env"
if (-not (Test-Path $envFile)) {
    Write-Error "Missing .env file. Copy .env.example to .env and fill in your values."
    exit 1
}

Get-Content $envFile | ForEach-Object {
    if ($_ -match '^\s*([^#][^=]+)=(.*)$') {
        $name = $matches[1].Trim()
        $value = $matches[2].Trim()
        Set-Item -Path "env:$name" -Value $value
    }
}

# Validate required variables
if (-not $env:AZURE_SUBSCRIPTION_ID) {
    Write-Error "AZURE_SUBSCRIPTION_ID is required in .env file"
    exit 1
}

# Set defaults for optional variables
$subscriptionId = $env:AZURE_SUBSCRIPTION_ID
$resourceGroup = if ($env:AZURE_RESOURCE_GROUP) { $env:AZURE_RESOURCE_GROUP } else { "tournament-allocator-rg" }
$location = if ($env:AZURE_LOCATION) { $env:AZURE_LOCATION } else { "eastus" }

# Generate globally unique app name by default using subscription ID prefix
if ($env:AZURE_APP_NAME) {
    $appName = $env:AZURE_APP_NAME
} else {
    $subPrefix = $subscriptionId.Substring(0, [Math]::Min(8, $subscriptionId.Length))
    $appName = "tournament-allocator-$subPrefix"
}

$appServicePlan = if ($env:AZURE_APP_SERVICE_PLAN) { $env:AZURE_APP_SERVICE_PLAN } else { "tournament-allocator-plan" }
$appServiceSku = if ($env:AZURE_APP_SERVICE_SKU) { $env:AZURE_APP_SERVICE_SKU } else { "B1" }

Write-Host "=== GitHub Actions Deployment Configuration ===" -ForegroundColor Cyan
Write-Host "Subscription: $subscriptionId"
Write-Host "Resource Group: $resourceGroup"
Write-Host "Location: $location"
Write-Host "App Name: $appName"
Write-Host "App Service Plan: $appServicePlan"
Write-Host "App Service SKU: $appServiceSku"
Write-Host "Branch: $Branch"
Write-Host ""

# Check for required tools
if (-not $SkipLogin) {
    Write-Host "Checking Azure CLI..." -ForegroundColor Yellow
    $azVersion = az version 2>$null
    if (-not $azVersion) {
        Write-Error "Azure CLI not found. Install from: https://aka.ms/installazurecli"
        exit 1
    }
    
    Write-Host "Checking GitHub CLI..." -ForegroundColor Yellow
    $ghVersion = gh version 2>$null
    if (-not $ghVersion) {
        Write-Error "GitHub CLI not found. Install from: https://cli.github.com/"
        exit 1
    }
}

# Login checks
if (-not $SkipLogin) {
    Write-Host "Checking Azure CLI login status..." -ForegroundColor Yellow
    $account = az account show 2>$null | ConvertFrom-Json
    if (-not $account) {
        Write-Host "Not logged in to Azure. Running 'az login'..." -ForegroundColor Yellow
        az login
    }
    
    Write-Host "Checking GitHub CLI authentication..." -ForegroundColor Yellow
    $ghAuth = gh auth status 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Not logged in to GitHub. Running 'gh auth login'..." -ForegroundColor Yellow
        gh auth login
    }
}

# Get repository information
Write-Host "Detecting repository information..." -ForegroundColor Yellow
$repoUrl = git config --get remote.origin.url 2>$null
if (-not $repoUrl) {
    Write-Error "No git remote 'origin' found. Ensure you're in a git repository with a remote."
    exit 1
}

# Parse owner/repo from URL
if ($repoUrl -match "github\.com[:/]([^/]+)/([^/\.]+)") {
    $repoOwner = $matches[1]
    $repoName = $matches[2]
} else {
    Write-Error "Could not parse GitHub repository from remote URL: $repoUrl"
    exit 1
}

Write-Host "Repository: $repoOwner/$repoName" -ForegroundColor Cyan
Write-Host ""

# Set subscription
Write-Host "Setting Azure subscription..." -ForegroundColor Yellow
az account set --subscription $subscriptionId

function Ensure-ProviderRegistered {
    param(
        [Parameter(Mandatory = $true)]
        [string]$Namespace
    )

    $state = az provider show --namespace $Namespace --query "registrationState" -o tsv 2>$null
    if ($state -ne "Registered") {
        Write-Host "Registering $Namespace resource provider..." -ForegroundColor Yellow
        az provider register --namespace $Namespace --wait
    } else {
        Write-Host "$Namespace resource provider already registered." -ForegroundColor DarkGray
    }
}

# Register required resource providers
Ensure-ProviderRegistered -Namespace "Microsoft.Web"
Ensure-ProviderRegistered -Namespace "Microsoft.Quota"
Ensure-ProviderRegistered -Namespace "Microsoft.Compute"

# Create resource group (idempotent)
Write-Host "Ensuring resource group '$resourceGroup' exists..." -ForegroundColor Yellow
$rgExists = az group exists --name $resourceGroup | ConvertFrom-Json
if (-not $rgExists) {
    az group create --name $resourceGroup --location $location --output none
} else {
    Write-Host "Resource group already exists." -ForegroundColor DarkGray
}

# Create App Service Plan (idempotent)
Write-Host "Ensuring App Service Plan '$appServicePlan' exists..." -ForegroundColor Yellow
az appservice plan show --name $appServicePlan --resource-group $resourceGroup --output none 2>$null
$planExists = ($LASTEXITCODE -eq 0)

if (-not $planExists) {
    Write-Host "Creating App Service Plan..." -ForegroundColor Yellow
    az appservice plan create `
        --name $appServicePlan `
        --resource-group $resourceGroup `
        --sku $appServiceSku `
        --is-linux `
        --output none
} else {
    Write-Host "App Service Plan already exists." -ForegroundColor DarkGray
}

# Create Web App (idempotent)
Write-Host "Ensuring Web App '$appName' exists..." -ForegroundColor Yellow
az webapp show --name $appName --resource-group $resourceGroup --output none 2>$null
$appExists = ($LASTEXITCODE -eq 0)

if (-not $appExists) {
    Write-Host "Creating Web App..." -ForegroundColor Yellow
    az webapp create `
        --name $appName `
        --resource-group $resourceGroup `
        --plan $appServicePlan `
        --runtime "PYTHON:3.11" `
        --output none
} else {
    Write-Host "Web App already exists." -ForegroundColor DarkGray
}

# Configure runtime settings for Flask
Write-Host "Configuring startup command..." -ForegroundColor Yellow
az webapp config set `
    --name $appName `
    --resource-group $resourceGroup `
    --startup-file "startup.sh" `
    --output none

# Set runtime app settings
Write-Host "Setting runtime app settings..." -ForegroundColor Yellow
az webapp config appsettings set `
    --name $appName `
    --resource-group $resourceGroup `
    --settings SCM_DO_BUILD_DURING_DEPLOYMENT=true DISABLE_COLLECTSTATIC=true TOURNAMENT_DATA_DIR=/home/data `
    --output none

# Set SECRET_KEY for Flask session security (only on first deploy)
$existingKey = az webapp config appsettings list --name $appName --resource-group $resourceGroup --query "[?name=='SECRET_KEY'].value" -o tsv
if (-not $existingKey) {
    Write-Host "Setting SECRET_KEY (first deploy)..." -ForegroundColor Yellow
    az webapp config appsettings set --name $appName --resource-group $resourceGroup --settings SECRET_KEY="$(New-Guid)" --output none
} else {
    Write-Host "SECRET_KEY already set, skipping (preserves user sessions)." -ForegroundColor DarkGray
}

# Set ADMIN_PASSWORD for admin user creation (only on first deploy)
$existingAdminPassword = az webapp config appsettings list --name $appName --resource-group $resourceGroup --query "[?name=='ADMIN_PASSWORD'].value" -o tsv
if (-not $existingAdminPassword) {
    $adminPassword = if ($env:ADMIN_PASSWORD) { $env:ADMIN_PASSWORD } else { "admin" }
    Write-Host "Setting ADMIN_PASSWORD (first deploy)..." -ForegroundColor Yellow
    az webapp config appsettings set --name $appName --resource-group $resourceGroup --settings ADMIN_PASSWORD="$adminPassword" --output none
    Write-Host "  Admin user will be created with username 'admin' and configured password." -ForegroundColor DarkGray
} else {
    Write-Host "ADMIN_PASSWORD already set, skipping." -ForegroundColor DarkGray
}

# Configure GitHub Actions deployment
Write-Host "Configuring GitHub Actions deployment..." -ForegroundColor Yellow

# Get deployment credentials from Azure
$deploymentJson = az webapp deployment list-publishing-credentials --name $appName --resource-group $resourceGroup --query "{username:publishingUserName,password:publishingPassword}" -o json
$deployment = $deploymentJson | ConvertFrom-Json

# Set GitHub secret for Azure publish profile
Write-Host "Setting GitHub repository secret AZURE_WEBAPP_PUBLISH_PROFILE..." -ForegroundColor Yellow
$publishProfile = az webapp deployment list-publishing-profiles --name $appName --resource-group $resourceGroup --xml
gh secret set AZURE_WEBAPP_PUBLISH_PROFILE --repo "$repoOwner/$repoName" --body "$publishProfile"

# Create GitHub Actions workflow file if it doesn't exist
$workflowDir = Join-Path $PSScriptRoot ".github\workflows"
$workflowFile = Join-Path $workflowDir "azure-deployment.yml"

if (-not (Test-Path $workflowDir)) {
    New-Item -ItemType Directory -Path $workflowDir -Force | Out-Null
}

if (-not (Test-Path $workflowFile)) {
    Write-Host "Creating GitHub Actions workflow file..." -ForegroundColor Yellow
    
    $workflowContent = @"
name: Deploy to Azure App Service

on:
  push:
    branches:
      - $Branch
  workflow_dispatch:

jobs:
  build-and-deploy:
    runs-on: ubuntu-latest
    
    steps:
      - name: Checkout code
        uses: actions/checkout@v4
      
      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      
      - name: Create deployment package
        run: |
          mkdir deploy-package
          cp -r src deploy-package/
          cp startup.sh deploy-package/
          cp requirements.txt deploy-package/
          
          # Add gunicorn to requirements if not present
          if ! grep -q "gunicorn" deploy-package/requirements.txt; then
            echo "gunicorn" >> deploy-package/requirements.txt
          fi
          
          cd deploy-package
          zip -r ../deploy.zip .
      
      - name: Deploy to Azure Web App
        uses: azure/webapps-deploy@v2
        with:
          app-name: '$appName'
          publish-profile: `${{ secrets.AZURE_WEBAPP_PUBLISH_PROFILE }}
          package: deploy.zip
"@

    $workflowContent | Set-Content $workflowFile -Encoding UTF8
    
    Write-Host "Workflow file created at: $workflowFile" -ForegroundColor Cyan
    Write-Host "Committing workflow file to repository..." -ForegroundColor Yellow
    
    git add $workflowFile
    git commit -m "Add GitHub Actions deployment workflow

Co-authored-by: Copilot <223556219+Copilot@users.noreply.github.com>"
    
    Write-Host "Pushing workflow to GitHub..." -ForegroundColor Yellow
    git push origin HEAD
    
} else {
    Write-Host "Workflow file already exists at: $workflowFile" -ForegroundColor DarkGray
    Write-Host "Skipping workflow creation. To update, delete the file and run this script again." -ForegroundColor DarkGray
}

Write-Host ""
Write-Host "=== Configuration Complete ===" -ForegroundColor Green
Write-Host ""
Write-Host "GitHub Actions deployment is now configured!" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Push to branch '$Branch' to trigger the first deployment"
Write-Host "  2. Monitor deployment: https://github.com/$repoOwner/$repoName/actions"
Write-Host "  3. Once deployed, visit: https://$appName.azurewebsites.net"
Write-Host ""
Write-Host "Admin Login:" -ForegroundColor Yellow
Write-Host "  Username: admin" -ForegroundColor Cyan
if ($env:ADMIN_PASSWORD) {
    Write-Host "  Password: (from ADMIN_PASSWORD in .env)" -ForegroundColor Cyan
} else {
    Write-Host "  Password: admin (default)" -ForegroundColor Cyan
}
Write-Host "  Note: Change the password after first login for security." -ForegroundColor DarkGray
Write-Host ""
Write-Host "Useful commands:" -ForegroundColor Yellow
Write-Host "  View app logs: az webapp log tail --name $appName --resource-group $resourceGroup"
Write-Host "  View deployments: gh run list --repo $repoOwner/$repoName --workflow azure-deployment.yml"
Write-Host "  Delete resources: az group delete --name $resourceGroup --yes"
