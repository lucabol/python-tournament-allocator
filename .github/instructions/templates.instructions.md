---
applyTo: "src/templates/**/*.html"
---

# Jinja2 Templates Instructions

## Module Purpose
The `src/templates/` directory contains Jinja2 HTML templates for the Flask web application.

## Template Hierarchy

### Base Template
All templates extend `base.html`:
```html
{% extends "base.html" %}

{% block title %}Page Title{% endblock %}

{% block content %}
<!-- Page content here -->
{% endblock %}
```

### Available Templates
| Template | Purpose | Data Context |
|----------|---------|--------------|
| `base.html` | Base layout with navigation | - |
| `index.html` | Dashboard/overview | pools, courts, constraints |
| `teams.html` | Team/pool management | pools |
| `courts.html` | Court management | courts |
| `constraints.html` | Settings/constraints | constraints, all_teams, all_courts |
| `schedule.html` | Generated schedule | schedule, stats, error |
| `tracking.html` | Result tracking | schedule, results, standings |
| `sbracket.html` | Single elimination bracket | bracket_data, bracket_results |
| `dbracket.html` | Double elimination bracket | bracket_data, silver_bracket_data |
| `print.html` | Printable summary | pools, schedule, standings, bracket_data |

## Common Template Patterns

### Form with Actions
```html
<form method="POST">
    <input type="hidden" name="action" value="add_item">
    <input type="text" name="item_name" required>
    <button type="submit">Add</button>
</form>
```

### Flash Messages
```html
{% with messages = get_flashed_messages(with_categories=true) %}
    {% if messages %}
        {% for category, message in messages %}
            <div class="alert alert-{{ category }}">{{ message }}</div>
        {% endfor %}
    {% endif %}
{% endwith %}
```

### Iterating Over Schedule
```html
{% for day, day_data in schedule.items() %}
    {% if day != '_time_slots' %}
        <h3>{{ day }}</h3>
        {% for time_slot in day_data['_time_slots'] %}
            <div class="time-row">
                <span>{{ time_slot }}</span>
                {% for court_name, court_data in day_data.items() %}
                    {% if court_name != '_time_slots' %}
                        {% set match = court_data.time_to_match.get(time_slot) %}
                        {% if match %}
                            <div class="match">
                                {{ match.teams[0] }} vs {{ match.teams[1] }}
                            </div>
                        {% endif %}
                    {% endif %}
                {% endfor %}
            </div>
        {% endfor %}
    {% endif %}
{% endfor %}
```

### Conditional Styling for Standings
```html
{% for i, team_data in enumerate(standings[pool_name]) %}
    <tr class="{% if i < team_data.advance_count %}advancing{% endif %}">
        <td>{{ i + 1 }}</td>
        <td>{{ team_data.team }}</td>
        <td>{{ team_data.wins }}-{{ team_data.losses }}</td>
    </tr>
{% endfor %}
```

## Data Structures in Templates

### Schedule Structure
```python
schedule = {
    'Day 1': {
        '_time_slots': ['09:00', '09:30', '10:00', ...],
        'Court 1': {
            'matches': [...],
            'time_to_match': {'09:00': match_obj, ...}
        },
        'Court 2': {...}
    },
    'Bracket Phase': {...}
}
```

### Match Object
```python
match = {
    'teams': ['Team A', 'Team B'],
    'start_time': '09:00',
    'end_time': '09:30',
    'day': 'Day 1',
    'pool': 'Pool A',  # or bracket phase name
    'is_bracket': False,
    'is_placeholder': False,
    'match_code': 'W1-M1',  # for bracket matches
    'result': {  # if results are enriched
        'winner': 'Team A',
        'loser': 'Team B',
        'sets': [[21, 15]],
        'completed': True
    }
}
```

### Bracket Data Structure
```python
bracket_data = {
    'winners_bracket': {
        'Quarterfinal': [
            {'teams': ['A', 'B'], 'match_number': 1, 'is_playable': True},
            ...
        ],
        'Semifinal': [...],
        'Final': [...]
    },
    'losers_bracket': {...},
    'grand_final': {'teams': [...], 'is_playable': False},
    'bracket_reset': {'teams': [...], 'needs_reset': False}
}
```

## CSS Classes (from style.css)
- `.advancing` - Teams advancing from pool
- `.completed` - Completed matches
- `.placeholder` - Unresolved bracket teams
- `.alert-success`, `.alert-error` - Flash messages
- `.match-result` - Score display
