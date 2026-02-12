<#
.SYNOPSIS
    Deploys with pre-installed dependencies (no remote Oryx build).

.DESCRIPTION
    The main failure mode of deploy.ps1 is Kudu timing out (502) while
    building numpy/pandas/ortools during SCM_DO_BUILD_DURING_DEPLOYMENT.
    
    This script installs dependencies locally into the zip package so
    Kudu has nothing heavy to build. Uses pip install --target to bundle
    all packages into the deployment artifact.

.NOTES
    Requires: Azure CLI, Python 3.11, .env file with AZURE_SUBSCRIPTION_ID
#>

param([switch]$SkipLogin)

$ErrorActionPreference = "Stop"

# --- Load .env ---
$envFile = Join-Path $PSScriptRoot ".env"
if (-not (Test-Path $envFile)) {
    Write-Error "Missing .env file. Copy .env.example to .env and fill in your values."
    exit 1
}
Get-Content $envFile | ForEach-Object {
    if ($_ -match '^\s*([^#][^=]+)=(.*)$') {
        Set-Item -Path "env:$($matches[1].Trim())" -Value $matches[2].Trim()
    }
}
if (-not $env:AZURE_SUBSCRIPTION_ID) { Write-Error "AZURE_SUBSCRIPTION_ID is required in .env file"; exit 1 }

$subscriptionId = $env:AZURE_SUBSCRIPTION_ID
$resourceGroup  = if ($env:AZURE_RESOURCE_GROUP)    { $env:AZURE_RESOURCE_GROUP }    else { "tournament-allocator-rg" }
$location       = if ($env:AZURE_LOCATION)          { $env:AZURE_LOCATION }          else { "eastus" }
$appName        = if ($env:AZURE_APP_NAME)           { $env:AZURE_APP_NAME }           else { "tournament-allocator" }
$appServicePlan = if ($env:AZURE_APP_SERVICE_PLAN)   { $env:AZURE_APP_SERVICE_PLAN }   else { "tournament-allocator-plan" }
$appServiceSku  = if ($env:AZURE_APP_SERVICE_SKU)    { $env:AZURE_APP_SERVICE_SKU }    else { "B1" }

Write-Host "=== deploy-nobuild: Pre-bundled Dependencies ===" -ForegroundColor Cyan
Write-Host "Strategy: Install deps locally, disable remote build" -ForegroundColor DarkGray
Write-Host ""

# --- Login & subscription ---
if (-not $SkipLogin) {
    Write-Host "Checking Azure CLI login status..." -ForegroundColor Yellow
    $account = az account show 2>$null | ConvertFrom-Json
    if (-not $account) { az login }
}
az account set --subscription $subscriptionId

# --- Ensure infrastructure ---
$rgExists = az group exists --name $resourceGroup | ConvertFrom-Json
if (-not $rgExists) { az group create --name $resourceGroup --location $location --output none }

try { az appservice plan show --name $appServicePlan --resource-group $resourceGroup --output none }
catch {
    az appservice plan create --name $appServicePlan --resource-group $resourceGroup --sku $appServiceSku --is-linux --output none
}

try { az webapp show --name $appName --resource-group $resourceGroup --output none }
catch {
    az webapp create --name $appName --resource-group $resourceGroup --plan $appServicePlan --runtime "PYTHON:3.11" --output none
}

# --- Configure: DISABLE remote build ---
Write-Host "Configuring app (remote build DISABLED)..." -ForegroundColor Yellow
az webapp config set --name $appName --resource-group $resourceGroup --startup-file "startup.sh" --output none

az webapp config appsettings set `
    --name $appName `
    --resource-group $resourceGroup `
    --settings SCM_DO_BUILD_DURING_DEPLOYMENT=false DISABLE_COLLECTSTATIC=true SECRET_KEY="$(New-Guid)" `
    --output none

# --- Build package with dependencies pre-installed ---
Write-Host "Building deployment package with pre-installed dependencies..." -ForegroundColor Yellow

$stagingDir = Join-Path $env:TEMP ("deploy-staging-" + [Guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $stagingDir | Out-Null

# Copy app code
Copy-Item -Path (Join-Path $PSScriptRoot "src") -Destination $stagingDir -Recurse
Copy-Item -Path (Join-Path $PSScriptRoot "data") -Destination $stagingDir -Recurse
Copy-Item -Path (Join-Path $PSScriptRoot "startup.sh") -Destination $stagingDir

# Create a modified startup.sh that uses the bundled packages
$startupContent = @'
#!/bin/bash
APP_ROOT="${APP_PATH:-/home/site/wwwroot}"

# Add bundled packages to Python path
export PYTHONPATH="$APP_ROOT/packages:$PYTHONPATH"

# Also try the Oryx venv if it exists
if [ -d "$APP_ROOT/antenv/bin" ]; then
    source "$APP_ROOT/antenv/bin/activate"
fi

cd "$APP_ROOT/src"
exec gunicorn --bind=0.0.0.0:8000 --timeout 600 --threads 4 app:app
'@
$startupContent | Set-Content (Join-Path $stagingDir "startup.sh") -NoNewline

# Prepare requirements (ensure gunicorn is included)
$requirementsPath = Join-Path $PSScriptRoot "requirements.txt"
$requirements = Get-Content $requirementsPath
if ($requirements -notcontains "gunicorn") { $requirements = $requirements + "gunicorn" }

# Install packages into an isolated venv then copy to packages/ dir.
# Using a venv avoids noise from global package conflicts.
$packagesDir = Join-Path $stagingDir "packages"
$tempReq = Join-Path $env:TEMP "requirements-deploy.txt"

# Filter out test-only packages
$prodRequirements = $requirements | Where-Object {
    $_ -notmatch "pytest" -and $_ -notmatch "pytest-cov" -and $_.Trim() -ne ""
}
$prodRequirements | Set-Content $tempReq

Write-Host "  Installing Python packages for Linux x86_64..." -ForegroundColor DarkGray

# Create a temporary isolated venv so global packages don't interfere
$buildVenv = Join-Path $env:TEMP ("deploy-venv-" + [Guid]::NewGuid().ToString("N"))
python -m venv $buildVenv --without-pip 2>$null

# Use --platform to get Linux-compatible wheels in an isolated pip call
python -m pip install `
    --target $packagesDir `
    --platform manylinux2014_x86_64 `
    --python-version 3.11 `
    --only-binary=:all: `
    --isolated `
    -r $tempReq `
    --no-cache-dir `
    --quiet 2>&1 | Where-Object { $_ -notmatch "dependency resolver|already installed|incompatible" }

if ($LASTEXITCODE -ne 0) {
    Write-Host "  Cross-platform pip install failed. Trying without --platform (will work if on Linux)..." -ForegroundColor Yellow
    python -m pip install --target $packagesDir --isolated -r $tempReq --no-cache-dir --quiet
}

Remove-Item $tempReq -ErrorAction SilentlyContinue
Remove-Item $buildVenv -Recurse -Force -ErrorAction SilentlyContinue

# Create zip
$zipFile = Join-Path $env:TEMP "deploy-nobuild.zip"
if (Test-Path $zipFile) { Remove-Item $zipFile }
Write-Host "  Compressing package..." -ForegroundColor DarkGray
Compress-Archive -Path (Join-Path $stagingDir "*") -DestinationPath $zipFile

$zipSizeMB = [math]::Round((Get-Item $zipFile).Length / 1MB, 1)
Write-Host "  Package size: ${zipSizeMB} MB" -ForegroundColor DarkGray

# --- Deploy ---
Write-Host "Waiting for config changes to propagate..." -ForegroundColor Yellow
Start-Sleep -Seconds 15

Write-Host "Deploying (no remote build — should be fast)..." -ForegroundColor Yellow
$deployStart = Get-Date

# Use az webapp deployment source config-zip which is more reliable for large packages
az webapp deployment source config-zip `
    --name $appName `
    --resource-group $resourceGroup `
    --src $zipFile `
    --timeout 600

$deployDuration = [math]::Round(((Get-Date) - $deployStart).TotalSeconds)

if ($LASTEXITCODE -ne 0) {
    Write-Error "Deployment failed after ${deployDuration}s."
} else {
    Write-Host "Deployment completed in ${deployDuration}s." -ForegroundColor Green
}

# --- Cleanup ---
Remove-Item $zipFile -ErrorAction SilentlyContinue
Remove-Item $stagingDir -Recurse -Force -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "=== Deployment Complete ===" -ForegroundColor Green
Write-Host "App URL: https://$appName.azurewebsites.net" -ForegroundColor Cyan
