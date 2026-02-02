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

### Production Deployment
See deployment guides:
- **[Azure App Service - Quick Start](QUICKSTART_AZURE.md)** - Get started in 10 minutes
- **[Azure App Service - Full Guide](AZURE_DEPLOYMENT.md)** - Complete deployment documentation

Other deployment options:
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