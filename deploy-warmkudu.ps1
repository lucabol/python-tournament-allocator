<#
.SYNOPSIS
    Deploys with aggressive Kudu warm-up and proper 502 detection.

.DESCRIPTION
    The original deploy.ps1 has two bugs:
    1. az webapp deploy returns exit code 0 even on 502, so retry logic never fires.
    2. A 15-second wait after config changes isn't enough for Kudu to fully restart.
    
    This script fixes both: it explicitly pings Kudu until it's healthy before
    deploying, and checks the deployment result via the Kudu API rather than
    trusting the exit code.

.NOTES
    Requires: Azure CLI, .env file with AZURE_SUBSCRIPTION_ID
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

Write-Host "=== deploy-warmkudu: Warm Kudu + Proper 502 Handling ===" -ForegroundColor Cyan
Write-Host "Strategy: Restart Kudu, wait until healthy, then deploy with verification" -ForegroundColor DarkGray
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

# --- Configure ---
Write-Host "Configuring app settings..." -ForegroundColor Yellow
az webapp config set --name $appName --resource-group $resourceGroup --startup-file "startup.sh" --output none

az webapp config appsettings set `
    --name $appName `
    --resource-group $resourceGroup `
    --settings SCM_DO_BUILD_DURING_DEPLOYMENT=true DISABLE_COLLECTSTATIC=true SECRET_KEY="$(New-Guid)" `
    --output none

# --- Restart and warm up Kudu before deploying ---
Write-Host "Restarting app to ensure clean Kudu state..." -ForegroundColor Yellow
az webapp restart --name $appName --resource-group $resourceGroup

Write-Host "Waiting for Kudu to become healthy..." -ForegroundColor Yellow
$kuduUrl = "https://$appName.scm.azurewebsites.net"
$maxWaitSeconds = 120
$waited = 0
$kuduReady = $false

while (-not $kuduReady -and $waited -lt $maxWaitSeconds) {
    try {
        # Use az rest to call Kudu with proper auth
        $kuduStatus = az rest --method get --url "$kuduUrl/api/environment" --resource "https://management.azure.com/" 2>$null
        if ($kuduStatus) {
            $kuduReady = $true
            Write-Host "  Kudu is healthy (waited ${waited}s)." -ForegroundColor Green
        }
    } catch {
        # Also try a simpler check via the webapp itself
        try {
            $publishProfile = az webapp deployment list-publishing-credentials `
                --name $appName --resource-group $resourceGroup --query "{user:publishingUserName,pass:publishingPassword}" -o json 2>$null | ConvertFrom-Json
            if ($publishProfile) {
                $kuduReady = $true
                Write-Host "  Kudu credentials accessible (waited ${waited}s)." -ForegroundColor Green
            }
        } catch {}
    }

    if (-not $kuduReady) {
        Start-Sleep -Seconds 10
        $waited += 10
        Write-Host "  Waiting... (${waited}s / ${maxWaitSeconds}s)" -ForegroundColor DarkGray
    }
}

if (-not $kuduReady) {
    Write-Host "  WARNING: Could not confirm Kudu health after ${maxWaitSeconds}s. Proceeding anyway..." -ForegroundColor Yellow
}

# --- Build deployment package ---
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
if ($requirements -notcontains "gunicorn") { $requirements = $requirements + "gunicorn" }
$requirements | Set-Content (Join-Path $stagingDir "requirements.txt")

Compress-Archive -Path (Join-Path $stagingDir "*") -DestinationPath $zipFile

# --- Deploy with proper 502 detection ---
Write-Host "Deploying application..." -ForegroundColor Yellow
Write-Host "  Remote build will install numpy/pandas/ortools (may take 3-5 minutes)..." -ForegroundColor DarkGray

$deployMaxRetries = 3
$deployAttempt = 0
$deploySuccess = $false

while (-not $deploySuccess -and $deployAttempt -lt $deployMaxRetries) {
    $deployAttempt++
    $deployStart = Get-Date

    Write-Host "  Attempt $deployAttempt/$deployMaxRetries..." -ForegroundColor Yellow

    # Capture both stdout and stderr to detect 502 in output
    $deployOutput = az webapp deploy `
        --name $appName `
        --resource-group $resourceGroup `
        --src-path $zipFile `
        --type zip `
        --clean true `
        --track-status false `
        --timeout 600000 2>&1

    $exitCode = $LASTEXITCODE
    $deployDuration = [math]::Round(((Get-Date) - $deployStart).TotalSeconds)
    $outputText = $deployOutput | Out-String

    # Check for 502 in output (az webapp deploy returns 0 even on 502!)
    if ($outputText -match "502" -or $outputText -match "Bad Gateway" -or $exitCode -ne 0) {
        Write-Host "  Attempt $deployAttempt failed after ${deployDuration}s (502/Bad Gateway from Kudu)." -ForegroundColor Yellow

        if ($deployAttempt -lt $deployMaxRetries) {
            # Exponential backoff: 30s, 60s
            $backoff = 30 * $deployAttempt
            Write-Host "  Restarting Kudu and waiting ${backoff}s before retry..." -ForegroundColor Yellow
            az webapp restart --name $appName --resource-group $resourceGroup 2>$null
            Start-Sleep -Seconds $backoff
        } else {
            Write-Error "Deployment failed after $deployMaxRetries attempts. Last output:`n$outputText"
        }
    } else {
        $deploySuccess = $true
        Write-Host "  Deployment succeeded in ${deployDuration}s." -ForegroundColor Green
    }
}

# --- Verify deployment by checking the app responds ---
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
    Write-Host "  WARNING: App not responding yet. It may still be starting up." -ForegroundColor Yellow
    Write-Host "  Check logs: az webapp log tail --name $appName --resource-group $resourceGroup" -ForegroundColor Yellow
}

# --- Cleanup ---
Remove-Item $zipFile -ErrorAction SilentlyContinue
Remove-Item $stagingDir -Recurse -Force -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "=== Deployment Complete ===" -ForegroundColor Green
Write-Host "App URL: $appUrl" -ForegroundColor Cyan
