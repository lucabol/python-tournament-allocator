---
applyTo: "src/app.py"
---

# Flask Application Module

## Module Purpose
The main Flask application containing all HTTP routes, API endpoints, and view rendering logic.

## Source of Truth Files
- [src/app.py](../../src/app.py) - All routes and API endpoints
- [data/constraints.yaml](../../data/constraints.yaml) - Default constraint values

## Route Naming Conventions

### Page Routes
- Return `render_template()` with HTML template
- Accept both GET and POST methods for forms
- Use `flash()` for user feedback messages
```python
@app.route('/teams', methods=['GET', 'POST'])
def teams():
    if request.method == 'POST':
        # Handle form submission
        flash('Action completed successfully.', 'success')
        return redirect(url_for('teams'))
    return render_template('teams.html', ...)
```

### API Routes
- Prefix with `/api/`
- Always return `jsonify()` responses
- Include success flag and data
```python
@app.route('/api/resource', methods=['POST'])
def api_resource():
    data = request.get_json()
    # Process...
    return jsonify({'success': True, 'result': data})
```

## Data Loading Functions

### Pattern: Load with Defaults
```python
def load_resource():
    """Load resource from file, returning defaults if missing."""
    defaults = {'key': 'default_value'}
    if not os.path.exists(RESOURCE_FILE):
        return defaults
    with open(RESOURCE_FILE, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
        if not data:
            return defaults
        return {**defaults, **data}  # Merge with defaults
```

### Saving Functions
- Always specify `encoding='utf-8'`
- Use `yaml.dump()` with `default_flow_style=False` for readable output
- For CSV, use `newline=''` on Windows

## State Management

### Important Data Files
| File | Format | Purpose |
|------|--------|---------|
| `teams.yaml` | YAML | Pool definitions with team lists |
| `courts.csv` | CSV | Court availability |
| `constraints.yaml` | YAML | Tournament settings |
| `results.yaml` | YAML | Match scores and outcomes |
| `schedule.yaml` | YAML | Generated schedule |

### Match Key Generation
```python
def get_match_key(team1: str, team2: str, pool: str = None) -> str:
    """Generate unique key - teams sorted alphabetically."""
    teams_sorted = sorted([team1, team2])
    key = f"{teams_sorted[0]}_vs_{teams_sorted[1]}"
    if pool:
        key += f"_{pool}"
    return key
```

## Constraints Schema
```yaml
match_duration_minutes: 30
days_number: 1
min_break_between_matches_minutes: 0
day_end_time_limit: "02:00"
bracket_type: "double"  # or "single"
scoring_format: "single_set"  # or "best_of_3"
pool_in_same_court: true
silver_bracket_enabled: true
pool_to_bracket_delay_minutes: 0
team_specific_constraints:
  - team_name: "Team A"
    play_after: "10:00"
    play_before: "18:00"
    note: "Optional note"
```

## Common Patterns

### Form Action Handling
```python
if request.method == 'POST':
    action = request.form.get('action')
    
    if action == 'add_item':
        # Handle add
        pass
    elif action == 'delete_item':
        # Handle delete
        pass
    elif action == 'edit_item':
        # Handle edit
        pass
    
    return redirect(url_for('current_page'))
```

### Schedule Enrichment
When displaying schedule with live results:
1. Load saved schedule with `load_schedule()`
2. Load results with `load_results()`
3. Call `enrich_schedule_with_results()` to resolve placeholders
4. Calculate standings with `calculate_pool_standings()`
