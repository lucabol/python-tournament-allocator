---
applyTo: "tests/**/*.py"
---

# Test Suite Instructions

## Module Purpose
The `tests/` directory contains the pytest test suite for validating tournament allocation logic, Flask routes, and bracket generation.

## Source of Truth Files
- [tests/conftest.py](../../tests/conftest.py) - Shared fixtures
- [tests/test_allocation.py](../../tests/test_allocation.py) - Reference test structure

## Test Organization

### File Naming
| Test File | Tests For |
|-----------|-----------|
| `test_allocation.py` | `AllocationManager` scheduling logic |
| `test_app.py` | Flask routes and API endpoints |
| `test_elimination.py` | Single elimination bracket |
| `test_double_elimination.py` | Double elimination bracket |
| `test_generate_matches.py` | Match generation utilities |
| `test_models.py` | Data model behavior |
| `test_integration.py` | End-to-end workflows |

### Class Naming Convention
```python
class TestFeatureName:
    """Tests for specific feature or component."""
    
    def test_specific_behavior(self, fixture1, fixture2):
        """Test description of expected behavior."""
        pass
```

## Available Fixtures

### From `conftest.py`
```python
@pytest.fixture
def sample_teams():
    """5 teams in 2 pools."""
    return [
        Team(name="Team A", attributes={"pool": "pool1"}),
        Team(name="Team B", attributes={"pool": "pool1"}),
        # ...
    ]

@pytest.fixture
def sample_courts():
    """2 courts starting at 08:00."""
    return [
        Court(name="Court 1", start_time="08:00"),
        Court(name="Court 2", start_time="08:00"),
    ]

@pytest.fixture
def basic_constraints():
    """Standard tournament constraints."""
    return {
        "match_duration_minutes": 60,
        "min_break_between_matches_minutes": 15,
        # ...
    }

@pytest.fixture
def constraints_with_team_preferences():
    """Constraints with play_after/play_before for specific teams."""
    pass

@pytest.fixture
def large_tournament_teams():
    """12 teams across 3 pools."""
    pass

@pytest.fixture
def tight_constraints():
    """Constraints that stress scheduling (short day, long breaks)."""
    pass
```

## Testing Patterns

### Testing Constraint Violations
```python
def test_constraint_violated(self, sample_teams, sample_courts, basic_constraints):
    """Test that constraint violation is detected."""
    manager = AllocationManager(sample_teams, sample_courts, basic_constraints)
    
    # Setup: schedule a conflicting match
    base_date = datetime.date.today()
    existing_start = datetime.datetime.combine(base_date, datetime.time(9, 0))
    existing_end = datetime.datetime.combine(base_date, datetime.time(10, 0))
    manager.schedule["Court 1"].append((1, existing_start, existing_end, ("Team A", "Team B")))
    
    # Verify constraint is violated
    new_start = datetime.datetime.combine(base_date, datetime.time(9, 30))
    assert manager._check_team_constraints(("Team A", "Team C"), new_start) is False
```

### Testing Flask Routes
```python
def test_api_endpoint(self, client):
    """Test API endpoint returns expected response."""
    response = client.post('/api/endpoint', 
        json={'key': 'value'},
        content_type='application/json')
    
    assert response.status_code == 200
    data = response.get_json()
    assert data['success'] is True
```

### Testing Bracket Generation
```python
def test_bracket_seeding(self):
    """Test teams are seeded correctly from pool standings."""
    pools = {
        'Pool A': {'teams': ['A1', 'A2'], 'advance': 2},
        'Pool B': {'teams': ['B1', 'B2'], 'advance': 2}
    }
    standings = {...}  # Mock standings
    
    seeded = seed_teams_from_pools(pools, standings)
    
    # Verify seeding order: 1st places first, then 2nd places
    assert seeded[0][0] == 'A1'  # #1 from Pool A
    assert seeded[1][0] == 'B1'  # #1 from Pool B
    assert seeded[2][0] == 'A2'  # #2 from Pool A
    assert seeded[3][0] == 'B2'  # #2 from Pool B
```

## Running Tests

```bash
# All tests with verbose output
pytest tests/ -v

# Specific test file
pytest tests/test_allocation.py -v

# Specific test class
pytest tests/ -v -k "TestCourtAvailability"

# Specific test method
pytest tests/ -v -k "test_court_available_empty_schedule"

# With coverage
pytest tests/ --cov=src --cov-report=html

# Stop on first failure
pytest tests/ -x
```

## Test Data Conventions
- Use `datetime.date.today()` for base dates
- Standard match duration: 60 minutes
- Standard court times: "08:00" to "22:00"
- Standard break: 15 minutes
