### 2026-02-14: GitHub Actions deployment via deploygh.ps1

**By:** Keaton

**What:** Created `deploygh.ps1` script that provisions Azure App Service infrastructure and configures GitHub Actions for automatic deployment on push. The script generates a `.github/workflows/azure-deployment.yml` workflow file, sets up Azure publish profile credentials as GitHub secrets, and configures the same runtime settings as `deploy.ps1` (startup command, app settings, SECRET_KEY, ADMIN_PASSWORD, TOURNAMENT_DATA_DIR).

**Why:** Manual deployment via `deploy.ps1` requires running the script every time code changes. GitHub Actions automation enables zero-touch deployments triggered by git push, reducing deployment friction and enabling faster iteration. The script is idempotent and safe to re-run, following Azure best practices by checking for existing resources before creation. This approach separates infrastructure provisioning (one-time setup) from code deployment (continuous), which is the standard pattern for modern CI/CD.

**Impact:** Developers can now choose between manual deployment (`deploy.ps1`) or continuous deployment (`deploygh.ps1`). The workflow file is committed to the repository, making the deployment process transparent and version-controlled. Requires both Azure CLI and GitHub CLI to be installed and authenticated.
