---
name: "powershell-exitcode-checking"
description: "Checking external command success in PowerShell using $LASTEXITCODE instead of try/catch"
domain: "scripting"
confidence: "low"
source: "earned"
---

## Context
PowerShell's try/catch blocks only catch terminating errors (exceptions), not non-zero exit codes from external commands like Azure CLI, git, npm, or other executables. To detect when an external command fails, you must check `$LASTEXITCODE` after the command completes.

## Patterns

### Checking Command Success
```powershell
# Run the command and suppress stderr if you expect failure
az resource show --name myresource --resource-group myrg --output none 2>$null
$exists = ($LASTEXITCODE -eq 0)

if ($exists) {
    Write-Host "Resource exists"
} else {
    Write-Host "Resource does not exist, creating..."
    az resource create ...
}
```

### Common Use Cases
- **Resource existence checks**: `az appservice plan show`, `az webapp show`, `kubectl get`
- **Git operations**: `git diff --quiet`, `git show <ref>`
- **Package managers**: `npm list <package>`, `pip show <package>`

### Why Try/Catch Doesn't Work
```powershell
# ❌ This does NOT work — $exists will always be $true
$exists = $false
try {
    az webapp show --name myapp --resource-group myrg --output none
    $exists = $true
} catch {
    $exists = $false  # Never reached for non-zero exit codes
}

# ✅ This DOES work
az webapp show --name myapp --resource-group myrg --output none 2>$null
$exists = ($LASTEXITCODE -eq 0)
```

## Anti-Patterns
- **Using try/catch for external commands** — will not catch non-zero exit codes
- **Forgetting to redirect stderr** — fills console with error messages when you expect failure
- **Not checking $LASTEXITCODE immediately** — the value is overwritten by the next command

## Examples

### Azure Resource Existence Check
```powershell
# Check if App Service Plan exists, create if missing
az appservice plan show --name $planName --resource-group $rgName --output none 2>$null
if ($LASTEXITCODE -eq 0) {
    Write-Host "App Service Plan exists"
} else {
    Write-Host "Creating App Service Plan..."
    az appservice plan create --name $planName --resource-group $rgName --sku B1
}
```

### Git Branch Check
```powershell
# Check if branch exists
git show-ref --verify --quiet refs/heads/$branchName 2>$null
if ($LASTEXITCODE -eq 0) {
    git checkout $branchName
} else {
    git checkout -b $branchName
}
```

### Package Installation Check
```powershell
# Check if npm package is installed globally
npm list -g typescript --depth=0 2>$null | Out-Null
if ($LASTEXITCODE -eq 0) {
    Write-Host "TypeScript is installed"
} else {
    npm install -g typescript
}
```
