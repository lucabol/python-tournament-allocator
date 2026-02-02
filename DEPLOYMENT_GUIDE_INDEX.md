# Azure App Service - Deployment Guide Index

Welcome! This repository is fully configured for Azure App Service deployment. This index helps you find the right documentation for your needs.

## 🚀 I Want to Deploy Now! (Fastest Path)

**Time: 20 minutes**

1. Open **[QUICKSTART_AZURE.md](./QUICKSTART_AZURE.md)**
2. Follow the "Azure Portal with GitHub" method (3 steps)
3. Wait 5-10 minutes for first deployment
4. Access your app at `https://your-app-name.azurewebsites.net`

**Perfect for:** First-time users, quick testing

---

## 📖 I Want to Understand Everything First

**Read in this order:**

1. **[SETUP_SUMMARY.md](./SETUP_SUMMARY.md)** - Start here for complete overview
2. **[ARCHITECTURE.md](./ARCHITECTURE.md)** - Understand the technical setup
3. **[AZURE_DEPLOYMENT.md](./AZURE_DEPLOYMENT.md)** - Deep dive into deployment
4. **[DEPLOYMENT_CHECKLIST.md](./DEPLOYMENT_CHECKLIST.md)** - Use as you deploy

**Perfect for:** Learning the full system, production deployments

---

## 🔧 I'm Ready for Production

**Pre-Production Checklist:**

1. Read **[DEPLOYMENT_CHECKLIST.md](./DEPLOYMENT_CHECKLIST.md)**
2. Set up data persistence (Azure Files or Database)
3. Upgrade to Basic (B1) or higher tier
4. Enable "Always On" setting
5. Configure Application Insights monitoring
6. Set strong SECRET_KEY in app settings
7. Review security settings in **[AZURE_DEPLOYMENT.md](./AZURE_DEPLOYMENT.md#security)**

**Perfect for:** Production deployments, professional setups

---

## 🤖 I Want Automated Deployment

**GitHub Actions CI/CD:**

1. Open **[.github/workflows/azure-deploy.yml](./.github/workflows/azure-deploy.yml)**
2. Update `AZURE_WEBAPP_NAME` to your app name
3. Download publish profile from Azure Portal
4. Add as GitHub secret: `AZURE_WEBAPP_PUBLISH_PROFILE`
5. Push to main branch → automatic deployment!

See details in **[AZURE_DEPLOYMENT.md](./AZURE_DEPLOYMENT.md#option-2-deploy-via-azure-cli)**

**Perfect for:** Continuous deployment, team workflows

---

## 📋 I Need a Step-by-Step Checklist

Open **[DEPLOYMENT_CHECKLIST.md](./DEPLOYMENT_CHECKLIST.md)**

This comprehensive checklist covers:
- ☑️ Pre-deployment preparation
- ☑️ Resource creation
- ☑️ App configuration
- ☑️ Deployment verification
- ☑️ Data persistence setup
- ☑️ Monitoring configuration
- ☑️ Cost management

**Perfect for:** Methodical deployments, avoiding mistakes

---

## 💻 I Prefer Command Line

**Azure CLI Method:**

All commands are in **[QUICKSTART_AZURE.md](./QUICKSTART_AZURE.md#using-azure-cli-alternative)**

Quick reference:
```bash
az login
az group create --name tournament-rg --location eastus
az appservice plan create --name tournament-plan --resource-group tournament-rg --sku B1 --is-linux
az webapp create --resource-group tournament-rg --plan tournament-plan --name <your-app-name> --runtime "PYTHON|3.11"
az webapp config set --resource-group tournament-rg --name <your-app-name> --startup-file "chmod +x /home/site/wwwroot/startup.sh && /home/site/wwwroot/startup.sh"
```

**Perfect for:** Automation, scripting, DevOps

---

## 🆘 Something Went Wrong

**Troubleshooting Resources:**

1. **[AZURE_DEPLOYMENT.md](./AZURE_DEPLOYMENT.md#troubleshooting)** - Common issues and solutions
2. Check deployment logs:
   - Portal: App Service → Deployment Center → Logs
   - CLI: `az webapp log tail --name <app-name> --resource-group tournament-rg`
3. **[DEPLOYMENT_CHECKLIST.md](./DEPLOYMENT_CHECKLIST.md#troubleshooting-steps)** - Troubleshooting checklist

**Common Issues:**
- App won't start → Check startup command
- Slow performance → Upgrade to B1+ tier
- Data keeps disappearing → Set up Azure Files mount
- Deployment fails → Check build logs

---

## 📚 Complete Documentation Map

### Quick Start Guides
- **[QUICKSTART_AZURE.md](./QUICKSTART_AZURE.md)** (2.9KB) - 10-minute deployment
- **[SETUP_SUMMARY.md](./SETUP_SUMMARY.md)** (9.4KB) - Overview of everything

### Comprehensive Guides
- **[AZURE_DEPLOYMENT.md](./AZURE_DEPLOYMENT.md)** (9.7KB) - Complete deployment reference
- **[DEPLOYMENT_CHECKLIST.md](./DEPLOYMENT_CHECKLIST.md)** (8.1KB) - Step-by-step checklist
- **[ARCHITECTURE.md](./ARCHITECTURE.md)** (15KB) - Technical architecture

### Configuration Files
- **[startup.sh](./startup.sh)** - Production startup script
- **[.deployment](./.deployment)** - Azure build config
- **[.env.example](./.env.example)** - Environment template
- **[.gitignore](./.gitignore)** - Git exclusions
- **[.github/workflows/azure-deploy.yml](./.github/workflows/azure-deploy.yml)** - CI/CD workflow
- **[requirements.txt](./requirements.txt)** - Python dependencies (includes gunicorn)

---

## 💰 Pricing Guide

| Tier | Cost | CPU | RAM | Use Case |
|------|------|-----|-----|----------|
| F1 (Free) | $0/month | Shared | 1GB | Testing only |
| B1 (Basic) | ~$13/month | 1 vCPU | 1.75GB | **Recommended minimum** |
| B2 (Basic) | ~$26/month | 2 vCPU | 3.5GB | Better performance |
| S1 (Standard) | ~$70/month | 1 vCPU | 1.75GB | Auto-scaling, staging |
| P1V2 (Premium) | ~$100/month | 1 vCPU | 3.5GB | High performance |

**Recommendation:** Start with B1 Basic for production. Free tier is too slow for ortools.

See full pricing details in **[ARCHITECTURE.md](./ARCHITECTURE.md#pricing-tiers)**

---

## ⚡ Quick Tips

### Before You Deploy
- ✅ Azure account created
- ✅ Repository pushed to GitHub
- ✅ Choose deployment method

### For Best Results
- 🎯 Use B1 or higher tier
- 🎯 Enable "Always On" (B1+ tier)
- 🎯 Set up Azure Files for data persistence
- 🎯 Configure strong SECRET_KEY
- 🎯 Enable Application Insights

### Time Estimates
- First deployment: 5-10 minutes (ortools installation)
- Subsequent deployments: 2-3 minutes
- Setup time: 10-20 minutes (depending on method)

---

## 🎯 Recommended Learning Paths

### Path 1: Quick Learner
1. QUICKSTART_AZURE.md (5 min read)
2. Deploy via Portal (5 min)
3. Wait for deployment (10 min)
4. **Done!**

### Path 2: Thorough Learner
1. SETUP_SUMMARY.md (10 min read)
2. ARCHITECTURE.md (15 min read)
3. QUICKSTART_AZURE.md (5 min read)
4. Deploy via Portal (5 min)
5. DEPLOYMENT_CHECKLIST.md (refer as needed)
6. **Done!**

### Path 3: Production Ready
1. SETUP_SUMMARY.md
2. AZURE_DEPLOYMENT.md (complete read)
3. DEPLOYMENT_CHECKLIST.md (use while deploying)
4. ARCHITECTURE.md (reference)
5. Set up data persistence
6. Configure monitoring
7. Set up CI/CD
8. **Production ready!**

---

## 🔗 External Resources

- [Azure Portal](https://portal.azure.com)
- [Azure App Service Docs](https://docs.microsoft.com/azure/app-service/)
- [Python on Azure](https://docs.microsoft.com/azure/app-service/quickstart-python)
- [Pricing Calculator](https://azure.microsoft.com/pricing/calculator/)

---

## 📞 Support

If you're stuck:
1. Check the troubleshooting section in AZURE_DEPLOYMENT.md
2. Review deployment logs in Azure Portal
3. Consult the DEPLOYMENT_CHECKLIST.md

---

**Ready to start?** Choose your path above and begin deploying! 🚀

Most users should start with: **[QUICKSTART_AZURE.md](./QUICKSTART_AZURE.md)**
