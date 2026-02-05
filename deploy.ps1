<#
.SYNOPSIS
    Deploys the Tournament Allocator app to Azure App Service.

.DESCRIPTION
    This script creates an Azure Resource Group, App Service Plan, and Web App,
    then deploys the Python Flask application using zip deployment.

.NOTES
    Prerequisites:
    - Azure CLI installed and logged in (run 'az login')
    - .env file with AZURE_SUBSCRIPTION_ID set
#>

param(
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
$appName = if ($env:AZURE_APP_NAME) { $env:AZURE_APP_NAME } else { "tournament-allocator" }
$appServicePlan = if ($env:AZURE_APP_SERVICE_PLAN) { $env:AZURE_APP_SERVICE_PLAN } else { "tournament-allocator-plan" }
$appServiceSku = if ($env:AZURE_APP_SERVICE_SKU) { $env:AZURE_APP_SERVICE_SKU } else { "B1" }

Write-Host "=== Azure Deployment Configuration ===" -ForegroundColor Cyan
Write-Host "Subscription: $subscriptionId"
Write-Host "Resource Group: $resourceGroup"
Write-Host "Location: $location"
Write-Host "App Name: $appName"
Write-Host "App Service Plan: $appServicePlan"
Write-Host "App Service SKU: $appServiceSku"
Write-Host ""

# Login check
if (-not $SkipLogin) {
    Write-Host "Checking Azure CLI login status..." -ForegroundColor Yellow
    $account = az account show 2>$null | ConvertFrom-Json
    if (-not $account) {
        Write-Host "Not logged in. Running 'az login'..." -ForegroundColor Yellow
        az login
    }
}

# Set subscription
Write-Host "Setting subscription..." -ForegroundColor Yellow
az account set --subscription $subscriptionId

# Register required resource providers
Write-Host "Registering Microsoft.Web resource provider..." -ForegroundColor Yellow
az provider register --namespace Microsoft.Web --wait
Write-Host "Registering Microsoft.Quota resource provider..." -ForegroundColor Yellow
az provider register --namespace Microsoft.Quota --wait
Write-Host "Registering Microsoft.Compute resource provider..." -ForegroundColor Yellow
az provider register --namespace Microsoft.Compute --wait

# Create resource group
Write-Host "Creating resource group '$resourceGroup'..." -ForegroundColor Yellow
az group create --name $resourceGroup --location $location --output none

# Create App Service Plan (Linux, Python)
Write-Host "Creating App Service Plan '$appServicePlan'..." -ForegroundColor Yellow
az appservice plan create `
    --name $appServicePlan `
    --resource-group $resourceGroup `
    --sku $appServiceSku `
    --is-linux `
    --output none

# Create Web App
Write-Host "Creating Web App '$appName'..." -ForegroundColor Yellow
az webapp create `
    --name $appName `
    --resource-group $resourceGroup `
    --plan $appServicePlan `
    --runtime "PYTHON:3.11" `
    --output none

# Configure startup command for Flask
Write-Host "Configuring startup command..." -ForegroundColor Yellow
az webapp config set `
    --name $appName `
    --resource-group $resourceGroup `
    --startup-file "gunicorn --bind=0.0.0.0:8000 --chdir /home/site/wwwroot/src --timeout 600 app:app" `
    --output none

# Enable Oryx build (to install requirements.txt)
Write-Host "Enabling Oryx build..." -ForegroundColor Yellow
az webapp config appsettings set `
    --name $appName `
    --resource-group $resourceGroup `
    --settings SCM_DO_BUILD_DURING_DEPLOYMENT=true `
    --output none

# Create deployment package
Write-Host "Creating deployment package..." -ForegroundColor Yellow
$zipFile = Join-Path $env:TEMP "deploy.zip"
if (Test-Path $zipFile) { Remove-Item $zipFile }

# Add gunicorn to requirements if not present
$requirementsPath = Join-Path $PSScriptRoot "requirements.txt"
$requirements = Get-Content $requirementsPath
if ($requirements -notcontains "gunicorn") {
    $tempRequirements = Join-Path $env:TEMP "requirements.txt"
    ($requirements + "gunicorn") | Set-Content $tempRequirements
} else {
    $tempRequirements = $requirementsPath
}

# Create zip with src, data, and requirements
Compress-Archive -Path (Join-Path $PSScriptRoot "src"), (Join-Path $PSScriptRoot "data") -DestinationPath $zipFile
# Add requirements.txt to the zip
Compress-Archive -Path $tempRequirements -Update -DestinationPath $zipFile

# Ensure the webapp is started before deployment
Write-Host "Starting webapp..." -ForegroundColor Yellow
az webapp start --name $appName --resource-group $resourceGroup --output none

# Wait for webapp to be ready
Write-Host "Waiting for webapp to be ready..." -ForegroundColor Yellow
$maxRetries = 10
$retryCount = 0
do {
    Start-Sleep -Seconds 5
    $state = az webapp show --name $appName --resource-group $resourceGroup --query "state" -o tsv
    $retryCount++
    Write-Host "  Webapp state: $state (attempt $retryCount/$maxRetries)"
} while ($state -ne "Running" -and $retryCount -lt $maxRetries)

if ($state -ne "Running") {
    Write-Warning "Webapp may not be fully started. Proceeding with deployment anyway..."
}

# Deploy
Write-Host "Deploying application..." -ForegroundColor Yellow
az webapp deploy `
    --name $appName `
    --resource-group $resourceGroup `
    --src-path $zipFile `
    --type zip `
    --output none

# Cleanup
Remove-Item $zipFile -ErrorAction SilentlyContinue
if ($tempRequirements -ne $requirementsPath) {
    Remove-Item $tempRequirements -ErrorAction SilentlyContinue
}

# Get the URL
$url = "https://$appName.azurewebsites.net"

Write-Host ""
Write-Host "=== Deployment Complete ===" -ForegroundColor Green
Write-Host "App URL: $url" -ForegroundColor Cyan
Write-Host ""
Write-Host "To view logs: az webapp log tail --name $appName --resource-group $resourceGroup"
Write-Host "To delete: az group delete --name $resourceGroup --yes"
