---
name: "yaml-persistence-with-defaults"
description: "Flask/Python pattern for loading YAML config files with default fallbacks and validation"
domain: "flask-data-persistence"
confidence: "medium"
source: "earned"
---

## Context
Web applications often need to load configuration or data from YAML files that may not exist yet (first run) or may be missing keys (version migration). Returning safe defaults prevents crashes and allows graceful degradation.

## Patterns

### Basic Load with Defaults
Always provide a complete default structure that mirrors the expected schema:

```python
def load_registrations():
    """Load team registrations from YAML file."""
    path = _file_path('registrations.yaml')
    if not os.path.exists(path):
        return {'registration_open': False, 'teams': []}
    
    with open(path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
        if not data:
            return {'registration_open': False, 'teams': []}
        
        # Ensure all expected keys exist
        if 'registration_open' not in data:
            data['registration_open'] = False
        if 'teams' not in data:
            data['teams'] = []
        
        return data
```

**Key insight:** Check for file existence first, then handle empty/null YAML (returns `None`), then validate/fill missing keys. This handles: missing file, empty file, malformed YAML, and partial data.

### Merge with Defaults (for complex configs)
For dictionaries with many keys, merge loaded data with defaults instead of checking each key:

```python
def load_constraints():
    """Load constraints from YAML file, merging with defaults."""
    defaults = get_default_constraints()
    path = _file_path('constraints.yaml')
    if not os.path.exists(path):
        return defaults
    
    with open(path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
        if not data:
            return defaults
        
        # Merge: defaults provide missing keys
        for key, value in defaults.items():
            if key not in data:
                data[key] = value
        
        return data
```

**When to use:** Config files with 10+ keys where version mismatches are likely. Allows adding new keys without breaking existing deployments.

### Save Pattern
Always use UTF-8 encoding and `default_flow_style=False` for human-readable output:

```python
def save_registrations(registrations):
    """Save team registrations to YAML file."""
    with open(_file_path('registrations.yaml'), 'w', encoding='utf-8') as f:
        yaml.dump(registrations, f, default_flow_style=False)
```

**Why `default_flow_style=False`:** Produces block style (readable, git-friendly) instead of inline JSON-like style.

## Anti-Patterns

❌ **Don't assume file exists:**
```python
with open(path, 'r') as f:  # Crashes if file missing
    data = yaml.safe_load(f)
```

❌ **Don't assume yaml.safe_load returns a dict:**
```python
data = yaml.safe_load(f)
return data['key']  # Crashes if file is empty or contains null
```

❌ **Don't skip encoding on Windows:**
```python
with open(path, 'w') as f:  # May use cp1252 on Windows
    yaml.dump(data, f)
```

## When to Apply
- Loading configuration files (constraints, settings, preferences)
- Loading user-generated data files that may be incomplete
- Any YAML persistence in a Flask app where files are created/modified over time
- Multi-version deployments where schema may evolve

## Evidence
Used extensively in tournament allocator app: `load_registrations()`, `load_constraints()`, `load_results()`, `load_teams()`, `load_awards()`, `load_tournaments()` all follow this pattern. Handles first-run scenarios, empty files, and schema evolution gracefully.
