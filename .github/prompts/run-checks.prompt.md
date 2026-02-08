# Run Development Checks

## Description
Run all quality checks before committing code.

## Quick Commands

### Run All Tests
```powershell
pytest tests/ -v
```

### Run Tests with Coverage
```powershell
pytest tests/ --cov=src --cov-report=html
# Open htmlcov/index.html to view report
```

### Run Specific Test File
```powershell
pytest tests/test_allocation.py -v
```

### Run Tests Matching Pattern
```powershell
pytest tests/ -v -k "TestCourtAvailability"
```

### Run Development Server
```powershell
cd src
python -m flask run --debug
# Access at http://127.0.0.1:5000
```

### Validate YAML Data Files
```powershell
python -c "import yaml; yaml.safe_load(open('data/teams.yaml'))"
python -c "import yaml; yaml.safe_load(open('data/constraints.yaml'))"
```

### Load Test Data
```powershell
# Via API (server must be running)
curl -X POST http://127.0.0.1:5000/api/test-data
```

### Generate Test Schedule
1. Start the dev server: `cd src && python -m flask run --debug`
2. Load test data: POST to `/api/test-data`
3. Generate schedule: POST to `/schedule`
4. Generate random results: POST to `/api/generate-random-results`

## Pre-Commit Checklist

1. [ ] All tests pass: `pytest tests/ -v`
2. [ ] No import errors: `python -c "from src.app import app"`
3. [ ] Server starts: `cd src && python -m flask run`
4. [ ] New features have tests
5. [ ] YAML files are valid

## Common Issues

### Import Errors
Add src to Python path:
```python
import sys
sys.path.insert(0, 'src')
```

### Database/File Not Found
Check working directory - should be project root, not `src/`.

### OR-Tools Timeout
If CP-SAT takes too long:
- Reduce `max_time_in_seconds` in allocation.py
- Check for conflicting constraints
- Verify greedy fallback works

### Template Not Found
Ensure Flask templates folder is configured:
```python
app = Flask(__name__)  # Uses default templates/ folder
```
