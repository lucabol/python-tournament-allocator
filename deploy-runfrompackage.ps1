<#
.SYNOPSIS
    Deploys using WEBSITE_RUN_FROM_PACKAGE (bypasses Kudu build entirely).

.DESCRIPTION
    This approach skips Kudu's Oryx build system completely by:
    1. Installing all Python dependencies locally into a virtual env
    2. Packaging everything (code + deps) into a single zip
    3. Using WEBSITE_RUN_FROM_PACKAGE=1 so Azure mounts the zip directly
    
    This eliminates the 502 error entirely since Kudu never builds anything.
    The app runs directly from the mounted zip filesystem.

    Trade-off: The zip is larger (~100MB+) but deployment is fast and reliable.
    
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

Write-Host "=== deploy-runfrompackage: Run From Package (No Kudu Build) ===" -ForegroundColor Cyan
Write-Host "Strategy: Bundle all deps locally, mount zip as filesystem" -ForegroundColor DarkGray
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

# --- Configure for run-from-package ---
Write-Host "Configuring app for run-from-package mode..." -ForegroundColor Yellow

# Custom startup: since we bundle deps, we need to set PYTHONPATH
$startupCmd = "cd /home/site/wwwroot/src && PYTHONPATH=/home/site/wwwroot/packages:\$PYTHONPATH gunicorn --bind=0.0.0.0:8000 --timeout 600 --threads 4 app:app"

az webapp config set --name $appName --resource-group $resourceGroup --startup-file "$startupCmd" --output none

az webapp config appsettings set `
    --name $appName `
    --resource-group $resourceGroup `
    --settings `
        SCM_DO_BUILD_DURING_DEPLOYMENT=false `
        WEBSITE_RUN_FROM_PACKAGE=1 `
        DISABLE_COLLECTSTATIC=true `
        SECRET_KEY="$(New-Guid)" `
    --output none

# --- Build self-contained package ---
Write-Host "Building self-contained deployment package..." -ForegroundColor Yellow

$stagingDir = Join-Path $env:TEMP ("deploy-staging-" + [Guid]::NewGuid().ToString("N"))
New-Item -ItemType Directory -Path $stagingDir | Out-Null

# Copy app code
Copy-Item -Path (Join-Path $PSScriptRoot "src") -Destination $stagingDir -Recurse
Copy-Item -Path (Join-Path $PSScriptRoot "data") -Destination $stagingDir -Recurse

# Prepare requirements
$requirements = Get-Content (Join-Path $PSScriptRoot "requirements.txt")
if ($requirements -notcontains "gunicorn") { $requirements = $requirements + "gunicorn" }

# Filter out test-only packages to reduce zip size
$prodRequirements = $requirements | Where-Object {
    $_ -notmatch "pytest" -and $_ -notmatch "pytest-cov" -and $_.Trim() -ne ""
}

$tempReq = Join-Path $env:TEMP "requirements-prod.txt"
$prodRequirements | Set-Content $tempReq

# Install packages for Linux x86_64
$packagesDir = Join-Path $stagingDir "packages"
Write-Host "  Downloading Linux x86_64 wheels..." -ForegroundColor DarkGray

pip install `
    --target $packagesDir `
    --platform manylinux2014_x86_64 `
    --python-version 3.11 `
    --only-binary=:all: `
    -r $tempReq `
    --no-cache-dir `
    --quiet 2>&1 | Out-Null

if ($LASTEXITCODE -ne 0) {
    Write-Host "  Some packages don't have manylinux wheels. Trying manylinux_2_17..." -ForegroundColor Yellow
    pip install `
        --target $packagesDir `
        --platform manylinux_2_17_x86_64 `
        --python-version 3.11 `
        --only-binary=:all: `
        -r $tempReq `
        --no-cache-dir `
        --quiet 2>&1 | Out-Null
}

if ($LASTEXITCODE -ne 0) {
    Write-Host "  Cross-platform install failed. Falling back to native install..." -ForegroundColor Yellow
    Write-Host "  NOTE: This will only work if you're on Linux. On Windows, consider using WSL." -ForegroundColor Yellow
    pip install --target $packagesDir -r $tempReq --no-cache-dir --quiet
}

Remove-Item $tempReq -ErrorAction SilentlyContinue

# Create zip (use .NET for better compression on large packages)
$zipFile = Join-Path $env:TEMP "deploy-rfp.zip"
if (Test-Path $zipFile) { Remove-Item $zipFile }

Write-Host "  Compressing package (this may take a moment for large deps)..." -ForegroundColor DarkGray
Add-Type -AssemblyName System.IO.Compression.FileSystem
[System.IO.Compression.ZipFile]::CreateFromDirectory($stagingDir, $zipFile, [System.IO.Compression.CompressionLevel]::Optimal, $false)

$zipSizeMB = [math]::Round((Get-Item $zipFile).Length / 1MB, 1)
Write-Host "  Package size: ${zipSizeMB} MB" -ForegroundColor DarkGray

# --- Deploy ---
Write-Host "Deploying package (no build step — just uploading)..." -ForegroundColor Yellow
$deployStart = Get-Date

az webapp deployment source config-zip `
    --name $appName `
    --resource-group $resourceGroup `
    --src $zipFile `
    --timeout 600

$deployDuration = [math]::Round(((Get-Date) - $deployStart).TotalSeconds)

if ($LASTEXITCODE -ne 0) {
    Write-Error "Deployment failed after ${deployDuration}s."
} else {
    Write-Host "  Upload completed in ${deployDuration}s." -ForegroundColor Green
}

# --- Verify ---
Write-Host "Verifying app is responding..." -ForegroundColor Yellow
$appUrl = "https://$appName.azurewebsites.net"
$verifyAttempts = 0
$appResponding = $false

while (-not $appResponding -and $verifyAttempts -lt 6) {
    $verifyAttempts++
    Start-Sleep -Seconds 10
    try {
        $response = Invoke-WebRequest -Uri $appUrl -UseBasicParsing -TimeoutSec 30
        if ($response.StatusCode -eq 200) {
            $appResponding = $true
            Write-Host "  App is responding (HTTP 200)." -ForegroundColor Green
        }
    } catch {
        Write-Host "  App not ready yet (attempt $verifyAttempts/6)..." -ForegroundColor DarkGray
    }
}

if (-not $appResponding) {
    Write-Host "  WARNING: App may still be starting. Check logs:" -ForegroundColor Yellow
    Write-Host "  az webapp log tail --name $appName --resource-group $resourceGroup" -ForegroundColor Yellow
}

# --- Cleanup ---
Remove-Item $zipFile -ErrorAction SilentlyContinue
Remove-Item $stagingDir -Recurse -Force -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "=== Deployment Complete ===" -ForegroundColor Green
Write-Host "App URL: $appUrl" -ForegroundColor Cyan
Write-Host ""
Write-Host "NOTE: data/ is read-only in run-from-package mode." -ForegroundColor Yellow
Write-Host "If the app writes to data/ at runtime, switch to deploy-nobuild.ps1 instead." -ForegroundColor Yellow
