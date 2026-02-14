### 2026-02-14: PowerShell Azure CLI existence checks use $LASTEXITCODE
**By:** McManus
**What:** In `deploy.ps1`, resource existence checks for App Service Plan and Web App now use `$LASTEXITCODE` after `az ... show` commands instead of try/catch blocks. Pattern is: `az <command> 2>$null; $exists = ($LASTEXITCODE -eq 0)`.
**Why:** PowerShell doesn't automatically throw exceptions for non-zero exit codes from external commands like Azure CLI. Try/catch blocks don't catch these failures, causing the script to incorrectly report that resources exist when they don't. Checking `$LASTEXITCODE` directly after running the command is the correct PowerShell pattern for detecting command failures.
