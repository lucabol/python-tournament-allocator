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

# Register required resource providers (skip if already registered)
Ensure-ProviderRegistered -Namespace "Microsoft.Web"
Ensure-ProviderRegistered -Namespace "Microsoft.Quota"
Ensure-ProviderRegistered -Namespace "Microsoft.Compute"

# Create resource group (if missing)
Write-Host "Ensuring resource group '$resourceGroup' exists..." -ForegroundColor Yellow
$rgExists = az group exists --name $resourceGroup | ConvertFrom-Json
if (-not $rgExists) {
    az group create --name $resourceGroup --location $location --output none
} else {
    Write-Host "Resource group already exists." -ForegroundColor DarkGray
}

# Create App Service Plan (Linux, Python) if missing
Write-Host "Ensuring App Service Plan '$appServicePlan' exists..." -ForegroundColor Yellow
$planExists = $false
try {
    az appservice plan show --name $appServicePlan --resource-group $resourceGroup --output none
    $planExists = $true
} catch {
    $planExists = $false
}

if (-not $planExists) {
    az appservice plan create `
        --name $appServicePlan `
        --resource-group $resourceGroup `
        --sku $appServiceSku `
        --is-linux `
        --output none
} else {
    Write-Host "App Service Plan already exists." -ForegroundColor DarkGray
}

# Create Web App if missing
Write-Host "Ensuring Web App '$appName' exists..." -ForegroundColor Yellow
$appExists = $false
try {
    az webapp show --name $appName --resource-group $resourceGroup --output none
    $appExists = $true
} catch {
    $appExists = $false
}

if (-not $appExists) {
    az webapp create `
        --name $appName `
        --resource-group $resourceGroup `
        --plan $appServicePlan `
        --runtime "PYTHON:3.11" `
        --output none
} else {
    Write-Host "Web App already exists." -ForegroundColor DarkGray
}

# Configure startup command for Flask
Write-Host "Configuring startup command..." -ForegroundColor Yellow
az webapp config set `
    --name $appName `
    --resource-group $resourceGroup `
    --startup-file "startup.sh" `
    --output none

# Enable Oryx build (to install requirements.txt)
Write-Host "Enabling Oryx build..." -ForegroundColor Yellow
az webapp config appsettings set `
    --name $appName `
    --resource-group $resourceGroup `
    --settings SCM_DO_BUILD_DURING_DEPLOYMENT=true DISABLE_COLLECTSTATIC=true `
    --output none

# Create deployment package
Write-Host "Creating deployment package..." -ForegroundColor Yellow
$zipFile = Join-Path $env:TEMP "deploy.zip"
if (Test-Path $zipFile) { Remove-Item $zipFile }

$stagingDir = Join-Path $env:TEMP ("deploy-staging-" + [Guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $stagingDir | Out-Null

Copy-Item -Path (Join-Path $PSScriptRoot "src") -Destination $stagingDir -Recurse
Copy-Item -Path (Join-Path $PSScriptRoot "data") -Destination $stagingDir -Recurse
Copy-Item -Path (Join-Path $PSScriptRoot "startup.sh") -Destination $stagingDir

$requirementsPath = Join-Path $PSScriptRoot "requirements.txt"
$requirements = Get-Content $requirementsPath
if ($requirements -notcontains "gunicorn") {
    $requirements = $requirements + "gunicorn"
}

$stagedRequirements = Join-Path $stagingDir "requirements.txt"
$requirements | Set-Content $stagedRequirements

Compress-Archive -Path (Join-Path $stagingDir "*") -DestinationPath $zipFile

# Restart webapp so config changes take effect before deploying
Write-Host "Restarting webapp to apply config changes..." -ForegroundColor Yellow
az webapp restart --name $appName --resource-group $resourceGroup --output none
Start-Sleep -Seconds 10

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
Write-Host "Uploading zip to Kudu and running remote build (this can take several minutes for numpy/pandas/ortools)..." -ForegroundColor DarkGray
$deployStart = Get-Date
az webapp deploy `
    --name $appName `
    --resource-group $resourceGroup `
    --src-path $zipFile `
    --type zip `
    --clean true `
    --track-status false `
    --timeout 600000 `
    --output none
$deployDuration = [math]::Round(((Get-Date) - $deployStart).TotalSeconds)
Write-Host "Deployment command finished in $deployDuration seconds." -ForegroundColor DarkGray

# Cleanup
Remove-Item $zipFile -ErrorAction SilentlyContinue
Remove-Item $stagingDir -Recurse -Force -ErrorAction SilentlyContinue

# Get the URL
$url = "https://$appName.azurewebsites.net"

$latestDeploymentId = $null
try {
    $latestDeploymentId = az webapp log deployment list --name $appName --resource-group $resourceGroup --query "[0].id" -o tsv 2>$null
} catch {
    $latestDeploymentId = $null
}

Write-Host ""
Write-Host "=== Deployment Complete ===" -ForegroundColor Green
Write-Host "App URL: $url" -ForegroundColor Cyan
Write-Host ""
Write-Host "To view logs: az webapp log tail --name $appName --resource-group $resourceGroup"
if ($latestDeploymentId) {
    Write-Host "To view build logs: az webapp log deployment show --name $appName --resource-group $resourceGroup --deployment-id $latestDeploymentId"
} else {
    Write-Host "To view build logs: az webapp log deployment show --name $appName --resource-group $resourceGroup --deployment-id <id>"
    Write-Host "To list deployment IDs: az webapp log deployment list --name $appName --resource-group $resourceGroup --query \"[0].id\" -o tsv"
}
Write-Host "To delete: az group delete --name $resourceGroup --yes"
