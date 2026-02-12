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

# Create deployment package
Write-Host "Creating deployment package..." -ForegroundColor Yellow
$zipFile = Join-Path $env:TEMP "deploy.zip"
if (Test-Path $zipFile) { Remove-Item $zipFile }

$stagingDir = Join-Path $env:TEMP ("deploy-staging-" + [Guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $stagingDir | Out-Null

Copy-Item -Path (Join-Path $PSScriptRoot "src") -Destination $stagingDir -Recurse
Copy-Item -Path (Join-Path $PSScriptRoot "startup.sh") -Destination $stagingDir

$requirementsPath = Join-Path $PSScriptRoot "requirements.txt"
$requirements = Get-Content $requirementsPath
if ($requirements -notcontains "gunicorn") {
    $requirements = $requirements + "gunicorn"
}

$stagedRequirements = Join-Path $stagingDir "requirements.txt"
$requirements | Set-Content $stagedRequirements

Compress-Archive -Path (Join-Path $stagingDir "*") -DestinationPath $zipFile

# Deploy with retry logic — Kudu may be slow to respond on first deploy
# NOTE: az webapp deploy returns exit code 0 even on 502, so we capture output to detect failures.
Write-Host "Deploying application..." -ForegroundColor Yellow
Write-Host "Uploading zip to Kudu and running remote build (this can take several minutes for numpy/pandas/ortools)..." -ForegroundColor DarkGray
$deployMaxRetries = 3
$deployAttempt = 0
$deploySuccess = $false
while (-not $deploySuccess -and $deployAttempt -lt $deployMaxRetries) {
    $deployAttempt++
    $deployStart = Get-Date
    try {
        $deployOutput = az webapp deploy `
            --name $appName `
            --resource-group $resourceGroup `
            --src-path $zipFile `
            --type zip `
            --clean true `
            --track-status false `
            --timeout 600000 2>&1
        $deployDuration = [math]::Round(((Get-Date) - $deployStart).TotalSeconds)
        $outputText = $deployOutput | Out-String

        # az webapp deploy returns exit code 0 even on 502 — check output text
        if ($outputText -match "Status Code: 50[0-9]" -or $outputText -match "Bad Gateway") {
            throw "Kudu returned an error: $outputText"
        }

        $deploySuccess = $true
        Write-Host "Deployment succeeded in $deployDuration seconds (attempt $deployAttempt/$deployMaxRetries)." -ForegroundColor DarkGray
    } catch {
        $deployDuration = [math]::Round(((Get-Date) - $deployStart).TotalSeconds)
        if ($deployAttempt -lt $deployMaxRetries) {
            $backoff = 30 * $deployAttempt
            Write-Host "  Deployment attempt $deployAttempt failed after ${deployDuration}s. Retrying in ${backoff}s..." -ForegroundColor Yellow
            Start-Sleep -Seconds $backoff
        } else {
            Write-Error "Deployment failed after $deployMaxRetries attempts. Last error: $_"
        }
    }
}

# Configure app AFTER deploy succeeds — each config change triggers a container restart,
# and on first deploy the Oryx remote build needs to complete before the container can boot.
# Setting config before deploy caused a race: container restarts before build artifacts exist.

# Configure startup command for Flask
Write-Host "Configuring startup command..." -ForegroundColor Yellow
az webapp config set `
    --name $appName `
    --resource-group $resourceGroup `
    --startup-file "startup.sh" `
    --output none

# Enable Oryx build and set app settings
Write-Host "Setting app settings..." -ForegroundColor Yellow
az webapp config appsettings set `
    --name $appName `
    --resource-group $resourceGroup `
    --settings SCM_DO_BUILD_DURING_DEPLOYMENT=true DISABLE_COLLECTSTATIC=true TOURNAMENT_DATA_DIR=/home/data `
    --output none

# Set SECRET_KEY for Flask session security — only on first deploy.
# Regenerating it invalidates all user session cookies (logs everyone out).
$existingKey = az webapp config appsettings list --name $appName --resource-group $resourceGroup --query "[?name=='SECRET_KEY'].value" -o tsv
if (-not $existingKey) {
    Write-Host "Setting SECRET_KEY (first deploy)..." -ForegroundColor Yellow
    az webapp config appsettings set --name $appName --resource-group $resourceGroup --settings SECRET_KEY="$(New-Guid)" --output none
} else {
    Write-Host "SECRET_KEY already set, skipping (preserves user sessions)." -ForegroundColor DarkGray
}

# Wait for config changes to propagate (config changes trigger async container restarts)
Write-Host "Waiting for config changes to propagate..." -ForegroundColor Yellow
Start-Sleep -Seconds 15

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
