# Tournament Allocator

This project is designed to allocate teams to courts for a tournament, supporting both pool play and single elimination formats. It provides a structured way to manage tournament logistics, ensuring that teams are allocated to courts according to specified constraints.

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
python src/app.py
```

The application will be available at `http://localhost:5000`.

### Docker

To run the application in a Docker container:
```bash
docker build -t tournament-allocator .
docker run -p 8080:8080 tournament-allocator
```

The application will be available at `http://localhost:8080`.

## Overview of Tournament Allocation Process

The allocation process involves:
- Reading team and court data from CSV files.
- Applying constraints defined in the JSON file.
- Allocating teams to courts based on the selected tournament format (pool play or single elimination).
- Outputting the results of the allocation.

This project aims to streamline the organization of tournaments, making it easier for organizers to manage teams and courts effectively.

## Deployment

### Azure Container Apps

For detailed instructions on deploying this application to Azure Container Apps, see [DEPLOYMENT.md](DEPLOYMENT.md).

Quick deployment:
```bash
# Make the script executable (first time only)
chmod +x deploy-azure.sh

# Run the deployment script
./deploy-azure.sh
```

The script will:
- Create an Azure resource group
- Set up a Container Apps environment
- Build and deploy your application
- Provide you with the URL to access your app

For manual deployment or advanced options, refer to the [DEPLOYMENT.md](DEPLOYMENT.md) guide.