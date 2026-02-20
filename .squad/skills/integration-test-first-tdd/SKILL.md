---
name: "integration-test-first-tdd"
description: "Writing integration tests before implementation to define API contracts and expected behavior"
domain: "testing"
confidence: "low"
source: "earned"
---

## Context
When multiple agents work in parallel (testers, backend developers, frontend developers), having tests written first provides a clear contract for what the implementation must do. Integration tests are especially valuable because they define the full request-response cycle, validation rules, and data persistence behavior.

## Patterns

### Test-First for New Features
1. **Read requirements document** — understand the complete feature lifecycle, edge cases, and validation rules before writing tests.

2. **Create comprehensive test class** — organize tests by feature area, not by HTTP method:
   ```python
   class TestFeatureName:
       """Integration tests for complete feature lifecycle."""
       
       def test_feature_starts_in_correct_state(self, ...):
           """Verify initial state."""
           
       def test_happy_path_success(self, ...):
           """Test main success scenario."""
           
       def test_validation_rule_1_enforced(self, ...):
           """Test specific validation rule."""
           
       def test_edge_case_x_handled(self, ...):
           """Test boundary condition."""
           
       def test_full_workflow_end_to_end(self, ...):
           """Test complete multi-step workflow."""
   ```

3. **Test behavior, not implementation** — tests should validate what the API does, not how it does it. Focus on:
   - HTTP status codes
   - JSON response structure (`success`, `error` fields)
   - Data persistence (read files/DB after operation)
   - State transitions (unassigned → assigned → unassigned)

4. **Cover validation rules explicitly** — each validation rule gets its own test:
   ```python
   def test_email_required(self, ...):
       """Test that email field is required."""
       response = client.post('/endpoint', json={'name': 'X'})
       data = response.get_json()
       assert data['success'] is False
       assert 'email' in data['error'].lower()
   ```

5. **Test the full lifecycle** — include at least one end-to-end test that exercises the complete workflow with multiple operations in sequence.

### Expected Test Results
- All tests should **fail initially** (routes don't exist yet)
- Tests define the contract: status codes, response structure, validation behavior
- Implementation team can run tests incrementally as they build features
- When all tests pass, feature is complete by definition

### Fixture Setup
Use temporary directories and monkeypatching to isolate test data:
```python
@pytest.fixture
def temp_data_dir(tmp_path, monkeypatch):
    """Set up isolated filesystem for tests."""
    # Create directory structure
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    
    # Create initial files with known state
    (data_dir / "file.yaml").write_text(yaml.dump({'key': 'value'}))
    
    # Monkeypatch app to use temp directory
    monkeypatch.setattr(app_module, 'DATA_DIR', str(data_dir))
    
    return str(data_dir)
```

## Anti-Patterns
- **Writing tests after implementation** — loses the benefit of tests as specification. Tests become "whatever the code does" rather than "what the code should do".
- **Testing implementation details** — tests shouldn't depend on internal variable names, function calls, or module structure. Test the public API only.
- **Skipping edge cases** — tests written first force you to think through validation, error handling, and boundary conditions before coding.
- **Incomplete lifecycle coverage** — test the complete workflow, not just creation. Include read, update, delete, and state transitions.

## Examples

### Good: Complete Lifecycle Test
```python
def test_complete_registration_workflow(self, client, temp_data_dir):
    """Test complete workflow: open → register → assign → remove."""
    # Setup: open registration
    client.post('/api/registrations/toggle')
    
    # Register team
    response = client.post('/register/user/tournament',
                          json={'team_name': 'Team A', 'email': 'a@ex.com'})
    assert response.get_json()['success'] is True
    
    # Verify in unassigned list
    response = client.get('/teams')
    assert b'Team A' in response.data
    
    # Assign to pool
    client.post('/api/teams/assign', json={'team': 'Team A', 'pool': 'Pool 1'})
    
    # Remove from pool
    client.post('/teams', data={'action': 'delete', 'team': 'Team A', 'pool': 'Pool 1'})
    
    # Verify back in unassigned
    response = client.get('/teams')
    assert b'Team A' in response.data
```

### Good: Specific Validation Test
```python
def test_duplicate_name_rejected(self, client, temp_data_dir):
    """Test that duplicate team names are rejected."""
    # Register first team
    client.post('/register/user/tournament',
               json={'team_name': 'Dupe', 'email': 'a@ex.com'})
    
    # Try duplicate
    response = client.post('/register/user/tournament',
                          json={'team_name': 'Dupe', 'email': 'b@ex.com'})
    
    data = response.get_json()
    assert data['success'] is False
    assert 'duplicate' in data['error'].lower()
```

### Bad: Testing Implementation Details
```python
def test_registration_calls_save_function(self, client, mock_save):
    """Don't test internal function calls — test behavior."""
    client.post('/register', json={...})
    assert mock_save.called  # BAD: tests implementation, not behavior
```

## When to Use
- New feature with clear requirements document
- Multiple agents working in parallel (tester, backend, frontend)
- Feature has complex validation rules or state transitions
- API contract needs to be defined before implementation

## When NOT to Use
- Bug fixes (test should reproduce the bug, then verify fix)
- Refactoring existing code (tests already exist)
- Exploratory prototyping (requirements unclear)
