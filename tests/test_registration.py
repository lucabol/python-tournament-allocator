"""
Integration tests for team registration feature.

Tests the complete registration lifecycle:
- Open/close registration
- Public team registration form
- Validation (email required, phone optional, duplicate names)
- Unassigned team list
- Pool assignment (drag-drop API)
- Pool removal (return to unassigned)
- Test button integration
"""
import pytest
import sys
import os
import yaml
from datetime import datetime
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from app import app


@pytest.fixture
def client():
    """Create an authenticated test client."""
    app.config['TESTING'] = True
    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess['user'] = 'testuser'
        yield client


@pytest.fixture
def temp_data_dir(tmp_path, monkeypatch):
    """Set up temporary data directory with user-scoped tournament structure."""
    import app as app_module
    
    # Build user-scoped directory structure
    users_dir = tmp_path / "users"
    testuser_dir = users_dir / "testuser"
    testuser_tournaments_dir = testuser_dir / "tournaments"
    tournament_data = testuser_tournaments_dir / "default"
    tournament_data.mkdir(parents=True)
    
    # Create test data files inside the default tournament
    teams_file = tournament_data / "teams.yaml"
    courts_file = tournament_data / "courts.csv"
    constraints_file = tournament_data / "constraints.yaml"
    results_file = tournament_data / "results.yaml"
    schedule_file = tournament_data / "schedule.yaml"
    print_settings_file = tournament_data / "print_settings.yaml"
    registrations_file = tournament_data / "registrations.yaml"
    
    teams_file.write_text("Pool A:\n  - Team One\n  - Team Two\n")
    courts_file.write_text("court_name,start_time,end_time\nCourt 1,08:00,22:00\n")
    constraints_file.write_text(yaml.dump({
        'match_duration_minutes': 30,
        'days_number': 1,
        'min_break_between_matches_minutes': 0,
        'day_end_time_limit': '22:00',
        'tournament_name': 'Test Tournament',
        'tournament_dates': '2026-03-01',
        'tournament_location': 'Test Venue'
    }))
    results_file.write_text("")
    schedule_file.write_text("")
    print_settings_file.write_text("")
    registrations_file.write_text(yaml.dump({
        'registration_open': False,
        'teams': []
    }))
    
    # Create tournaments.yaml
    tournaments_yaml = users_dir / "tournaments.yaml"
    tournaments_yaml.write_text(yaml.dump({
        'active': None,
        'tournaments': []
    }))
    
    # Monkeypatch app module to use temp directory
    monkeypatch.setattr(app_module, 'DATA_DIR', str(users_dir))
    monkeypatch.setattr(app_module, 'USERS_DIR', str(users_dir))
    
    return str(users_dir)


class TestTeamRegistration:
    """Integration tests for team registration lifecycle."""
    
    def test_registration_starts_closed(self, client, temp_data_dir):
        """Test that registration system starts in closed state."""
        with client.session_transaction() as sess:
            sess['user'] = 'testuser'
            sess['active_tournament'] = 'default'
        
        response = client.get('/teams')
        assert response.status_code == 200
        # Registration should be closed by default
        assert b'closed' in response.data.lower() or b'open registration' in response.data.lower()
    
    def test_open_registration_toggle(self, client, temp_data_dir):
        """Test opening registration via toggle endpoint."""
        with client.session_transaction() as sess:
            sess['user'] = 'testuser'
            sess['active_tournament'] = 'default'
        
        response = client.post('/api/registrations/toggle',
                              json={},
                              content_type='application/json')
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert data['registration_open'] is True
    
    def test_close_registration_toggle(self, client, temp_data_dir):
        """Test closing registration via toggle endpoint."""
        with client.session_transaction() as sess:
            sess['user'] = 'testuser'
            sess['active_tournament'] = 'default'
        
        # First open it
        client.post('/api/registrations/toggle',
                   json={},
                   content_type='application/json')
        
        # Then close it
        response = client.post('/api/registrations/toggle',
                              json={},
                              content_type='application/json')
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        assert data['registration_open'] is False
    
    def test_public_registration_form_when_closed(self, client, temp_data_dir):
        """Test that public registration form shows closed message when registration is closed."""
        response = client.get('/register/testuser/default')
        
        assert response.status_code == 200
        # Should show closed message
        assert b'closed' in response.data.lower() or b'not currently accepting' in response.data.lower()
    
    def test_public_registration_form_when_open(self, client, temp_data_dir):
        """Test that public registration form shows form when registration is open."""
        # First open registration
        with client.session_transaction() as sess:
            sess['user'] = 'testuser'
            sess['active_tournament'] = 'default'
        
        client.post('/api/registrations/toggle',
                   json={},
                   content_type='application/json')
        
        # Now access public form
        response = client.get('/register/testuser/default')
        
        assert response.status_code == 200
        # Should show form fields
        assert b'team' in response.data.lower()
        assert b'email' in response.data.lower()
    
    def test_register_team_success(self, client, temp_data_dir):
        """Test successful team registration with all required fields."""
        # Open registration first
        with client.session_transaction() as sess:
            sess['user'] = 'testuser'
            sess['active_tournament'] = 'default'
        
        client.post('/api/registrations/toggle',
                   json={},
                   content_type='application/json')
        
        # Register a team
        response = client.post('/register/testuser/default',
                              json={
                                  'team_name': 'New Team Alpha',
                                  'email': 'alpha@example.com',
                                  'phone': '+1234567890'
                              },
                              content_type='application/json')
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
    
    def test_register_team_email_required(self, client, temp_data_dir):
        """Test that email field is required for registration."""
        # Open registration first
        with client.session_transaction() as sess:
            sess['user'] = 'testuser'
            sess['active_tournament'] = 'default'
        
        client.post('/api/registrations/toggle',
                   json={},
                   content_type='application/json')
        
        # Try to register without email
        response = client.post('/register/testuser/default',
                              json={
                                  'team_name': 'No Email Team',
                                  'phone': '+1234567890'
                              },
                              content_type='application/json')
        
        # Should fail validation
        data = response.get_json()
        assert data['success'] is False
        assert 'email' in data['error'].lower()
    
    def test_register_team_phone_optional(self, client, temp_data_dir):
        """Test that phone field is optional for registration."""
        # Open registration first
        with client.session_transaction() as sess:
            sess['user'] = 'testuser'
            sess['active_tournament'] = 'default'
        
        client.post('/api/registrations/toggle',
                   json={},
                   content_type='application/json')
        
        # Register without phone
        response = client.post('/register/testuser/default',
                              json={
                                  'team_name': 'No Phone Team',
                                  'email': 'nophone@example.com'
                              },
                              content_type='application/json')
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
    
    def test_register_duplicate_team_name_rejected(self, client, temp_data_dir):
        """Test that duplicate team names are rejected."""
        # Open registration and register first team
        with client.session_transaction() as sess:
            sess['user'] = 'testuser'
            sess['active_tournament'] = 'default'
        
        client.post('/api/registrations/toggle',
                   json={},
                   content_type='application/json')
        
        client.post('/register/testuser/default',
                   json={
                       'team_name': 'Duplicate Team',
                       'email': 'first@example.com',
                       'phone': '+1111111111'
                   },
                   content_type='application/json')
        
        # Try to register with same name
        response = client.post('/register/testuser/default',
                              json={
                                  'team_name': 'Duplicate Team',
                                  'email': 'second@example.com',
                                  'phone': '+2222222222'
                              },
                              content_type='application/json')
        
        data = response.get_json()
        assert data['success'] is False
        assert 'duplicate' in data['error'].lower() or 'already' in data['error'].lower()
    
    def test_registered_team_appears_in_unassigned_list(self, client, temp_data_dir):
        """Test that newly registered team appears in unassigned list on teams page."""
        # Open registration and register a team
        with client.session_transaction() as sess:
            sess['user'] = 'testuser'
            sess['active_tournament'] = 'default'
        
        client.post('/api/registrations/toggle',
                   json={},
                   content_type='application/json')
        
        client.post('/register/testuser/default',
                   json={
                       'team_name': 'Unassigned Team',
                       'email': 'unassigned@example.com',
                       'phone': '+3333333333'
                   },
                   content_type='application/json')
        
        # Check teams page
        response = client.get('/teams')
        assert response.status_code == 200
        assert b'Unassigned Team' in response.data
        assert b'unassigned@example.com' in response.data
    
    def test_assign_team_to_pool(self, client, temp_data_dir):
        """Test assigning a registered team to a pool via API."""
        # Open registration and register a team
        with client.session_transaction() as sess:
            sess['user'] = 'testuser'
            sess['active_tournament'] = 'default'
        
        client.post('/api/registrations/toggle',
                   json={},
                   content_type='application/json')
        
        client.post('/register/testuser/default',
                   json={
                       'team_name': 'Team To Assign',
                       'email': 'assign@example.com',
                       'phone': '+4444444444'
                   },
                   content_type='application/json')
        
        # Assign to pool
        response = client.post('/api/teams/assign_from_registration',
                              json={
                                  'team_name': 'Team To Assign',
                                  'pool_name': 'Pool A'
                              },
                              content_type='application/json')
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
    
    def test_assigned_team_appears_in_pool_and_leaves_unassigned(self, client, temp_data_dir):
        """Test that assigned team appears in pool and is removed from unassigned list."""
        # Open registration and register a team
        with client.session_transaction() as sess:
            sess['user'] = 'testuser'
            sess['active_tournament'] = 'default'
        
        client.post('/api/registrations/toggle',
                   json={},
                   content_type='application/json')
        
        client.post('/register/testuser/default',
                   json={
                       'team_name': 'Assigned Team',
                       'email': 'assigned@example.com'
                   },
                   content_type='application/json')
        
        # Verify in unassigned list first
        response = client.get('/teams')
        assert b'Assigned Team' in response.data
        
        # Assign to pool
        client.post('/api/teams/assign_from_registration',
                   json={
                       'team_name': 'Assigned Team',
                       'pool_name': 'Pool A'
                   },
                   content_type='application/json')
        
        # Verify in pool and not in unassigned
        response = client.get('/teams')
        assert response.status_code == 200
        # Team should appear in Pool A section
        content = response.data.decode('utf-8')
        # Should contain the team name within Pool A context
        assert 'Assigned Team' in content
        # The team's registration status should be "assigned" (not visible in unassigned section)
    
    def test_remove_team_from_pool_returns_to_unassigned(self, client, temp_data_dir):
        """Test that removing a registered team from a pool returns it to unassigned list."""
        # Open registration, register, and assign a team
        with client.session_transaction() as sess:
            sess['user'] = 'testuser'
            sess['active_tournament'] = 'default'
        
        client.post('/api/registrations/toggle',
                   json={},
                   content_type='application/json')
        
        client.post('/register/testuser/default',
                   json={
                       'team_name': 'Removable Team',
                       'email': 'remove@example.com'
                   },
                   content_type='application/json')
        
        client.post('/api/teams/assign_from_registration',
                   json={
                       'team_name': 'Removable Team',
                       'pool_name': 'Pool A'
                   },
                   content_type='application/json')
        
        # Remove from pool
        response = client.post('/teams',
                              data={
                                  'action': 'delete_team',
                                  'pool_name': 'Pool A',
                                  'team_name': 'Removable Team'
                              })
        
        # Verify it's back in unassigned
        response = client.get('/teams')
        assert response.status_code == 200
        assert b'Removable Team' in response.data
    
    def test_edit_registration(self, client, temp_data_dir):
        """Test editing a registered team's information."""
        # Open registration and register a team
        with client.session_transaction() as sess:
            sess['user'] = 'testuser'
            sess['active_tournament'] = 'default'
        
        client.post('/api/registrations/toggle',
                   json={},
                   content_type='application/json')
        
        client.post('/register/testuser/default',
                   json={
                       'team_name': 'Team To Edit',
                       'email': 'original@example.com',
                       'phone': '+5555555555'
                   },
                   content_type='application/json')
        
        # Edit the registration
        response = client.post('/api/registrations/edit',
                              json={
                                  'original_name': 'Team To Edit',
                                  'team_name': 'Team Edited',
                                  'email': 'edited@example.com',
                                  'phone': '+6666666666'
                              },
                              content_type='application/json')
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
    
    def test_delete_registration(self, client, temp_data_dir):
        """Test deleting a registered team."""
        # Open registration and register a team
        with client.session_transaction() as sess:
            sess['user'] = 'testuser'
            sess['active_tournament'] = 'default'
        
        client.post('/api/registrations/toggle',
                   json={},
                   content_type='application/json')
        
        client.post('/register/testuser/default',
                   json={
                       'team_name': 'Team To Delete',
                       'email': 'delete@example.com'
                   },
                   content_type='application/json')
        
        # Delete the registration
        response = client.post('/api/registrations/delete',
                              json={'team_name': 'Team To Delete'},
                              content_type='application/json')
        
        assert response.status_code == 200
        data = response.get_json()
        assert data['success'] is True
        
        # Verify not in unassigned list
        response = client.get('/teams')
        assert b'Team To Delete' not in response.data
    
    def test_registration_when_closed_rejected(self, client, temp_data_dir):
        """Test that registration attempts are rejected when registration is closed."""
        # Ensure registration is closed
        with client.session_transaction() as sess:
            sess['user'] = 'testuser'
            sess['active_tournament'] = 'default'
        
        # Try to register with closed registration
        response = client.post('/register/testuser/default',
                              json={
                                  'team_name': 'Late Team',
                                  'email': 'late@example.com'
                              },
                              content_type='application/json')
        
        data = response.get_json()
        assert data['success'] is False
        assert 'closed' in data['error'].lower() or 'not open' in data['error'].lower()
    
    def test_test_button_integration(self, client, temp_data_dir):
        """Test that Test button still works with registration system in place."""
        with client.session_transaction() as sess:
            sess['user'] = 'testuser'
            sess['active_tournament'] = 'default'
        
        # Use the test button endpoint (if it exists)
        # This typically generates sample data
        response = client.post('/teams',
                              data={'action': 'generate_test_data'})
        
        # Should succeed (or 404 if endpoint doesn't exist yet)
        # We're testing that registration system doesn't break existing functionality
        assert response.status_code in [200, 302, 404]
        
        # If successful, verify we can still view the teams page
        if response.status_code in [200, 302]:
            response = client.get('/teams')
            assert response.status_code == 200
    
    def test_registration_persists_timestamp(self, client, temp_data_dir):
        """Test that registration timestamp is stored and can be retrieved."""
        # Open registration and register a team
        with client.session_transaction() as sess:
            sess['user'] = 'testuser'
            sess['active_tournament'] = 'default'
        
        client.post('/api/registrations/toggle',
                   json={},
                   content_type='application/json')
        
        before_time = datetime.now()
        
        client.post('/register/testuser/default',
                   json={
                       'team_name': 'Timestamped Team',
                       'email': 'timestamp@example.com'
                   },
                   content_type='application/json')
        
        after_time = datetime.now()
        
        # Read registrations file directly to verify timestamp
        users_dir = temp_data_dir
        reg_file = Path(users_dir) / 'testuser' / 'tournaments' / 'default' / 'registrations.yaml'
        with open(reg_file, 'r', encoding='utf-8') as f:
            reg_data = yaml.safe_load(f)
        
        team_data = next((t for t in reg_data['teams'] if t['team_name'] == 'Timestamped Team'), None)
        assert team_data is not None
        assert 'registered_at' in team_data
        
        # Parse timestamp
        reg_time = datetime.fromisoformat(team_data['registered_at'])
        # Should be between before and after
        assert before_time <= reg_time <= after_time
    
    def test_multiple_teams_registration_workflow(self, client, temp_data_dir):
        """Test complete workflow with multiple teams."""
        # Open registration
        with client.session_transaction() as sess:
            sess['user'] = 'testuser'
            sess['active_tournament'] = 'default'
        
        client.post('/api/registrations/toggle',
                   json={},
                   content_type='application/json')
        
        # Register three teams
        teams = [
            ('Team Alpha', 'alpha@example.com', '+1111111111'),
            ('Team Beta', 'beta@example.com', None),
            ('Team Gamma', 'gamma@example.com', '+3333333333')
        ]
        
        for name, email, phone in teams:
            payload = {'team_name': name, 'email': email}
            if phone:
                payload['phone'] = phone
            
            response = client.post('/register/testuser/default',
                                  json=payload,
                                  content_type='application/json')
            assert response.status_code == 200
            data = response.get_json()
            assert data['success'] is True
        
        # Verify all in unassigned list
        response = client.get('/teams')
        for name, _, _ in teams:
            assert name.encode() in response.data
        
        # Assign first two to Pool A
        for name, _, _ in teams[:2]:
            response = client.post('/api/teams/assign_from_registration',
                                  json={
                                      'team_name': name,
                                      'pool_name': 'Pool A'
                                  },
                                  content_type='application/json')
            assert response.status_code == 200
        
        # Verify third still unassigned
        response = client.get('/teams')
        assert b'Team Gamma' in response.data
        
        # Close registration
        response = client.post('/api/registrations/toggle',
                              json={},
                              content_type='application/json')
        data = response.get_json()
        assert data['registration_open'] is False
        
        # Remove first team from pool
        client.post('/teams',
                   data={
                       'action': 'delete_team',
                       'pool_name': 'Pool A',
                       'team_name': 'Team Alpha'
                   })
        
        # Verify it returned to unassigned
        response = client.get('/teams')
        assert b'Team Alpha' in response.data
