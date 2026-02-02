# Tournament Allocator

A Flask web application designed to allocate teams to courts for beach volleyball tournaments. Supports pool play, single elimination, and double elimination brackets with constraint-based scheduling using Google OR-Tools.

## Project Structure

```
python-tournament-allocator
├── src
│   ├── main.py               # Entry point of the application
│   └── core
│       ├── __init__.py       # Initializes the core module
│       ├── allocation.py      # Manages allocation of teams to courts
│       ├── formats.py         # Defines tournament formats
│       └── models.py          # Data models for teams, courts, and constraints
├── data
│   ├── teams.csv             # Definitions of participating teams
│   ├── courts.csv            # Definitions of available courts
│   └── constraints.json       # Allocation constraints in JSON format
├── requirements.txt           # Project dependencies
└── README.md                  # Project documentation
```

## Setup Instructions

1. **Clone the repository**:
   ```
   git clone <repository-url>
   cd python-tournament-allocator
   ```

2. **Install dependencies**:
   Ensure you have Python installed, then run:
   ```
   pip install -r requirements.txt
   ```

3. **Prepare data files**:
   - Populate `data/teams.csv` with the names and attributes of the teams.
   - Populate `data/courts.csv` with the names and start times of the courts.
   - Define allocation constraints in `data/constraints.json`.

## Running the Application

### Local Development
To run the Flask web application locally:
```bash
cd src
python app.py
```

The application will be available at `http://localhost:5000`

### Production Deployment to Azure

**🚀 New! Complete Azure App Service setup included!**

This repository is fully configured for Azure App Service deployment. Choose your path:

#### For First-Time Users (Easiest)
1. Read **[QUICKSTART_AZURE.md](QUICKSTART_AZURE.md)** - Deploy in 10 minutes via Azure Portal
2. Follow the 3-step process to get your app live

#### For Detailed Setup
- **[AZURE_DEPLOYMENT.md](AZURE_DEPLOYMENT.md)** - Comprehensive guide with 3 deployment methods
- **[DEPLOYMENT_CHECKLIST.md](DEPLOYMENT_CHECKLIST.md)** - Step-by-step checklist
- **[ARCHITECTURE.md](ARCHITECTURE.md)** - Technical architecture and diagrams
- **[SETUP_SUMMARY.md](SETUP_SUMMARY.md)** - Complete overview

**What's Included:**
- ✅ Production-ready startup script (`startup.sh`)
- ✅ Gunicorn WSGI server configuration
- ✅ GitHub Actions CI/CD workflow
- ✅ Azure build configuration
- ✅ Environment template (`.env.example`)
- ✅ 1,500+ lines of documentation

**Pricing:** Starting at $0/month (Free tier) or $13/month (Basic tier - recommended)

#### Other Deployment Options
- Azure Container Apps
- Docker containers  
- Any Python-capable hosting platform

## Overview of Tournament Allocation Process

The allocation process involves:
- Reading team and court data from CSV files.
- Applying constraints defined in the JSON file.
- Allocating teams to courts based on the selected tournament format (pool play or single elimination).
- Outputting the results of the allocation.

This project aims to streamline the organization of tournaments, making it easier for organizers to manage teams and courts effectively.