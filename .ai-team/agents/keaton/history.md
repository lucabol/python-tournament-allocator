# History — Keaton

## Project Learnings (from import)

**Project:** Python Flask tournament scheduling and management web application
**Owner:** Luca Bolognese (lucabol@microsoft.com)
**Stack:** Python 3.11+, Flask, Jinja2, pandas, numpy, OR-Tools CP-SAT, PyYAML, pytest
**Description:** Tournament scheduling app with pool play, single/double elimination brackets, court allocation, and match result tracking.

## Learnings

### 2026-02-14: Joined the team
- Added as Azure Deployment Specialist
- Responsible for Azure App Service deployments, CI/CD, monitoring, and production environment management
- Key deployment artifact: `deploy.ps1` (PowerShell deployment script)
- CI/CD pipelines in `.github/workflows/`

### GitHub Actions deployment automation
- Created `deploygh.ps1` script for one-time setup of GitHub Actions continuous deployment
- Script provisions same Azure infrastructure as `deploy.ps1` but configures auto-deployment instead of manual push
- Uses Azure publish profiles with GitHub secrets for secure credential management
- Generates `.github/workflows/azure-deployment.yml` workflow file automatically
- Workflow triggers on push to specified branch (default: main) or manual dispatch
- Deployment package includes src/, startup.sh, and requirements.txt with auto-added gunicorn
- Script is idempotent: safe to re-run, checks for existing resources before creation
- Requires both Azure CLI (`az`) and GitHub CLI (`gh`) with authenticated sessions
- Parses repository owner/name from git remote origin URL

### GitHub Actions deployment issues with B1 tier (2026-02-14)
- **Issue:** `azure/webapps-deploy@v2` and `@v3` actions default `slot-name: production` internally when using publish profiles
- **Root cause:** B1 (Basic) App Service tier does NOT support deployment slots — slots require Standard tier or higher
- **Error:** "Publish profile is invalid for app-name and slot-name provided" followed by 401 Unauthorized
- **Workaround attempts:**
  1. Upgrading to v3 — still adds slot-name internally
  2. Removing app-name parameter — still defaults to production slot
  3. Azure Login with service principal — requires different credential format, complex setup
- **Current status:** GitHub Actions deployment NOT working on B1 tier due to action's slot assumptions
- **Recommended solution:** Use `deploy.ps1` for manual deployments until upgrading to Standard tier or action is fixed
- **Alternative:** Upgrade App Service to Standard tier (S1+) to support deployment slots
