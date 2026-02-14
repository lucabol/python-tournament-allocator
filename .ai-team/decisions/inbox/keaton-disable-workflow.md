# Decision: Disable Azure Deployment Workflow (B1 Tier Limitation)

**Date**: $(date)
**Decision Maker**: Keaton (Azure Deployment Specialist)
**Status**: IMPLEMENTED

## Problem
The GitHub Actions deployment workflow (`azure-deployment.yml`) was designed to automatically deploy to Azure App Service on every push to main. However, the production app is running on Azure B1 tier, which does not support deployment slots—a critical requirement for zero-downtime deployments.

## Solution
Disabled the entire `azure-deployment.yml` workflow by commenting it out with detailed documentation. This prevents automatic deployments that would cause service interruptions.

### Why This Approach?
- **Preserves knowledge**: The commented code remains visible for future reference
- **Clear documentation**: Includes explicit explanation of why it's disabled and the B1 tier limitation
- **Easy re-enablement**: Can be quickly uncommented if the app is upgraded to Standard or Premium tier
- **Low risk**: Prevents accidental deployments while maintaining deployment infrastructure knowledge

## Next Steps
- If Azure plan is upgraded to Standard or Premium tier → uncomment the workflow
- For deployments in the interim → use manual Azure CLI or Portal deployment
- Document any manual deployment process in the runbook

## References
- B1 tier limitations: No deployment slots support
- Original workflow: `.github/workflows/azure-deployment.yml`
