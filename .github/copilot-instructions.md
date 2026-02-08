# Tournament Allocator - AI Copilot Instructions

## Project Overview
This is a **Python Flask web application** for tournament scheduling and management. It handles pool play, single/double elimination brackets, court allocation, and match result tracking for sports tournaments.

## Tech Stack (Exact Versions)
- **Python**: 3.11+
- **Framework**: Flask (latest)
- **Data Processing**: pandas, numpy
- **Constraint Solving**: ortools (OR-Tools CP-SAT solver) >= 9.0
- **Data Validation**: jsonschema
- **Configuration**: PyYAML 6.0.1
- **Testing**: pytest >= 7.0.0, pytest-cov >= 4.0.0
- **Deployment**: Azure App Service with Gunicorn

## Project Structure
```
src/
├── app.py                 # Main Flask application (routes, API endpoints)
├── generate_matches.py    # Match generation utilities
├── allocate_matches.py    # CLI tool for allocation
├── core/                  # Core business logic
│   ├── models.py          # Data models: Team, Court, Constraint
│   ├── allocation.py      # AllocationManager with OR-Tools CP-SAT
│   ├── elimination.py     # Single elimination bracket logic
│   ├── double_elimination.py  # Double elimination bracket logic
│   └── formats.py         # Tournament format definitions
├── templates/             # Jinja2 HTML templates
└── static/                # CSS stylesheets

data/                      # YAML/CSV tournament data files
tests/                     # pytest test suite
```

## Golden Rules

### 1. Data Model Conventions
- **Team**: Always has `name` and `attributes` dict (must include `pool` key)
- **Court**: Has `name`, `start_time`, and optional `end_time`
- **Pools data format**: Dict of `{pool_name: {'teams': [...], 'advance': int}}`

### 2. Code Style
- Use type hints for all function signatures
- Docstrings required for public functions (Google style)
- Class names: PascalCase (`AllocationManager`, `Team`)
- Functions/variables: snake_case (`generate_pool_play_matches`, `match_duration`)
- Constants in UPPER_CASE (`DATA_DIR`, `TEAMS_FILE`)

### 3. Flask Routes
- Use `@app.route` decorators with explicit methods
- API endpoints return `jsonify()` responses
- Use `flash()` for user feedback on form submissions
- Always redirect after POST to prevent resubmission

### 4. Constraint Programming (OR-Tools)
- Use `cp_model.CpModel()` for scheduling optimization
- Prefer interval variables for match scheduling
- Always include timeout (`max_time_in_seconds = 60.0`)
- Fall back to greedy algorithm if CP-SAT fails

### 5. Testing
- Tests live in `tests/` directory
- Use fixtures from `conftest.py` (`sample_teams`, `sample_courts`, `basic_constraints`)
- Test class naming: `Test{FeatureName}` (e.g., `TestCourtAvailability`)
- Run with: `pytest tests/ -v`

### 6. Data Files
- Teams: YAML format with pools structure
- Courts: CSV with `court_name,start_time,end_time`
- Constraints: YAML with tournament settings
- Results: YAML persisted in `data/results.yaml`

### 7. Error Handling
- Wrap file operations in try/except
- Return sensible defaults for missing data files
- Log warnings for non-critical issues (e.g., missing teams)

## Key Algorithms

### Match Scheduling (CP-SAT)
The `AllocationManager.allocate_teams_to_courts()` method:
1. Creates decision variables for (match, court, day, slot) assignments
2. Adds constraints: no overlap on courts, team availability, minimum breaks
3. Objective: minimize makespan, then maximize team rest time
4. Falls back to greedy if no solution found

### Bracket Generation
- `seed_teams_from_pools()`: Seeds by pool finish position (1st places first)
- `calculate_bracket_size()`: Rounds to next power of 2
- Handles byes for non-power-of-2 team counts

## Common Development Tasks

### Adding a New API Endpoint
```python
@app.route('/api/new-endpoint', methods=['POST'])
def api_new_endpoint():
    """Description of what this endpoint does."""
    data = request.get_json()
    # Process data
    return jsonify({'success': True, 'result': ...})
```

### Adding a New Model
Add to `src/core/models.py`:
```python
class NewModel:
    def __init__(self, name, **kwargs):
        self.name = name
        # Initialize attributes
    
    def __repr__(self):
        return f"NewModel(name={self.name})"
```

### Running the Application
```bash
# Development
cd src && python -m flask run --debug

# Production (Azure)
./deploy.ps1
```

### Running Tests
```bash
pytest tests/ -v                    # All tests
pytest tests/test_allocation.py -v  # Specific file
pytest tests/ -v -k "TestCourtAvailability"  # By class
```

## Deployment
- Target: Azure App Service (Linux, Python 3.11)
- Script: `deploy.ps1`
- Startup: `gunicorn --bind=0.0.0.0:8000 --chdir /home/site/wwwroot/src app:app`
- Requires: `.env` file with `AZURE_SUBSCRIPTION_ID`
