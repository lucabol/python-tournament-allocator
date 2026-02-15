# Tournament Allocator

A web application for organizing sports tournaments. Handles pool play, single/double elimination brackets, court allocation with constraint-based scheduling, match result tracking, and public live pages.

## Features

- Multi-user authentication with per-user tournament management
- Pool play with configurable team pools
- Single and double elimination brackets with seeding
- Constraint-based court scheduling (OR-Tools CP-SAT solver)
- Live match result tracking with automatic standings
- Public shareable live page for spectators
- Print-friendly tournament views
- Export/import at tournament, user, and site levels
- Admin site backup/restore for platform migration

## Tech Stack

- **Python 3.11+**
- **Flask** — web framework
- **OR-Tools** — constraint-based scheduling via CP-SAT solver
- **pandas, numpy** — data processing
- **PyYAML 6.0.1** — configuration
- **jsonschema** — data validation
- **filelock** — concurrent file access
- **Gunicorn** — production WSGI server

## Project Structure

```
src/
├── app.py                    # Flask application (routes, API endpoints, auth)
├── generate_matches.py       # Match generation utilities
├── allocate_matches.py       # CLI allocation tool
├── core/
│   ├── models.py             # Data models: Team, Court, Constraint
│   ├── allocation.py         # AllocationManager (OR-Tools CP-SAT)
│   ├── elimination.py        # Single elimination bracket logic
│   ├── double_elimination.py # Double elimination bracket logic
│   └── formats.py            # Tournament format definitions
├── templates/                # Jinja2 HTML templates
└── static/                   # CSS stylesheets
data/                         # Tournament data (YAML/CSV, created at runtime)
tests/                        # pytest test suite
```

## Getting Started

```bash
git clone <repository-url>
cd python-tournament-allocator
pip install -r requirements.txt
cd src && python -m flask run --debug
```

Open http://127.0.0.1:5000, register an account, and create a tournament.

## Running Tests

```bash
pytest tests/ -v
pytest tests/ --cov=src --cov-report=html  # with coverage
```

## Deployment

Deploy to Azure App Service:

**Prerequisites:** Azure CLI logged in, `.env` file with `AZURE_SUBSCRIPTION_ID`.

Optional `.env` variables: `AZURE_RESOURCE_GROUP`, `AZURE_LOCATION`, `AZURE_APP_NAME`, `AZURE_APP_SERVICE_PLAN`, `AZURE_APP_SERVICE_SKU`.

```bash
.\deploy.ps1
```

The script handles resource creation, zip deployment with retry, and configuration. Production uses Gunicorn via `startup.sh`. Data persists in `/home/data` on Azure (outside wwwroot).

**Security**: The deployment script auto-generates an `ADMIN_API_KEY` for backup/restore operations if not already set. This key is stored in Azure App Settings and written to the local `.env` file.

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `AZURE_SUBSCRIPTION_ID` | Yes (deploy) | — | Azure subscription for deployment |
| `TOURNAMENT_DATA_DIR` | No | `./data` | Directory for tournament data files |
| `SECRET_KEY` | No | Auto-generated | Flask session signing key |
| `ADMIN_API_KEY` | No (deploy auto-generates) | — | API key for backup/restore operations |

## Backup & Restore

For Azure deployments, use HTTP-based scripts to backup and restore tournament data:

```bash
# Backup to local ZIP
python scripts/backup.py

# Restore from backup
python scripts/restore.py path/to/backup.zip
```

No Azure CLI installation required. The scripts use HTTP API routes with API key authentication. The API key is auto-generated during deployment.

See [docs/BACKUP_RESTORE.md](docs/BACKUP_RESTORE.md) for detailed usage, security notes, automation examples (scheduled backups, CI/CD), and disaster recovery procedures.

## Documentation

See [USER_GUIDE.md](USER_GUIDE.md) for a complete walkthrough of all features.

## License

See LICENSE file.