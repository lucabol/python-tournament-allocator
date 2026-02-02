# Azure App Service Architecture

## Deployment Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         GitHub Repository                        │
│                  lucabol/python-tournament-allocator            │
│                                                                  │
│  ┌────────────────────────────────────────────────────────┐   │
│  │  Code Files:                                            │   │
│  │  • src/app.py (Flask application)                      │   │
│  │  • requirements.txt (dependencies)                      │   │
│  │  • startup.sh (App Service startup script)            │   │
│  │  • .deployment (build configuration)                   │   │
│  └────────────────────────────────────────────────────────┘   │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                            │ Automated Deployment
                            │ (GitHub Integration or GitHub Actions)
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Azure App Service (Linux)                     │
│                                                                  │
│  ┌──────────────────────────────────────────────────────┐     │
│  │  Python 3.11 Runtime Container                       │     │
│  │  ┌────────────────────────────────────────────┐     │     │
│  │  │                                             │     │     │
│  │  │  gunicorn --workers=4 app:app              │     │     │
│  │  │  ├─ Flask App (port 8000)                  │     │     │
│  │  │  │  ├─ /teams                              │     │     │
│  │  │  │  ├─ /courts                             │     │     │
│  │  │  │  ├─ /schedule                           │     │     │
│  │  │  │  ├─ /dbracket                           │     │     │
│  │  │  │  └─ /print                              │     │     │
│  │  │  │                                          │     │     │
│  │  │  └─ OR-Tools Constraint Solver             │     │     │
│  │  │                                             │     │     │
│  │  └────────────────────────────────────────────┘     │     │
│  │                                                       │     │
│  │  Ephemeral Storage: /home/site/wwwroot/              │     │
│  │  ├─ src/ (application code)                         │     │
│  │  └─ data/ (⚠️ temporary - see persistence options)  │     │
│  │                                                       │     │
│  └───────────────────────────────────────────────────────┘     │
│                                                                  │
│  Configuration:                                                 │
│  • Startup Command: ./startup.sh                               │
│  • Environment: FLASK_ENV=production                           │
│  • App Settings: SECRET_KEY, etc.                              │
│                                                                  │
└──────────────────────┬───────────────────────────────────────────┘
                       │
                       │ HTTPS
                       ▼
            https://<app-name>.azurewebsites.net
                       │
                       │
                       ▼
                  ┌─────────┐
                  │ Users   │
                  └─────────┘
```

## Optional: Persistent Storage Architecture

For production deployments, add persistent storage:

```
┌─────────────────────────────────────────────────────────────────┐
│                    Azure App Service (Linux)                     │
│                                                                  │
│  ┌──────────────────────────────────────────────────────┐     │
│  │  Python Container                                    │     │
│  │  ├─ Flask App (gunicorn)                            │     │
│  │  └─ /home/site/wwwroot/data/ ───────┐              │     │
│  └──────────────────────────────────────│───────────────┘     │
└─────────────────────────────────────────│───────────────────────┘
                                          │
                                          │ Azure Files Mount
                                          │ (persistent across restarts)
                                          ▼
                            ┌──────────────────────────┐
                            │  Azure Storage Account   │
                            │  ┌────────────────────┐ │
                            │  │  File Share        │ │
                            │  │  ├─ teams.yaml     │ │
                            │  │  ├─ courts.csv     │ │
                            │  │  ├─ constraints.yaml│ │
                            │  │  ├─ results.yaml   │ │
                            │  │  └─ schedule.yaml  │ │
                            │  └────────────────────┘ │
                            └──────────────────────────┘
```

## Deployment Flow

### Initial Setup
```
Developer                Azure Portal/CLI              Azure
   │                            │                        │
   │  1. Create Resources       │                        │
   │  ──────────────────────────>                        │
   │                            │  2. Provision          │
   │                            │  ───────────────────>  │
   │                            │                        │
   │  3. Configure Deployment   │                        │
   │  ──────────────────────────>                        │
   │                            │  4. Link GitHub        │
   │                            │  ───────────────────>  │
   │                            │                        │
   │  5. Set Startup Command    │                        │
   │  ──────────────────────────>                        │
   │                            │                        │
```

### Continuous Deployment
```
Developer            GitHub              Azure App Service
   │                   │                        │
   │  1. git push      │                        │
   │  ────────────────>│                        │
   │                   │  2. Webhook triggers   │
   │                   │  ─────────────────────>│
   │                   │                        │
   │                   │  3. Pull code          │
   │                   │<───────────────────────│
   │                   │                        │
   │                   │  4. Build              │
   │                   │  (pip install)         │
   │                   │                        │
   │                   │  5. Deploy & Restart   │
   │                   │                        │
   │                   │  6. Health Check       │
   │                   │  (startup.sh runs)     │
   │                   │                        │
   │  7. App live at   │                        │
   │  <──────────────────────────────────────── │
   │  https://app.azurewebsites.net             │
   │                                             │
```

## Key Components

### 1. Runtime Environment
- **OS**: Linux (Ubuntu-based)
- **Python**: 3.11
- **Web Server**: Gunicorn with 4 workers
- **Port**: 8000 (Azure internal)

### 2. Application Structure
```
/home/site/wwwroot/          (App Service root)
├── src/
│   ├── app.py               (Flask application entry point)
│   └── core/                (Business logic)
├── data/                    (Data files - ephemeral by default)
│   ├── teams.yaml
│   ├── courts.csv
│   ├── constraints.yaml
│   ├── results.yaml
│   └── schedule.yaml
├── requirements.txt         (Python dependencies)
├── startup.sh              (Startup script)
└── .deployment             (Build configuration)
```

### 3. Dependencies (~200MB)
- Flask (lightweight web framework)
- ortools (~100MB - constraint solver)
- pandas, numpy (data processing)
- PyYAML (configuration files)
- gunicorn (production WSGI server)

### 4. Pricing Tiers

| Tier | Cost/Month | CPU | RAM | Use Case |
|------|-----------|-----|-----|----------|
| F1 (Free) | $0 | Shared | 1GB | Testing only, slow |
| B1 (Basic) | ~$13 | 1 vCPU | 1.75GB | Development, small prod |
| B2 (Basic) | ~$26 | 2 vCPU | 3.5GB | Medium production |
| S1 (Standard) | ~$70 | 1 vCPU | 1.75GB | Auto-scale, staging slots |
| P1V2 (Premium) | ~$100 | 1 vCPU | 3.5GB | High performance |

### 5. Security Features
- HTTPS enforced (automatic SSL certificate)
- Azure Active Directory integration (optional)
- Managed identities for Azure resources
- Network isolation with VNet integration (Premium tier)
- IP restrictions support

## Monitoring & Diagnostics

```
Azure App Service
       │
       ├─> Application Logs ──> Log Stream (real-time)
       │                     └─> Blob Storage (archive)
       │
       ├─> Metrics ──────────> Azure Monitor
       │                     ├─ CPU Usage
       │                     ├─ Memory Usage
       │                     ├─ Response Time
       │                     └─ HTTP Status Codes
       │
       └─> Application Insights (optional)
                             ├─ Performance Monitoring
                             ├─ Exception Tracking
                             ├─ User Analytics
                             └─ Distributed Tracing
```

## Scaling Options

### Vertical Scaling (Scale Up)
- Change pricing tier
- More CPU/Memory
- Immediate effect
- Downtime: None

### Horizontal Scaling (Scale Out)
- Add more instances (Standard tier+)
- Load balanced automatically
- Can be automated based on:
  - CPU percentage
  - Memory percentage
  - HTTP queue length
  - Custom metrics

## Disaster Recovery

### Backup Strategy
1. **Code**: Stored in GitHub (version controlled)
2. **Data**: Requires Azure Files or Database backup
3. **Configuration**: Document in environment setup

### Recovery Options
- Redeploy from GitHub (code)
- Restore from Azure Files snapshots (data)
- Deploy to different region for geo-redundancy

## Best Practices

1. **Always use Basic (B1) or higher for production**
   - Free tier is too limited for ortools
   
2. **Enable "Always On"**
   - Prevents cold starts
   - Available in Basic tier and above
   
3. **Use persistent storage for production**
   - Azure Files mount recommended
   - Or migrate to Azure SQL Database
   
4. **Monitor performance**
   - Enable Application Insights
   - Set up alerts for errors and performance issues
   
5. **Secure your application**
   - Set strong SECRET_KEY
   - Enable HTTPS only
   - Consider authentication for production

6. **Automate deployments**
   - Use GitHub integration or GitHub Actions
   - Test in staging before production (Standard tier)

## Cost Optimization

- **Development**: Use B1, stop when not in use
- **Testing**: Use F1 (free) for quick tests
- **Production**: Use B2 or S1, enable auto-scale
- **Off-hours**: Scale down or stop non-production environments

## Further Reading

- [App Service Documentation](https://docs.microsoft.com/azure/app-service/)
- [Python on Azure Guide](https://docs.microsoft.com/azure/app-service/quickstart-python)
- [App Service Pricing](https://azure.microsoft.com/pricing/details/app-service/linux/)
