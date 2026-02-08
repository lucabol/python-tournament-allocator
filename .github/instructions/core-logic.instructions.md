---
applyTo: "src/core/**/*.py"
---

# Core Business Logic Module

## Module Purpose
The `src/core/` directory contains the domain logic for tournament management, including scheduling algorithms, bracket generation, and data models.

## Source of Truth Files
- [src/core/models.py](../../src/core/models.py) - All data models
- [src/core/allocation.py](../../src/core/allocation.py) - Scheduling algorithm
- [tests/conftest.py](../../tests/conftest.py) - Test fixtures

## Data Models

### Team Model
```python
class Team:
    def __init__(self, name: str, attributes: dict = None):
        self.name = name
        self.attributes = attributes if attributes else {}  # Must include 'pool' key
```

### Court Model
```python
class Court:
    def __init__(self, name: str, start_time: str, end_time: str = None):
        self.name = name
        self.start_time = start_time  # Format: "HH:MM"
        self.end_time = end_time      # Optional, allows midnight crossing
        self.matches = []
```

## Scheduling Algorithm Patterns

### CP-SAT Model Structure
When modifying `AllocationManager`:
1. **Decision Variables**: Use `model.NewIntVar()` for positions, `model.NewBoolVar()` for presence
2. **Interval Variables**: Use `model.NewOptionalIntervalVar()` for time-based scheduling
3. **Constraints**: Add via `model.Add()` with `.OnlyEnforceIf()` for conditional constraints
4. **No-Overlap**: Use `model.AddNoOverlap(intervals_list)` for resource constraints

### Time Handling
- All times are strings in "HH:MM" format
- Use `_parse_time()` to convert to `datetime.time`
- Handle midnight crossing: if `end_time <= start_time`, add 24 hours
- Slot-based scheduling uses 5-minute increments by default

### Greedy Fallback
Always implement a greedy fallback when CP-SAT may fail:
```python
if status not in [cp_model.OPTIMAL, cp_model.FEASIBLE]:
    self._allocate_greedy(matches, ...)
```

## Bracket Generation Rules

### Seeding Order
1. All 1st place teams from each pool (sorted alphabetically by pool name)
2. All 2nd place teams from each pool  
3. Continue for each finishing position

### Placeholder Teams
Use format `"#N Pool X"` for teams before standings are finalized:
```python
team_name = f"#{position} {pool_name}"  # e.g., "#1 Pool A"
```

### Bye Handling
- Calculate: `byes = 2^(ceil(log2(num_teams))) - num_teams`
- Assign byes to top seeds first
- Mark bye matches with `is_bye: True`

## Testing Requirements
- Test all helper methods independently (`_parse_time`, `_check_court_availability`)
- Use `conftest.py` fixtures: `sample_teams`, `sample_courts`, `basic_constraints`
- Test constraint violations explicitly
- Test edge cases: midnight crossing, empty schedules, single-team pools
