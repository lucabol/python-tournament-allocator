# Add New API Endpoint

## Description
Add a new REST API endpoint to the Flask application.

## Variables
- `ENDPOINT_PATH`: URL path (e.g., "/api/matches/swap")
- `HTTP_METHOD`: POST, GET, PUT, DELETE
- `ENDPOINT_PURPOSE`: What the endpoint does

## Workflow

### Step 1: Define Route in app.py
Add the route decorator and function in `src/app.py`:

```python
@app.route('{{ENDPOINT_PATH}}', methods=['{{HTTP_METHOD}}'])
def api_{{endpoint_name}}():
    """{{ENDPOINT_PURPOSE}}"""
    data = request.get_json()
    
    # Validate required fields
    required_fields = ['field1', 'field2']
    for field in required_fields:
        if not data.get(field):
            return jsonify({'error': f'Missing {field}'}), 400
    
    # Process request
    try:
        result = process_{{endpoint_name}}(data)
        return jsonify({'success': True, 'result': result})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
```

### Step 2: Implement Processing Logic
If complex, add a helper function:

```python
def process_{{endpoint_name}}(data):
    """Process the {{endpoint_name}} request."""
    # Load relevant data
    existing_data = load_relevant_data()
    
    # Apply changes
    # ...
    
    # Save updated data
    save_relevant_data(existing_data)
    
    return processed_result
```

### Step 3: Add Frontend Call (if needed)
Add JavaScript to call the API:

```javascript
fetch('{{ENDPOINT_PATH}}', {
    method: '{{HTTP_METHOD}}',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({field1: value1, field2: value2})
})
.then(response => response.json())
.then(data => {
    if (data.success) {
        // Handle success
    } else {
        // Handle error
        console.error(data.error);
    }
});
```

### Step 4: Write Tests
Add tests in `tests/test_app.py`:

```python
def test_{{endpoint_name}}_success(self, client):
    """Test successful {{endpoint_name}} request."""
    response = client.post('{{ENDPOINT_PATH}}',
        json={'field1': 'value1', 'field2': 'value2'},
        content_type='application/json')
    
    assert response.status_code == 200
    data = response.get_json()
    assert data['success'] is True

def test_{{endpoint_name}}_missing_field(self, client):
    """Test {{endpoint_name}} with missing required field."""
    response = client.post('{{ENDPOINT_PATH}}',
        json={'field1': 'value1'},  # Missing field2
        content_type='application/json')
    
    assert response.status_code == 400
    assert 'error' in response.get_json()
```

### Step 5: Run Tests
```bash
pytest tests/test_app.py -v -k "{{endpoint_name}}"
```
