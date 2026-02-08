"""
Unit tests for Flask web application.
"""
import pytest
import sys
import os
import tempfile
import yaml

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from app import app, load_teams, save_teams, load_constraints, get_default_constraints


@pytest.fixture
def client():
    """Create a test client for the Flask app."""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


@pytest.fixture
def temp_data_dir(tmp_path, monkeypatch):
    """Set up temporary data directory for tests."""
    import app as app_module
    
    # Create temp files
    teams_file = tmp_path / "teams.yaml"
    courts_file = tmp_path / "courts.csv"
    constraints_file = tmp_path / "constraints.yaml"
    
    # Initialize with test data
    teams_file.write_text("")
    courts_file.write_text("court_name,start_time,end_time\n")
    constraints_file.write_text("")
    
    # Monkeypatch the file paths
    monkeypatch.setattr(app_module, 'TEAMS_FILE', str(teams_file))
    monkeypatch.setattr(app_module, 'COURTS_FILE', str(courts_file))
    monkeypatch.setattr(app_module, 'CONSTRAINTS_FILE', str(constraints_file))
    
    return tmp_path


class TestLoadTeams:
    """Tests for load_teams function with new format."""
    
    def test_load_teams_normalizes_old_format(self, temp_data_dir, monkeypatch):
        """Test that old list format is normalized to new dict format."""
        import app as app_module
        
        teams_file = temp_data_dir / "teams.yaml"
        yaml_content = """pool1:
  - Team A
  - Team B
pool2:
  - Team C
"""
        teams_file.write_text(yaml_content)
        
        pools = load_teams()
        
        # Should be normalized to new format
        assert 'pool1' in pools
        assert 'pool2' in pools
        assert pools['pool1']['teams'] == ['Team A', 'Team B']
        assert pools['pool1']['advance'] == 2  # Default value
        assert pools['pool2']['teams'] == ['Team C']
        assert pools['pool2']['advance'] == 2
    
    def test_load_teams_preserves_new_format(self, temp_data_dir, monkeypatch):
        """Test that new format with advance is preserved."""
        import app as app_module
        
        teams_file = temp_data_dir / "teams.yaml"
        yaml_content = """pool1:
  teams:
    - Team A
    - Team B
  advance: 3
pool2:
  teams:
    - Team C
  advance: 1
"""
        teams_file.write_text(yaml_content)
        
        pools = load_teams()
        
        assert pools['pool1']['teams'] == ['Team A', 'Team B']
        assert pools['pool1']['advance'] == 3
        assert pools['pool2']['teams'] == ['Team C']
        assert pools['pool2']['advance'] == 1
    
    def test_load_teams_empty_file(self, temp_data_dir, monkeypatch):
        """Test loading empty teams file."""
        import app as app_module
        
        teams_file = temp_data_dir / "teams.yaml"
        teams_file.write_text("")
        
        pools = load_teams()
        
        assert pools == {}
    
    def test_load_teams_missing_file(self, temp_data_dir, monkeypatch):
        """Test loading when file doesn't exist."""
        import app as app_module
        
        # Point to non-existent file
        monkeypatch.setattr(app_module, 'TEAMS_FILE', str(temp_data_dir / "nonexistent.yaml"))
        
        pools = load_teams()
        
        assert pools == {}


class TestSaveTeams:
    """Tests for save_teams function."""
    
    def test_save_teams_new_format(self, temp_data_dir, monkeypatch):
        """Test saving teams in new format."""
        import app as app_module
        
        teams_file = temp_data_dir / "teams.yaml"
        
        pools_data = {
            'pool1': {'teams': ['Team A', 'Team B'], 'advance': 3},
            'pool2': {'teams': ['Team C'], 'advance': 1}
        }
        
        save_teams(pools_data)
        
        # Verify file content
        with open(teams_file, 'r') as f:
            saved_data = yaml.safe_load(f)
        
        assert saved_data['pool1']['teams'] == ['Team A', 'Team B']
        assert saved_data['pool1']['advance'] == 3
        assert saved_data['pool2']['advance'] == 1


class TestTeamsRoutes:
    """Tests for teams management routes."""
    
    def test_add_pool_with_advance_count(self, client, temp_data_dir):
        """Test adding a pool with custom advance count."""
        response = client.post('/teams', data={
            'action': 'add_pool',
            'pool_name': 'new_pool',
            'advance_count': '3'
        }, follow_redirects=True)
        
        assert response.status_code == 200
        
        pools = load_teams()
        assert 'new_pool' in pools
        assert pools['new_pool']['advance'] == 3
        assert pools['new_pool']['teams'] == []
    
    def test_add_pool_default_advance_count(self, client, temp_data_dir):
        """Test adding a pool with default advance count."""
        response = client.post('/teams', data={
            'action': 'add_pool',
            'pool_name': 'default_pool'
        }, follow_redirects=True)
        
        assert response.status_code == 200
        
        pools = load_teams()
        assert 'default_pool' in pools
        assert pools['default_pool']['advance'] == 2  # Default
    
    def test_update_advance_count(self, client, temp_data_dir):
        """Test updating advance count for existing pool."""
        # First create a pool
        client.post('/teams', data={
            'action': 'add_pool',
            'pool_name': 'test_pool',
            'advance_count': '2'
        })
        
        # Update advance count
        response = client.post('/teams', data={
            'action': 'update_advance',
            'pool_name': 'test_pool',
            'advance_count': '4'
        }, follow_redirects=True)
        
        assert response.status_code == 200
        
        pools = load_teams()
        assert pools['test_pool']['advance'] == 4
    
    def test_add_team_to_new_format_pool(self, client, temp_data_dir):
        """Test adding a team to a pool in new format."""
        # Create pool
        client.post('/teams', data={
            'action': 'add_pool',
            'pool_name': 'my_pool',
            'advance_count': '2'
        })
        
        # Add team
        response = client.post('/teams', data={
            'action': 'add_team',
            'pool_name': 'my_pool',
            'team_name': 'New Team'
        }, follow_redirects=True)
        
        assert response.status_code == 200
        
        pools = load_teams()
        assert 'New Team' in pools['my_pool']['teams']
        assert pools['my_pool']['advance'] == 2  # Should still be preserved
    
    def test_delete_team_preserves_advance(self, client, temp_data_dir):
        """Test that deleting a team preserves the advance count."""
        # Create pool with team
        client.post('/teams', data={
            'action': 'add_pool',
            'pool_name': 'del_pool',
            'advance_count': '3'
        })
        client.post('/teams', data={
            'action': 'add_team',
            'pool_name': 'del_pool',
            'team_name': 'Team To Delete'
        })
        
        # Delete team
        response = client.post('/teams', data={
            'action': 'delete_team',
            'pool_name': 'del_pool',
            'team_name': 'Team To Delete'
        }, follow_redirects=True)
        
        assert response.status_code == 200
        
        pools = load_teams()
        assert 'Team To Delete' not in pools['del_pool']['teams']
        assert pools['del_pool']['advance'] == 3  # Still preserved
    
    def test_edit_team_name(self, client, temp_data_dir):
        """Test editing a team name."""
        # Create pool with team
        client.post('/teams', data={
            'action': 'add_pool',
            'pool_name': 'edit_pool'
        })
        client.post('/teams', data={
            'action': 'add_team',
            'pool_name': 'edit_pool',
            'team_name': 'Original Name'
        })
        
        # Edit team name
        response = client.post('/teams', data={
            'action': 'edit_team',
            'pool_name': 'edit_pool',
            'old_team_name': 'Original Name',
            'new_team_name': 'New Name'
        }, follow_redirects=True)
        
        assert response.status_code == 200
        
        pools = load_teams()
        assert 'Original Name' not in pools['edit_pool']['teams']
        assert 'New Name' in pools['edit_pool']['teams']
    
    def test_edit_team_name_duplicate_error(self, client, temp_data_dir):
        """Test that renaming to existing team name shows error."""
        # Create pool with two teams
        client.post('/teams', data={
            'action': 'add_pool',
            'pool_name': 'dup_edit_pool'
        })
        client.post('/teams', data={
            'action': 'add_team',
            'pool_name': 'dup_edit_pool',
            'team_name': 'Team Alpha'
        })
        client.post('/teams', data={
            'action': 'add_team',
            'pool_name': 'dup_edit_pool',
            'team_name': 'Team Beta'
        })
        
        # Try to rename Team Beta to Team Alpha
        response = client.post('/teams', data={
            'action': 'edit_team',
            'pool_name': 'dup_edit_pool',
            'old_team_name': 'Team Beta',
            'new_team_name': 'Team Alpha'
        }, follow_redirects=True)
        
        assert response.status_code == 200
        assert b'already exists' in response.data
        
        # Original names should be unchanged
        pools = load_teams()
        assert 'Team Alpha' in pools['dup_edit_pool']['teams']
        assert 'Team Beta' in pools['dup_edit_pool']['teams']
    
    def test_duplicate_pool_shows_error(self, client, temp_data_dir):
        """Test that adding duplicate pool shows error message."""
        # Create pool
        client.post('/teams', data={
            'action': 'add_pool',
            'pool_name': 'dup_pool'
        })
        
        # Try to create same pool again
        response = client.post('/teams', data={
            'action': 'add_pool',
            'pool_name': 'dup_pool'
        }, follow_redirects=True)
        
        assert response.status_code == 200
        assert b'already exists' in response.data
    
    def test_duplicate_team_shows_error(self, client, temp_data_dir):
        """Test that adding duplicate team shows error message."""
        # Create pool and team
        client.post('/teams', data={
            'action': 'add_pool',
            'pool_name': 'pool_a'
        })
        client.post('/teams', data={
            'action': 'add_team',
            'pool_name': 'pool_a',
            'team_name': 'Same Team'
        })
        
        # Create another pool and try to add same team
        client.post('/teams', data={
            'action': 'add_pool',
            'pool_name': 'pool_b'
        })
        response = client.post('/teams', data={
            'action': 'add_team',
            'pool_name': 'pool_b',
            'team_name': 'Same Team'
        }, follow_redirects=True)
        
        assert response.status_code == 200
        assert b'already exists' in response.data


class TestIndexRoute:
    """Tests for index route displaying pool information."""
    
    def test_index_shows_total_teams(self, client, temp_data_dir):
        """Test that index shows correct total team count."""
        import app as app_module
        
        teams_file = temp_data_dir / "teams.yaml"
        yaml_content = """pool1:
  teams:
    - Team A
    - Team B
  advance: 2
pool2:
  teams:
    - Team C
  advance: 1
"""
        teams_file.write_text(yaml_content)
        
        response = client.get('/')
        
        assert response.status_code == 200
        # Page should show 3 total teams
        assert b'3' in response.data


class TestCourtsRoutes:
    """Tests for courts management routes."""
    
    def test_edit_court_name(self, client, temp_data_dir):
        """Test editing a court name."""
        # Add a court
        client.post('/courts', data={
            'action': 'add_court',
            'court_name': 'Court 1',
            'start_time': '08:00',
            'end_time': '20:00'
        })
        
        # Edit court name
        response = client.post('/courts', data={
            'action': 'edit_court',
            'old_court_name': 'Court 1',
            'new_court_name': 'Main Court'
        }, follow_redirects=True)
        
        assert response.status_code == 200
        assert b'Main Court' in response.data
        assert b'Court 1' not in response.data or b'renamed' in response.data.lower()
    
    def test_edit_court_duplicate_error(self, client, temp_data_dir):
        """Test that renaming to existing court name shows error."""
        # Add two courts
        client.post('/courts', data={
            'action': 'add_court',
            'court_name': 'Court A',
            'start_time': '08:00',
            'end_time': '20:00'
        })
        client.post('/courts', data={
            'action': 'add_court',
            'court_name': 'Court B',
            'start_time': '09:00',
            'end_time': '21:00'
        })
        
        # Try to rename Court B to Court A
        response = client.post('/courts', data={
            'action': 'edit_court',
            'old_court_name': 'Court B',
            'new_court_name': 'Court A'
        }, follow_redirects=True)
        
        assert response.status_code == 200
        assert b'already exists' in response.data


class TestSettingsRoute:
    """Tests for settings route with team list from new format."""
    
    def test_settings_lists_all_teams(self, client, temp_data_dir):
        """Test that settings page lists teams from new format pools."""
        import app as app_module
        
        teams_file = temp_data_dir / "teams.yaml"
        yaml_content = """pool1:
  teams:
    - Alpha Team
    - Beta Team
  advance: 2
"""
        teams_file.write_text(yaml_content)
        
        response = client.get('/settings')
        
        assert response.status_code == 200
        assert b'Alpha Team' in response.data or b'alpha' in response.data.lower()


class TestLiveRoute:
    """Tests for live tournament view page (read-only player view)."""
    
    def test_live_page_loads(self, client, temp_data_dir):
        """Test live page loads successfully."""
        response = client.get('/live')
        assert response.status_code == 200
        assert b'Live Tournament' in response.data
    
    def test_live_page_shows_empty_state(self, client, temp_data_dir):
        """Test live page shows empty state when no teams configured."""
        response = client.get('/live')
        assert response.status_code == 200
        assert b'Tournament Not Started' in response.data or b'No teams' in response.data.lower()
    
    def test_live_page_shows_standings(self, client, temp_data_dir):
        """Test live page shows pool standings when teams exist."""
        import app as app_module
        
        teams_file = temp_data_dir / "teams.yaml"
        yaml_content = """Pool A:
  teams:
    - Team Alpha
    - Team Beta
  advance: 2
"""
        teams_file.write_text(yaml_content)
        
        response = client.get('/live')
        
        assert response.status_code == 200
        assert b'Pool Standings' in response.data
        assert b'Pool A' in response.data
        assert b'Team Alpha' in response.data
        assert b'Team Beta' in response.data
    
    def test_live_page_has_sse(self, client, temp_data_dir):
        """Test live page uses EventSource (SSE) for live updates."""
        response = client.get('/live')
        assert response.status_code == 200
        assert b'EventSource' in response.data
        assert b'/api/live-stream' in response.data
    
    def test_live_page_is_read_only(self, client, temp_data_dir):
        """Test live page does not contain score input fields."""
        import app as app_module
        
        teams_file = temp_data_dir / "teams.yaml"
        yaml_content = """Pool A:
  teams:
    - Team 1
    - Team 2
  advance: 2
"""
        teams_file.write_text(yaml_content)
        
        response = client.get('/live')
        
        assert response.status_code == 200
        # Should not have score input fields (which are in the manager views)
        assert b'class="score-input"' not in response.data


class TestLiveSSE:
    """Tests for SSE-based live update endpoints."""

    def test_live_html_returns_partial(self, client, temp_data_dir):
        """Test /api/live-html returns partial HTML without full page wrapper."""
        response = client.get('/api/live-html')
        assert response.status_code == 200
        html = response.data
        # Partial should not contain full-page elements
        assert b'<html' not in html
        assert b'<head' not in html
        assert b'</html>' not in html
        # Should still contain the live content
        assert b'Tournament Not Started' in html or b'Pool Standings' in html

    def test_live_html_shows_standings(self, client, temp_data_dir):
        """Test /api/live-html returns standings when teams exist."""
        import app as app_module

        teams_file = temp_data_dir / "teams.yaml"
        yaml_content = """Pool A:
  teams:
    - Team Alpha
    - Team Beta
  advance: 2
"""
        teams_file.write_text(yaml_content)

        response = client.get('/api/live-html')
        assert response.status_code == 200
        assert b'Pool A' in response.data
        assert b'Team Alpha' in response.data

    def test_live_stream_returns_event_stream(self, client, temp_data_dir):
        """Test /api/live-stream returns the correct content type."""
        response = client.get('/api/live-stream')
        assert response.status_code == 200
        assert 'text/event-stream' in response.content_type
