# Add New Scheduling Constraint

## Description
Add a new constraint type to the tournament scheduling system.

## Variables
- `CONSTRAINT_NAME`: The name of the new constraint (e.g., "max_games_per_day")
- `CONSTRAINT_PURPOSE`: What the constraint enforces
- `DEFAULT_VALUE`: Default value in constraints.yaml

## Workflow

### Step 1: Update Constraints Schema
Add the new constraint to `data/constraints.yaml` and `get_default_constraints()` in `src/app.py`:

```python
def get_default_constraints():
    return {
        # ... existing constraints ...
        '{{CONSTRAINT_NAME}}': {{DEFAULT_VALUE}},
    }
```

### Step 2: Add UI Control
Update `src/templates/constraints.html` to add a form field:

```html
<div class="form-group">
    <label>{{CONSTRAINT_PURPOSE}}</label>
    <input type="number" name="{{CONSTRAINT_NAME}}" 
           value="{{ constraints.{{CONSTRAINT_NAME}} }}">
</div>
```

### Step 3: Handle Form Submission
In `src/app.py`, update the `settings()` route:

```python
if action == 'update_general':
    constraints_data['{{CONSTRAINT_NAME}}'] = int(request.form.get('{{CONSTRAINT_NAME}}', {{DEFAULT_VALUE}}))
```

### Step 4: Implement in AllocationManager
In `src/core/allocation.py`, add constraint to CP-SAT model:

```python
# In allocate_teams_to_courts()
{{constraint_name}} = self.constraints.get('{{CONSTRAINT_NAME}}', {{DEFAULT_VALUE}})

# Add constraint to model
for team in all_team_names:
    # ... constraint implementation using CP-SAT ...
```

### Step 5: Add Greedy Fallback
Ensure the constraint is also handled in `_allocate_greedy()`.

### Step 6: Write Tests
Add tests in `tests/test_allocation.py`:

```python
class Test{{CONSTRAINT_NAME}}:
    def test_{{constraint_name}}_satisfied(self, ...):
        """Test constraint is satisfied when met."""
        pass
    
    def test_{{constraint_name}}_violated(self, ...):
        """Test constraint violation is detected."""
        pass
```

### Step 7: Run Tests
```bash
pytest tests/test_allocation.py -v -k "{{CONSTRAINT_NAME}}"
```
