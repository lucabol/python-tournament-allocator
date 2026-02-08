# Add New Tournament Page

## Description
Add a new page/view to the tournament management application.

## Variables
- `PAGE_NAME`: Route name and template (e.g., "statistics")
- `PAGE_TITLE`: Display title (e.g., "Tournament Statistics")
- `PAGE_PURPOSE`: What the page displays/does

## Workflow

### Step 1: Create Template
Create `src/templates/{{page_name}}.html`:

```html
{% extends "base.html" %}

{% block title %}{{PAGE_TITLE}}{% endblock %}

{% block content %}
<div class="container">
    <h1>{{PAGE_TITLE}}</h1>
    
    {% with messages = get_flashed_messages(with_categories=true) %}
        {% if messages %}
            {% for category, message in messages %}
                <div class="alert alert-{{ category }}">{{ message }}</div>
            {% endfor %}
        {% endif %}
    {% endwith %}
    
    <!-- Page content -->
    <div class="content">
        {% if data %}
            <!-- Display data -->
        {% else %}
            <p>No data available.</p>
        {% endif %}
    </div>
    
    {% if has_form %}
    <form method="POST">
        <input type="hidden" name="action" value="action_name">
        <!-- Form fields -->
        <button type="submit">Submit</button>
    </form>
    {% endif %}
</div>
{% endblock %}
```

### Step 2: Add Route in app.py
Add the route in `src/app.py`:

```python
@app.route('/{{page_name}}', methods=['GET', 'POST'])
def {{page_name}}():
    """{{PAGE_PURPOSE}}"""
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'specific_action':
            # Handle action
            flash('Action completed.', 'success')
        
        return redirect(url_for('{{page_name}}'))
    
    # Load data for display
    pools = load_teams()
    results = load_results()
    # ... other data loading ...
    
    return render_template('{{page_name}}.html',
                          pools=pools,
                          results=results)
```

### Step 3: Add Navigation Link
Update `src/templates/base.html` navigation:

```html
<nav>
    <!-- existing links -->
    <a href="{{ url_for('{{page_name}}') }}">{{PAGE_TITLE}}</a>
</nav>
```

### Step 4: Add Styles (if needed)
Add CSS to `src/static/style.css`:

```css
/* {{PAGE_TITLE}} page styles */
.{{page_name}}-container {
    /* Page-specific styles */
}
```

### Step 5: Write Tests
Add tests in `tests/test_app.py`:

```python
def test_{{page_name}}_page_loads(self, client):
    """Test {{page_name}} page loads successfully."""
    response = client.get('/{{page_name}}')
    assert response.status_code == 200
    assert b'{{PAGE_TITLE}}' in response.data

def test_{{page_name}}_form_submission(self, client):
    """Test form submission on {{page_name}} page."""
    response = client.post('/{{page_name}}',
        data={'action': 'specific_action', 'field': 'value'},
        follow_redirects=True)
    assert response.status_code == 200
```

### Step 6: Run and Verify
```bash
# Run the dev server
cd src && python -m flask run --debug

# Run tests
pytest tests/test_app.py -v -k "{{page_name}}"
```
