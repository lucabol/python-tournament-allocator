# Azure App Service Setup - Complete Guide

This repository is now fully configured for deployment to Azure App Service. All necessary configuration files and documentation have been added.

## 📚 Documentation Structure

We've created comprehensive documentation to help you deploy this Flask application to Azure:

### Quick Start
- **[QUICKSTART_AZURE.md](./QUICKSTART_AZURE.md)** - Get your app deployed in 10 minutes
  - Portal-based deployment (easiest)
  - Azure CLI commands (for automation)
  - Minimal configuration required

### Detailed Guides
- **[AZURE_DEPLOYMENT.md](./AZURE_DEPLOYMENT.md)** - Complete deployment guide
  - Three deployment methods (Portal, CLI, VS Code)
  - Data persistence options (critical for production)
  - Performance optimization
  - Security configuration
  - Custom domain setup
  - Troubleshooting guide

### Reference Materials
- **[DEPLOYMENT_CHECKLIST.md](./DEPLOYMENT_CHECKLIST.md)** - Step-by-step checklist
  - Pre-deployment preparation
  - Resource creation steps
  - Configuration checklist
  - Post-deployment verification
  - Monitoring setup
  - Cost management

- **[ARCHITECTURE.md](./ARCHITECTURE.md)** - Technical architecture
  - Deployment architecture diagrams
  - Component descriptions
  - Pricing tier comparison
  - Scaling strategies
  - Best practices

- **[.env.example](./.env.example)** - Environment configuration template
  - Application settings reference
  - How to configure in Azure Portal or CLI

## 🚀 Quick Deployment (3 Steps)

### 1. Create App Service (Azure Portal)
```
1. Go to https://portal.azure.com
2. Create a resource → Web App
3. Configure:
   - Name: <your-unique-name>
   - Runtime: Python 3.11
   - OS: Linux
   - Plan: B1 Basic ($13/month recommended)
4. Create
```

### 2. Connect GitHub
```
1. Your App Service → Deployment Center
2. Source: GitHub
3. Authorize and select:
   - Repo: lucabol/python-tournament-allocator
   - Branch: main
4. Save
```

### 3. Set Startup Command
```
1. Configuration → General settings
2. Startup Command:
   chmod +x /home/site/wwwroot/startup.sh && /home/site/wwwroot/startup.sh
3. Save
```

**That's it!** Your app will be live at `https://<your-name>.azurewebsites.net` in 5-10 minutes.

## 📁 Configuration Files Added

### Core Files
- **`startup.sh`** - Application startup script
  - Creates data directory structure
  - Initializes default configuration files
  - Starts gunicorn with 4 workers
  - ✅ Executable and tested

- **`.deployment`** - Azure build configuration
  - Enables build during deployment
  - Installs Python packages from requirements.txt

- **`requirements.txt`** - Updated with gunicorn
  - Added `gunicorn>=21.0.0` for production WSGI server
  - All other dependencies preserved

### Automation
- **`.github/workflows/azure-deploy.yml`** - GitHub Actions workflow (optional)
  - Automated build and deployment
  - Triggered on push to main branch
  - Requires publish profile secret

### Development
- **`.gitignore`** - Git ignore rules
  - Excludes Python cache files
  - Excludes virtual environments
  - Excludes local data files (can be overridden)

## ⚠️ Important Considerations

### 1. Data Persistence
**By default, file storage in Azure App Service is ephemeral!**

Your data files (teams.yaml, courts.csv, etc.) may be lost when:
- App restarts
- Deployment occurs
- App scales to multiple instances

**Solutions:**
1. **Azure Files Mount** (Recommended for production)
   - Persistent across restarts
   - See AZURE_DEPLOYMENT.md for setup instructions
   
2. **Azure SQL Database** (Best for scaling)
   - Requires code refactoring
   - Better for multi-instance deployments

3. **Regular Backups** (Quick fix)
   - Download data files periodically
   - Acceptable for development/testing

### 2. First Deployment Time
- Expect 5-10 minutes for first deployment
- `ortools` package is ~100MB and takes time to install
- Subsequent deployments are faster (cached dependencies)

### 3. Performance
- **Free (F1) tier**: Very limited, may timeout during ortools operations
- **Basic (B1) tier**: Minimum recommended ($13/month)
- **Standard (S1) tier**: Better performance, auto-scaling ($70/month)

Enable "Always On" (Basic tier+) to prevent cold starts.

### 4. Cost Management
- Free tier: $0/month (testing only)
- Basic B1: ~$13/month (recommended minimum)
- Standard S1: ~$70/month (production with auto-scaling)
- Storage: Additional ~$0.06/GB/month if using Azure Files

Set up budget alerts in Azure Cost Management!

## 🧪 Local Testing

Test the deployment configuration locally:

```bash
# Install dependencies
pip install -r requirements.txt

# Test with gunicorn (production server)
cd src
gunicorn --bind=0.0.0.0:8000 --workers=2 app:app

# Or test with Flask dev server
python app.py
```

Visit `http://localhost:8000` (gunicorn) or `http://localhost:5000` (Flask dev).

## 📊 Deployment Options Comparison

| Method | Difficulty | Best For | Setup Time |
|--------|-----------|----------|------------|
| Azure Portal + GitHub | ⭐ Easy | First-time users | 10 min |
| Azure CLI | ⭐⭐ Medium | Automation, scripts | 15 min |
| GitHub Actions | ⭐⭐ Medium | CI/CD pipelines | 20 min |
| VS Code Extension | ⭐ Easy | Developers using VS Code | 10 min |

**Recommendation**: Start with Azure Portal + GitHub for simplest setup.

## 🔍 Monitoring Your App

### View Logs
```bash
# Real-time logs
az webapp log tail --name <app-name> --resource-group tournament-rg

# Or in Azure Portal
# App Service → Monitoring → Log stream
```

### Check App Status
```bash
# App Service status
az webapp show --name <app-name> --resource-group tournament-rg --query state

# Restart app
az webapp restart --name <app-name> --resource-group tournament-rg
```

### Enable Application Insights
Portal: App Service → Monitoring → Application Insights → Turn on

Provides:
- Performance monitoring
- Exception tracking
- User analytics
- Custom metrics

## 🆘 Troubleshooting

### App won't start
1. Check startup command is set correctly
2. View logs: `az webapp log tail --name <app-name> --resource-group tournament-rg`
3. Verify requirements.txt has all dependencies
4. Check Python version is 3.11

### App is slow
1. Upgrade from Free (F1) to Basic (B1) tier
2. Enable "Always On" in Configuration
3. Check Application Insights for bottlenecks

### Data keeps disappearing
1. Implement Azure Files mount (see AZURE_DEPLOYMENT.md)
2. Or use Azure SQL Database

### Deployment fails
1. Check deployment logs in Deployment Center
2. Verify GitHub connection is active
3. Check build logs for package installation errors

## 📖 Next Steps

1. **Deploy the application** using QUICKSTART_AZURE.md
2. **Verify it works** by testing all features
3. **Set up data persistence** if needed for production
4. **Configure monitoring** with Application Insights
5. **Set up alerts** for errors and performance issues
6. **Configure custom domain** (optional)
7. **Enable authentication** if needed (optional)

## 🎯 Production Readiness Checklist

Before going to production:

- [ ] Upgrade to Basic (B1) or higher tier
- [ ] Enable "Always On"
- [ ] Set up Azure Files mount for data persistence
- [ ] Configure strong SECRET_KEY in Application Settings
- [ ] Enable HTTPS Only
- [ ] Set up Application Insights
- [ ] Configure alerts for errors and performance
- [ ] Set up budget alerts
- [ ] Document recovery procedures
- [ ] Test backup and restore process
- [ ] Configure authentication (if needed)
- [ ] Set up staging slot (Standard tier) for testing deployments

## 📞 Support Resources

- **Azure Documentation**: https://docs.microsoft.com/azure/app-service/
- **Python on Azure**: https://docs.microsoft.com/azure/app-service/quickstart-python
- **Azure CLI Reference**: https://docs.microsoft.com/cli/azure/
- **Pricing Calculator**: https://azure.microsoft.com/pricing/calculator/

## 📝 Files Reference

All files added/modified in this setup:

```
python-tournament-allocator/
├── startup.sh                    # App Service startup script ⭐ NEW
├── .deployment                   # Build configuration ⭐ NEW
├── .gitignore                    # Git ignore rules ⭐ NEW
├── .env.example                  # Environment template ⭐ NEW
├── requirements.txt              # Updated with gunicorn ✏️ MODIFIED
├── README.md                     # Updated with deployment info ✏️ MODIFIED
├── QUICKSTART_AZURE.md          # Quick start guide ⭐ NEW
├── AZURE_DEPLOYMENT.md          # Full deployment guide ⭐ NEW
├── DEPLOYMENT_CHECKLIST.md      # Deployment checklist ⭐ NEW
├── ARCHITECTURE.md              # Architecture diagrams ⭐ NEW
├── SETUP_SUMMARY.md             # This file ⭐ NEW
└── .github/
    └── workflows/
        └── azure-deploy.yml      # GitHub Actions workflow ⭐ NEW
```

## ✅ Setup Complete!

Your repository is now fully configured for Azure App Service deployment. Choose your preferred deployment method from the guides above and get started!

**Recommended path for beginners:**
1. Read QUICKSTART_AZURE.md
2. Deploy using Azure Portal method
3. Verify app works
4. Refer to AZURE_DEPLOYMENT.md for advanced configuration

**Recommended path for experienced users:**
1. Use Azure CLI commands from QUICKSTART_AZURE.md
2. Set up GitHub Actions for CI/CD
3. Configure Azure Files for data persistence
4. Enable Application Insights

Good luck with your deployment! 🚀
