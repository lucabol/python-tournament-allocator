"""
Unit tests for Flask web application.
"""
import pytest
import sys
import os
import pathlib
import tempfile
import yaml
import zipfile
import io

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from app import app, load_teams, save_teams, load_constraints, get_default_constraints, determine_tournament_phase, calculate_match_stats


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
    logo_prefix = str(tournament_data / "logo")

    teams_file.write_text("")
    courts_file.write_text("court_name,start_time,end_time\n")
    constraints_file.write_text("")

    # Auth: create users.yaml so ensure_tournament_structure() skips migration
    users_file = tmp_path / "users.yaml"
    users_file.write_text(yaml.dump({'users': [
        {'username': 'testuser', 'password_hash': 'unused', 'created': '2026-01-01'}
    ]}, default_flow_style=False))

    # User's tournament registry with an active default tournament
    user_reg = testuser_dir / "tournaments.yaml"
    user_reg.write_text(yaml.dump({
        'active': 'default',
        'tournaments': [{'slug': 'default', 'name': 'Default'}]
    }, default_flow_style=False))

    # Global registry stub
    global_reg = tmp_path / "tournaments.yaml"
    global_reg.write_text(yaml.dump({'active': None, 'tournaments': []}, default_flow_style=False))

    # Monkeypatch — DATA_DIR points to tournament dir so fallback reads match
    monkeypatch.setattr(app_module, 'DATA_DIR', str(tournament_data))
    monkeypatch.setattr(app_module, 'TEAMS_FILE', str(teams_file))
    monkeypatch.setattr(app_module, 'COURTS_FILE', str(courts_file))
    monkeypatch.setattr(app_module, 'CONSTRAINTS_FILE', str(constraints_file))
    monkeypatch.setattr(app_module, 'RESULTS_FILE', str(results_file))
    monkeypatch.setattr(app_module, 'SCHEDULE_FILE', str(schedule_file))
    monkeypatch.setattr(app_module, 'PRINT_SETTINGS_FILE', str(print_settings_file))
    monkeypatch.setattr(app_module, 'LOGO_FILE_PREFIX', logo_prefix)
    monkeypatch.setattr(app_module, 'USERS_FILE', str(users_file))
    monkeypatch.setattr(app_module, 'USERS_DIR', str(users_dir))
    monkeypatch.setattr(app_module, 'TOURNAMENTS_FILE', str(global_reg))
    monkeypatch.setattr(app_module, 'TOURNAMENTS_DIR', str(testuser_tournaments_dir))

    # Rebuild derived constants so export/import uses temp paths
    exportable = {
        'teams.yaml': str(teams_file),
        'courts.csv': str(courts_file),
        'constraints.yaml': str(constraints_file),
        'results.yaml': str(results_file),
        'schedule.yaml': str(schedule_file),
        'print_settings.yaml': str(print_settings_file),
    }
    monkeypatch.setattr(app_module, 'EXPORTABLE_FILES', exportable)
    monkeypatch.setattr(app_module, 'ALLOWED_IMPORT_NAMES', set(exportable.keys()))

    return tournament_data


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


class TestDetermineTournamentPhase:
    """Tests for determine_tournament_phase helper function."""

    def test_setup_when_no_schedule(self):
        """Test returns 'setup' when no schedule exists."""
        results = {'pool_play': {}, 'bracket': {}}
        assert determine_tournament_phase(None, results, None) == 'setup'

    def test_pool_play_when_schedule_exists_but_no_results(self):
        """Test returns 'pool_play' when schedule exists but no results."""
        schedule = {
            'Day 1': {
                '_time_slots': ['09:00'],
                'Court 1': {'matches': [{'teams': ['A', 'B'], 'is_bracket': False}], 'time_to_match': {}}
            }
        }
        results = {'pool_play': {}, 'bracket': {}}
        assert determine_tournament_phase(schedule, results, None) == 'pool_play'

    def test_pool_play_when_some_results(self):
        """Test returns 'pool_play' when some pool results exist."""
        schedule = {
            'Day 1': {
                '_time_slots': ['09:00', '10:00'],
                'Court 1': {
                    'matches': [
                        {'teams': ['A', 'B'], 'is_bracket': False},
                        {'teams': ['C', 'D'], 'is_bracket': False},
                    ],
                    'time_to_match': {}
                }
            }
        }
        results = {
            'pool_play': {'A_vs_B_Pool 1': {'completed': True}},
            'bracket': {}
        }
        assert determine_tournament_phase(schedule, results, None) == 'pool_play'

    def test_bracket_when_all_pool_results_in(self):
        """Test returns 'bracket' when all pool matches completed."""
        schedule = {
            'Day 1': {
                '_time_slots': ['09:00'],
                'Court 1': {
                    'matches': [{'teams': ['A', 'B'], 'is_bracket': False}],
                    'time_to_match': {}
                }
            }
        }
        results = {
            'pool_play': {'A_vs_B_Pool 1': {'completed': True}},
            'bracket': {}
        }
        assert determine_tournament_phase(schedule, results, None) == 'bracket'

    def test_bracket_when_bracket_results_exist(self):
        """Test returns 'bracket' when bracket results exist."""
        schedule = {'Day 1': {'_time_slots': [], 'Court 1': {'matches': [], 'time_to_match': {}}}}
        results = {
            'pool_play': {},
            'bracket': {'winners_QF_1': {'completed': True}}
        }
        assert determine_tournament_phase(schedule, results, None) == 'bracket'

    def test_complete_when_champion_determined(self):
        """Test returns 'complete' when bracket has a champion."""
        schedule = {'Day 1': {'_time_slots': [], 'Court 1': {'matches': [], 'time_to_match': {}}}}
        results = {'pool_play': {}, 'bracket': {}}
        bracket_data = {'champion': 'Team A'}
        assert determine_tournament_phase(schedule, results, bracket_data) == 'complete'


class TestCalculateMatchStats:
    """Tests for calculate_match_stats helper function."""

    def test_no_completed_matches_returns_none(self):
        """Test returns None when no completed matches exist."""
        results = {'pool_play': {}, 'bracket': {}}
        assert calculate_match_stats(results) is None

    def test_single_completed_match(self):
        """Test stats from a single completed match."""
        results = {
            'pool_play': {
                'A_vs_B_Pool 1': {
                    'completed': True,
                    'sets': [[21, 15]],
                    'winner': 'A',
                    'team1': 'A',
                    'team2': 'B',
                }
            },
            'bracket': {}
        }
        stats = calculate_match_stats(results)
        assert stats is not None
        assert stats['matches_completed'] == 1
        assert stats['total_points'] == 36
        assert stats['closest_match']['winner'] == 'A'
        assert stats['biggest_blowout']['winner'] == 'A'
        assert stats['average_margin'] == 6.0

    def test_multiple_matches_finds_extremes(self):
        """Test that closest and biggest are found correctly."""
        results = {
            'pool_play': {
                'A_vs_B': {
                    'completed': True,
                    'sets': [[21, 19]],  # margin 2
                    'winner': 'A', 'team1': 'A', 'team2': 'B',
                },
                'C_vs_D': {
                    'completed': True,
                    'sets': [[21, 5]],  # margin 16
                    'winner': 'C', 'team1': 'C', 'team2': 'D',
                },
            },
            'bracket': {}
        }
        stats = calculate_match_stats(results)
        assert stats['closest_match']['margin'] == 2
        assert stats['biggest_blowout']['margin'] == 16


class TestEnhancedDashboard:
    """Tests for the enhanced dashboard route."""

    def test_dashboard_loads_with_no_data(self, client, temp_data_dir):
        """Test dashboard returns 200 with no data files."""
        response = client.get('/')
        assert response.status_code == 200
        assert b'Setup' in response.data  # Phase indicator

    def test_dashboard_shows_phase_indicator(self, client, temp_data_dir):
        """Test dashboard shows the phase indicator."""
        response = client.get('/')
        assert response.status_code == 200
        assert b'phase-step' in response.data
        assert b'Pool Play' in response.data
        assert b'Bracket' in response.data

    def test_dashboard_shows_tournament_header(self, client, temp_data_dir):
        """Test dashboard shows tournament identity header."""
        import app as app_module

        constraints_file = temp_data_dir / "constraints.yaml"
        constraints_file.write_text(yaml.dump({
            'club_name': 'Test Club',
            'tournament_name': 'Test Tournament',
            'tournament_date': 'Feb 2026',
        }))

        response = client.get('/')
        assert response.status_code == 200
        assert b'Test Club' in response.data
        assert b'Test Tournament' in response.data

    def test_dashboard_shows_standings_when_results_exist(self, client, temp_data_dir):
        """Test dashboard shows compact standings when pool results exist."""
        import app as app_module

        teams_file = temp_data_dir / "teams.yaml"
        teams_file.write_text(yaml.dump({
            'Pool A': {
                'teams': ['Team X', 'Team Y'],
                'advance': 1,
            }
        }))

        results_file = temp_data_dir / "results.yaml"
        monkeypatch_results = str(results_file)
        app_module.RESULTS_FILE = monkeypatch_results
        results_file.write_text(yaml.dump({
            'pool_play': {
                'Team X_vs_Team Y_Pool A': {
                    'completed': True,
                    'sets': [[21, 15]],
                    'winner': 'Team X',
                    'team1': 'Team X',
                    'team2': 'Team Y',
                }
            },
            'bracket': {},
        }))

        response = client.get('/')
        assert response.status_code == 200
        assert b'Team X' in response.data
        assert b'1-0' in response.data  # Win-Loss record

    def test_dashboard_shows_export_bar(self, client, temp_data_dir):
        """Test dashboard shows quick action buttons."""
        response = client.get('/')
        assert response.status_code == 200
        assert b'Quick Actions' in response.data
        assert b'Print View' in response.data
        assert b'Copy Live Link' in response.data


class TestExportScheduleCSV:
    """Tests for the CSV export API endpoint."""

    def test_csv_export_no_schedule(self, client, temp_data_dir):
        """Test CSV export returns 404 when no schedule exists."""
        import app as app_module
        app_module.SCHEDULE_FILE = str(temp_data_dir / "nonexistent_schedule.yaml")

        response = client.get('/api/export/schedule-csv')
        assert response.status_code == 404

    def test_csv_export_returns_csv(self, client, temp_data_dir):
        """Test CSV export returns valid CSV content."""
        import app as app_module

        schedule_file = temp_data_dir / "schedule.yaml"
        app_module.SCHEDULE_FILE = str(schedule_file)
        schedule_data = {
            'schedule': {
                'Day 1': {
                    '_time_slots': ['09:00'],
                    'Court 1': {
                        'matches': [{
                            'teams': ['Team A', 'Team B'],
                            'start_time': '09:00',
                            'end_time': '09:30',
                            'pool': 'Pool X',
                            'match_code': '',
                        }],
                        'time_to_match': {}
                    }
                }
            },
            'stats': {'total_matches': 1, 'scheduled_matches': 1, 'unscheduled_matches': 0}
        }
        schedule_file.write_text(yaml.dump(schedule_data))

        response = client.get('/api/export/schedule-csv')
        assert response.status_code == 200
        assert 'text/csv' in response.content_type
        content = response.data.decode('utf-8')
        assert 'Team A' in content
        assert 'Team B' in content
        assert 'Court 1' in content


class TestExportTournament:
    """Tests for the tournament ZIP export endpoint."""

    def test_export_returns_zip(self, client, temp_data_dir):
        """Test GET /api/export/tournament returns a valid ZIP file."""
        response = client.get('/api/export/tournament')
        assert response.status_code == 200
        assert 'application/zip' in response.content_type
        # Validate that the response body is a valid ZIP
        zf = zipfile.ZipFile(io.BytesIO(response.data))
        assert zf.testzip() is None  # No corrupt files

    def test_export_contains_existing_files(self, client, temp_data_dir):
        """Test the ZIP includes data files that exist on disk."""
        # teams.yaml and courts.csv were created by the fixture
        response = client.get('/api/export/tournament')
        zf = zipfile.ZipFile(io.BytesIO(response.data))
        names = zf.namelist()
        assert 'teams.yaml' in names
        assert 'courts.csv' in names

    def test_export_excludes_missing_files(self, client, temp_data_dir):
        """Test that files which don't exist are simply absent from the ZIP."""
        # results.yaml was NOT created by the fixture
        response = client.get('/api/export/tournament')
        zf = zipfile.ZipFile(io.BytesIO(response.data))
        names = zf.namelist()
        assert 'results.yaml' not in names

    def test_export_includes_logo(self, client, temp_data_dir):
        """Test that an uploaded logo is included in the export."""
        import app as app_module
        logo_path = temp_data_dir / "logo.png"
        logo_path.write_bytes(b'\x89PNG_FAKE_DATA')

        response = client.get('/api/export/tournament')
        zf = zipfile.ZipFile(io.BytesIO(response.data))
        assert 'logo.png' in zf.namelist()
        assert zf.read('logo.png') == b'\x89PNG_FAKE_DATA'

    def test_export_attachment_filename(self, client, temp_data_dir):
        """Test download filename contains 'tournament_export'."""
        response = client.get('/api/export/tournament')
        cd = response.headers.get('Content-Disposition', '')
        assert 'tournament_export' in cd
        assert '.zip' in cd


class TestImportTournament:
    """Tests for the tournament ZIP import endpoint."""

    def _make_zip(self, files: dict) -> io.BytesIO:
        """Helper: create an in-memory ZIP from a dict of {name: bytes}."""
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w') as zf:
            for name, data in files.items():
                zf.writestr(name, data)
        buf.seek(0)
        return buf

    def test_import_valid_zip(self, client, temp_data_dir):
        """Test importing a valid ZIP restores data files."""
        teams_content = "Pool X:\n  teams:\n    - Alpha\n  advance: 1\n"
        buf = self._make_zip({'teams.yaml': teams_content})

        response = client.post(
            '/api/import/tournament',
            data={'file': (buf, 'tournament.zip')},
            content_type='multipart/form-data',
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert b'imported successfully' in response.data

        # Verify the file was written
        pools = load_teams()
        assert 'Pool X' in pools
        assert pools['Pool X']['teams'] == ['Alpha']

    def test_import_no_file(self, client, temp_data_dir):
        """Test import with no file shows error."""
        response = client.post(
            '/api/import/tournament',
            data={},
            content_type='multipart/form-data',
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert b'No file selected' in response.data

    def test_import_invalid_file(self, client, temp_data_dir):
        """Test that uploading a non-ZIP file returns an error."""
        buf = io.BytesIO(b'this is not a zip')
        response = client.post(
            '/api/import/tournament',
            data={'file': (buf, 'bad.zip')},
            content_type='multipart/form-data',
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert b'not a valid ZIP' in response.data


class TestTournamentCRUDCornerCases:
    """Tests for tournament CRUD corner cases: no-tournament guard, session sync, YAML errors."""

    def _delete_all_tournaments(self, client, temp_data_dir):
        """Helper: delete every tournament via the API so the registry is empty."""
        user_dir = temp_data_dir.parent.parent  # e.g. …/users/testuser
        reg_file = user_dir / "tournaments.yaml"
        data = yaml.safe_load(reg_file.read_text()) or {'active': None, 'tournaments': []}
        for t in list(data.get('tournaments', [])):
            client.post('/api/tournaments/delete', data={'slug': t['slug']})

    def _create_tournament(self, client, name):
        """Helper: create a tournament via the API and return the response."""
        return client.post('/api/tournaments/create', data={'name': name}, follow_redirects=True)

    # ---- 1. Guard: no-tournament routes redirect ----

    def test_no_tournaments_redirects_to_tournaments_page(self, client, temp_data_dir):
        """When no tournaments exist, accessing /teams should redirect to /tournaments."""
        self._delete_all_tournaments(client, temp_data_dir)

        response = client.get('/teams')
        assert response.status_code == 302
        assert '/tournaments' in response.headers.get('Location', '')

    # ---- 2. Guard: tournament management routes still work ----

    def test_no_tournaments_allows_tournament_routes(self, client, temp_data_dir):
        """When no tournaments exist, /tournaments should return 200."""
        self._delete_all_tournaments(client, temp_data_dir)

        response = client.get('/tournaments')
        assert response.status_code == 200

    # ---- 3. Guard: can still create when empty ----

    def test_no_tournaments_allows_create_tournament(self, client, temp_data_dir):
        """When no tournaments exist, creating a new tournament should succeed."""
        self._delete_all_tournaments(client, temp_data_dir)

        response = client.post('/api/tournaments/create',
                               data={'name': 'Fresh Start'},
                               follow_redirects=True)
        assert response.status_code == 200

        # Verify the new tournament exists in the registry
        user_dir = temp_data_dir.parent.parent
        reg_file = user_dir / "tournaments.yaml"
        data = yaml.safe_load(reg_file.read_text())
        slugs = [t['slug'] for t in data.get('tournaments', [])]
        assert 'fresh-start' in slugs

    # ---- 4. Delete active → session switches to remaining ----

    def test_delete_active_tournament_switches_to_next(self, client, temp_data_dir):
        """Deleting the active tournament should set the remaining one as active in session."""
        # Create a second tournament (fixture already has 'default')
        self._create_tournament(client, 'Second')

        # The session should currently point to 'second' (just created)
        with client.session_transaction() as sess:
            assert sess.get('active_tournament') == 'second'

        # Delete the active tournament ('second')
        client.post('/api/tournaments/delete', data={'slug': 'second'})

        # After fix: session should fall back to 'default' (the remaining tournament)
        with client.session_transaction() as sess:
            active = sess.get('active_tournament')
            assert active == 'default'

    # ---- 5. Delete last → session cleared ----

    def test_delete_last_tournament_clears_session(self, client, temp_data_dir):
        """Deleting the very last tournament should clear active_tournament from session."""
        self._delete_all_tournaments(client, temp_data_dir)

        with client.session_transaction() as sess:
            # active_tournament should be absent or None
            assert sess.get('active_tournament') is None

    # ---- 6. Corrupted tournaments YAML ----

    def test_corrupted_tournaments_yaml_returns_default(self, client, temp_data_dir):
        """load_tournaments() should return default dict when YAML is corrupt."""
        from app import load_tournaments as _load_tournaments

        user_dir = temp_data_dir.parent.parent
        reg_file = user_dir / "tournaments.yaml"
        reg_file.write_text("{{{{invalid yaml: [unterminated")
        with app.test_request_context():
            from flask import g as _g
            _g.user_tournaments_file = str(reg_file)
            result = _load_tournaments()

        assert result == {'active': None, 'tournaments': []}

    # ---- 7. Corrupted users YAML ----

    def test_corrupted_users_yaml_returns_empty(self, client, temp_data_dir):
        """load_users() should return [] when YAML is corrupt."""
        import app as app_module
        from app import load_users as _load_users

        users_file = pathlib.Path(app_module.USERS_FILE)
        users_file.write_text("{{{{invalid yaml: [unterminated")

        result = _load_users()
        assert result == []


class TestImportTournamentEdgeCases:
    """Additional import edge case tests (originally in TestImportTournament)."""

    def _make_zip(self, files: dict) -> io.BytesIO:
        """Helper: create an in-memory ZIP from a dict of {name: bytes}."""
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w') as zf:
            for name, data in files.items():
                zf.writestr(name, data)
        buf.seek(0)
        return buf

    def test_import_rejects_unknown_zip(self, client, temp_data_dir):
        """Test that a ZIP without any recognised tournament files is rejected."""
        buf = self._make_zip({'random.txt': 'hello'})
        response = client.post(
            '/api/import/tournament',
            data={'file': (buf, 'unknown.zip')},
            content_type='multipart/form-data',
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert b'does not appear to contain tournament data' in response.data

    def test_import_rejects_path_traversal(self, client, temp_data_dir):
        """Test that ZIP entries with path traversal are rejected."""
        buf = self._make_zip({'../teams.yaml': 'bad', 'teams.yaml': 'ok'})
        response = client.post(
            '/api/import/tournament',
            data={'file': (buf, 'evil.zip')},
            content_type='multipart/form-data',
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert b'unsafe file paths' in response.data

    def test_import_overwrites_existing(self, client, temp_data_dir):
        """Test that import replaces existing data files."""
        # Write initial data
        (temp_data_dir / "teams.yaml").write_text("Pool Old:\n  teams: []\n  advance: 2\n")

        # Import new data
        new_content = "Pool New:\n  teams:\n    - Bravo\n  advance: 3\n"
        buf = self._make_zip({'teams.yaml': new_content})
        client.post(
            '/api/import/tournament',
            data={'file': (buf, 'new.zip')},
            content_type='multipart/form-data',
            follow_redirects=True,
        )

        pools = load_teams()
        assert 'Pool Old' not in pools
        assert 'Pool New' in pools
        assert pools['Pool New']['teams'] == ['Bravo']

    def test_import_handles_logo(self, client, temp_data_dir):
        """Test that old logo is deleted and new one extracted on import."""
        # Create an existing logo
        old_logo = temp_data_dir / "logo.jpg"
        old_logo.write_bytes(b'OLD')

        # Import with a new logo (different extension)
        buf = self._make_zip({
            'teams.yaml': 'Pool Z:\n  teams: []\n  advance: 2\n',
            'logo.png': b'NEW_PNG',
        })
        client.post(
            '/api/import/tournament',
            data={'file': (buf, 'logo_import.zip')},
            content_type='multipart/form-data',
            follow_redirects=True,
        )

        # Old logo should be gone, new one present
        assert not old_logo.exists()
        new_logo = temp_data_dir / "logo.png"
        assert new_logo.exists()
        assert new_logo.read_bytes() == b'NEW_PNG'

    def test_roundtrip_export_import(self, client, temp_data_dir):
        """Test that exporting then importing produces identical data."""
        original_teams = "Pool RT:\n  teams:\n    - Charlie\n    - Delta\n  advance: 2\n"
        original_courts = "court_name,start_time,end_time\nCourt 1,09:00,18:00\n"
        (temp_data_dir / "teams.yaml").write_text(original_teams)
        (temp_data_dir / "courts.csv").write_text(original_courts)

        # Export
        export_resp = client.get('/api/export/tournament')
        assert export_resp.status_code == 200

        # Wipe current data
        (temp_data_dir / "teams.yaml").write_text("")
        (temp_data_dir / "courts.csv").write_text("court_name,start_time,end_time\n")

        # Import the exported ZIP
        buf = io.BytesIO(export_resp.data)
        client.post(
            '/api/import/tournament',
            data={'file': (buf, 'roundtrip.zip')},
            content_type='multipart/form-data',
            follow_redirects=True,
        )

        # Data should match originals
        assert (temp_data_dir / "teams.yaml").read_text() == original_teams
        assert (temp_data_dir / "courts.csv").read_text() == original_courts


class TestPublicLive:
    """Tests for public (no-auth) live tournament page."""

    def test_public_live_returns_200_without_login(self, temp_data_dir):
        """Public live page should be accessible without login."""
        with app.test_client() as anon_client:
            response = anon_client.get('/live/testuser/default')
            assert response.status_code == 200

    def test_public_live_html_returns_200_without_login(self, temp_data_dir):
        """Public live-html API should work without login."""
        with app.test_client() as anon_client:
            response = anon_client.get('/api/live-html/testuser/default')
            assert response.status_code == 200

    def test_public_live_stream_returns_200_without_login(self, temp_data_dir):
        """Public SSE stream should connect without login."""
        with app.test_client() as anon_client:
            response = anon_client.get('/api/live-stream/testuser/default')
            assert response.status_code == 200
            assert response.content_type.startswith('text/event-stream')

    def test_public_live_404_for_nonexistent_user(self, temp_data_dir):
        """Public live should 404 for a user that doesn't exist."""
        with app.test_client() as anon_client:
            response = anon_client.get('/live/nobody/default')
            assert response.status_code == 404

    def test_public_live_404_for_nonexistent_tournament(self, temp_data_dir):
        """Public live should 404 for a tournament that doesn't exist."""
        with app.test_client() as anon_client:
            response = anon_client.get('/live/testuser/nonexistent')
            assert response.status_code == 404

    def test_public_live_rejects_path_traversal(self, temp_data_dir):
        """Public live should reject path traversal attempts."""
        with app.test_client() as anon_client:
            response = anon_client.get('/live/testuser/../admin')
            # Flask may return 404 or the route won't match — either way, not 200
            assert response.status_code != 200

    def test_public_live_passes_public_mode(self, temp_data_dir):
        """Public live should pass public_mode=True to template."""
        with app.test_client() as anon_client:
            response = anon_client.get('/live/testuser/default')
            assert response.status_code == 200
            # The response should contain the public API URLs
            assert b'/api/live-html/testuser/default' in response.data or b'live-html' in response.data


def _make_user_zip(tournaments_yaml_content: dict, tournament_files: dict) -> io.BytesIO:
    """Build a user export ZIP.

    tournaments_yaml_content: dict for tournaments.yaml
    tournament_files: {slug: {filename: content_bytes}}
    """
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as zf:
        zf.writestr('tournaments.yaml', yaml.dump(tournaments_yaml_content))
        for slug, files in tournament_files.items():
            for fname, content in files.items():
                zf.writestr(f'{slug}/{fname}', content)
    buf.seek(0)
    return buf


class TestUserExportImport:
    """Tests for user-level export/import endpoints (/api/export/user, /api/import/user)."""

    def test_export_user_produces_valid_zip(self, client, temp_data_dir):
        """GET /api/export/user returns a ZIP containing tournaments.yaml and default/ entries."""
        response = client.get('/api/export/user')
        assert response.status_code == 200
        assert 'application/zip' in response.content_type

        zf = zipfile.ZipFile(io.BytesIO(response.data))
        assert zf.testzip() is None
        names = zf.namelist()
        assert 'tournaments.yaml' in names
        # At least one entry under the default/ tournament subfolder
        assert any(n.startswith('default/') for n in names)

    def test_export_user_includes_all_tournaments(self, client, temp_data_dir):
        """Export ZIP contains entries for every tournament in the registry."""
        # Create a second tournament directory with a teams.yaml
        second_dir = temp_data_dir.parent / "second"
        second_dir.mkdir(parents=True, exist_ok=True)
        (second_dir / "teams.yaml").write_text(
            yaml.dump({'Pool S': {'teams': ['S1', 'S2'], 'advance': 1}})
        )

        # Update user's tournaments.yaml to include both tournaments
        user_reg = temp_data_dir.parent.parent / "tournaments.yaml"
        user_reg.write_text(yaml.dump({
            'active': 'default',
            'tournaments': [
                {'slug': 'default', 'name': 'Default'},
                {'slug': 'second', 'name': 'Second'},
            ]
        }, default_flow_style=False))

        response = client.get('/api/export/user')
        assert response.status_code == 200

        zf = zipfile.ZipFile(io.BytesIO(response.data))
        names = zf.namelist()
        assert any(n.startswith('default/') for n in names)
        assert any(n.startswith('second/') for n in names)

    def test_import_user_creates_new_tournament(self, client, temp_data_dir):
        """Importing a ZIP with a new tournament creates its directory and files."""
        tournaments_content = {
            'active': 'imported',
            'tournaments': [{'slug': 'imported', 'name': 'Imported'}],
        }
        tournament_files = {
            'imported': {
                'teams.yaml': yaml.dump({'Pool I': {'teams': ['I1', 'I2'], 'advance': 1}}),
            },
        }
        buf = _make_user_zip(tournaments_content, tournament_files)

        response = client.post(
            '/api/import/user',
            data={'file': (buf, 'user_backup.zip')},
            content_type='multipart/form-data',
            follow_redirects=True,
        )
        # Should succeed (200 after redirect, or 302)
        assert response.status_code in (200, 302)

        # The tournament directory and teams.yaml should exist
        imported_dir = temp_data_dir.parent / "imported"
        assert imported_dir.is_dir()
        assert (imported_dir / "teams.yaml").exists()

    def test_import_user_overwrites_existing(self, client, temp_data_dir):
        """Importing a ZIP overwrites files in existing tournaments."""
        original_content = "Pool Old:\n  teams:\n    - OldTeam\n  advance: 1\n"
        (temp_data_dir / "teams.yaml").write_text(original_content)

        new_content = yaml.dump({'Pool New': {'teams': ['NewTeam'], 'advance': 1}})
        tournaments_content = {
            'active': 'default',
            'tournaments': [{'slug': 'default', 'name': 'Default'}],
        }
        tournament_files = {
            'default': {'teams.yaml': new_content},
        }
        buf = _make_user_zip(tournaments_content, tournament_files)

        client.post(
            '/api/import/user',
            data={'file': (buf, 'overwrite.zip')},
            content_type='multipart/form-data',
            follow_redirects=True,
        )

        written = (temp_data_dir / "teams.yaml").read_text()
        assert 'Pool New' in written
        assert 'OldTeam' not in written

    def test_import_user_rejects_malicious_zip(self, client, temp_data_dir):
        """A ZIP with path traversal entries should be rejected."""
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w') as zf:
            zf.writestr('tournaments.yaml', yaml.dump({
                'active': 'evil',
                'tournaments': [{'slug': 'evil', 'name': 'Evil'}],
            }))
            zf.writestr('../evil/teams.yaml', 'Pool Evil:\n  teams: [Hacker]\n  advance: 1\n')
        buf.seek(0)

        response = client.post(
            '/api/import/user',
            data={'file': (buf, 'evil.zip')},
            content_type='multipart/form-data',
            follow_redirects=True,
        )

        # Should not succeed cleanly — either error status or flash rejection
        # The malicious path should NOT have been extracted
        evil_dir = temp_data_dir.parent.parent.parent / "evil"
        assert not evil_dir.exists(), "Path traversal entry was extracted — security vulnerability!"

    def test_import_user_preserves_unmentioned_tournaments(self, client, temp_data_dir):
        """Tournaments not in the import ZIP should remain untouched."""
        # Confirm "default" tournament exists with some data
        (temp_data_dir / "teams.yaml").write_text(
            yaml.dump({'Pool D': {'teams': ['D1'], 'advance': 1}})
        )

        # Import a ZIP that only mentions a new "imported" tournament
        tournaments_content = {
            'active': 'imported',
            'tournaments': [{'slug': 'imported', 'name': 'Imported'}],
        }
        tournament_files = {
            'imported': {
                'teams.yaml': yaml.dump({'Pool I': {'teams': ['I1'], 'advance': 1}}),
            },
        }
        buf = _make_user_zip(tournaments_content, tournament_files)

        client.post(
            '/api/import/user',
            data={'file': (buf, 'partial.zip')},
            content_type='multipart/form-data',
            follow_redirects=True,
        )

        # The default tournament directory and its data should still exist
        assert temp_data_dir.is_dir()
        assert (temp_data_dir / "teams.yaml").exists()
        existing = (temp_data_dir / "teams.yaml").read_text()
        assert 'Pool D' in existing

    def test_import_after_delete_all_sets_active(self, client, temp_data_dir):
        """After deleting all tournaments, importing sets an active tournament so navigation works."""
        # Export current tournaments
        export_resp = client.get('/api/export/user')
        assert export_resp.status_code == 200
        zip_data = export_resp.data

        # Delete all tournaments
        client.post('/api/tournaments/delete', data={'slug': 'default'})
        # Verify no active tournament
        user_reg = temp_data_dir.parent.parent / "tournaments.yaml"
        reg = yaml.safe_load(user_reg.read_text())
        assert not reg.get('tournaments') or len(reg['tournaments']) == 0

        # Import the exported ZIP
        buf = io.BytesIO(zip_data)
        client.post(
            '/api/import/user',
            data={'file': (buf, 'backup.zip')},
            content_type='multipart/form-data',
        )

        # Verify an active tournament is set in tournaments.yaml
        reg = yaml.safe_load(user_reg.read_text())
        assert reg.get('active') is not None
        assert len(reg.get('tournaments', [])) > 0

        # Verify navigating to a tab does NOT redirect to /tournaments
        resp = client.get('/teams', follow_redirects=False)
        assert resp.status_code == 200


def _make_site_zip(secret_key_content: bytes = b'test-secret-key-data',
                   users_yaml_content: dict = None,
                   user_tree: dict = None) -> io.BytesIO:
    """Build a site-level export ZIP.

    secret_key_content: raw bytes for .secret_key entry
    users_yaml_content: dict to serialize as users.yaml
    user_tree: {relative_path: content_str} for entries under users/
    """
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as zf:
        if secret_key_content is not None:
            zf.writestr('.secret_key', secret_key_content)
        if users_yaml_content is not None:
            zf.writestr('users.yaml', yaml.dump(users_yaml_content, default_flow_style=False))
        if user_tree:
            for rel_path, content in user_tree.items():
                zf.writestr(f'users/{rel_path}', content)
    buf.seek(0)
    return buf


class TestSiteExportImport:
    """Tests for admin-only site-wide export/import."""

    def _login_as_admin(self, client, temp_data_dir):
        """Set up admin user in the test environment and switch session to admin."""
        import app as app_module
        from werkzeug.security import generate_password_hash

        # Add admin to users.yaml if not present
        users_file = pathlib.Path(app_module.USERS_FILE)
        users_data = yaml.safe_load(users_file.read_text()) or {'users': []}
        if not any(u['username'] == 'admin' for u in users_data.get('users', [])):
            users_data['users'].append({
                'username': 'admin',
                'password_hash': generate_password_hash('admin'),
                'created': '2026-01-01'
            })
            users_file.write_text(yaml.dump(users_data, default_flow_style=False))

        # Create admin user directory with a default tournament
        users_dir = pathlib.Path(app_module.USERS_DIR)
        admin_dir = users_dir / "admin"
        admin_default = admin_dir / "tournaments" / "default"
        admin_default.mkdir(parents=True, exist_ok=True)
        (admin_dir / "tournaments.yaml").write_text(yaml.dump({
            'active': 'default',
            'tournaments': [{'slug': 'default', 'name': 'Admin Default'}]
        }, default_flow_style=False))
        (admin_default / "teams.yaml").write_text("")
        (admin_default / "courts.csv").write_text("court_name,start_time,end_time\n")
        (admin_default / "constraints.yaml").write_text("")

        # Ensure .secret_key exists in site root (parent of USERS_FILE)
        site_root = pathlib.Path(app_module.USERS_FILE).parent
        secret_key_path = site_root / ".secret_key"
        if not secret_key_path.exists():
            secret_key_path.write_bytes(b'test-secret-key-data')

        # Switch session to admin
        with client.session_transaction() as sess:
            sess['user'] = 'admin'

    def test_export_site_non_admin_forbidden(self, client, temp_data_dir):
        """Non-admin user cannot export site."""
        response = client.get('/api/export/site')
        # testuser is logged in — should be 403 or redirect, not 200
        assert response.status_code in (302, 303, 403)

    def test_export_site_admin_produces_valid_zip(self, client, temp_data_dir):
        """Admin export returns valid ZIP with correct structure."""
        self._login_as_admin(client, temp_data_dir)
        response = client.get('/api/export/site')
        assert response.status_code == 200
        assert 'application/zip' in response.content_type

        zf = zipfile.ZipFile(io.BytesIO(response.data))
        assert zf.testzip() is None
        names = zf.namelist()
        assert 'users.yaml' in names
        assert any(n.startswith('users/') for n in names)

    def test_export_site_includes_secret_key(self, client, temp_data_dir):
        """Export ZIP contains .secret_key file."""
        self._login_as_admin(client, temp_data_dir)
        response = client.get('/api/export/site')
        assert response.status_code == 200

        zf = zipfile.ZipFile(io.BytesIO(response.data))
        assert '.secret_key' in zf.namelist()
        content = zf.read('.secret_key')
        assert len(content) > 0

    def test_export_site_includes_users_data(self, client, temp_data_dir):
        """Export ZIP contains users.yaml and user directories."""
        self._login_as_admin(client, temp_data_dir)
        response = client.get('/api/export/site')
        assert response.status_code == 200

        zf = zipfile.ZipFile(io.BytesIO(response.data))
        names = zf.namelist()
        assert 'users.yaml' in names
        # Both testuser and admin should have entries in the ZIP
        assert any('testuser' in n for n in names)
        assert any('admin' in n for n in names)

    def test_import_site_non_admin_forbidden(self, client, temp_data_dir):
        """Non-admin user cannot import site."""
        buf = _make_site_zip(
            users_yaml_content={'users': [
                {'username': 'testuser', 'password_hash': 'x', 'created': '2026-01-01'}
            ]},
            user_tree={
                'testuser/tournaments.yaml': yaml.dump({
                    'active': 'default', 'tournaments': []
                })
            }
        )
        response = client.post(
            '/api/import/site',
            data={'file': (buf, 'site_backup.zip')},
            content_type='multipart/form-data',
        )
        # testuser is not admin — should be 403 or redirect
        assert response.status_code in (302, 303, 403)

    def test_import_site_replaces_data(self, client, temp_data_dir):
        """Admin import replaces existing user data with ZIP contents."""
        import app as app_module
        self._login_as_admin(client, temp_data_dir)

        users_dir = pathlib.Path(app_module.USERS_DIR)

        # Plant a marker in existing user dir to verify full wipe
        marker = users_dir / "testuser" / "marker.txt"
        marker.write_text("should be deleted")

        # Build a site ZIP with only a "newuser"
        new_users = {'users': [
            {'username': 'newuser', 'password_hash': 'hash123', 'created': '2026-01-01'}
        ]}
        user_tree = {
            'newuser/tournaments.yaml': yaml.dump({
                'active': 'default',
                'tournaments': [{'slug': 'default', 'name': 'New'}]
            }),
            'newuser/tournaments/default/teams.yaml': yaml.dump(
                {'Pool N': {'teams': ['N1'], 'advance': 1}}
            ),
        }
        buf = _make_site_zip(users_yaml_content=new_users, user_tree=user_tree)

        response = client.post(
            '/api/import/site',
            data={'file': (buf, 'site_backup.zip')},
            content_type='multipart/form-data',
            follow_redirects=True,
        )
        assert response.status_code in (200, 302)

        # Full replace: old testuser data should be wiped
        assert not marker.exists(), "Old user data was not wiped — import should do full replace"

        # New user directory should exist with correct files
        assert (users_dir / "newuser").is_dir()
        assert (users_dir / "newuser" / "tournaments" / "default" / "teams.yaml").exists()

    def test_import_site_rejects_malicious_zip(self, client, temp_data_dir):
        """ZIP with path traversal entries is rejected."""
        import app as app_module
        self._login_as_admin(client, temp_data_dir)

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w') as zf:
            zf.writestr('users.yaml', yaml.dump({'users': []}))
            zf.writestr('../../../etc/evil.txt', 'malicious content')
        buf.seek(0)

        users_dir = pathlib.Path(app_module.USERS_DIR)

        response = client.post(
            '/api/import/site',
            data={'file': (buf, 'evil.zip')},
            content_type='multipart/form-data',
            follow_redirects=True,
        )

        # The path traversal entry must NOT be extracted
        evil_path = users_dir.parent.parent.parent / "etc" / "evil.txt"
        assert not evil_path.exists(), "Path traversal entry was extracted — security vulnerability!"

    def test_import_site_rejects_missing_users_yaml(self, client, temp_data_dir):
        """ZIP without users.yaml is rejected."""
        self._login_as_admin(client, temp_data_dir)

        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w') as zf:
            zf.writestr('.secret_key', b'somekey')
            zf.writestr('users/testuser/tournaments.yaml', 'active: default')
        buf.seek(0)

        response = client.post(
            '/api/import/site',
            data={'file': (buf, 'no_users.zip')},
            content_type='multipart/form-data',
            follow_redirects=True,
        )

        # Should reject — either 400 or error flash
        page_text = response.data.decode('utf-8', errors='replace').lower()
        assert response.status_code == 400 or 'users.yaml' in page_text or 'error' in page_text or 'invalid' in page_text

    def test_import_site_clears_session(self, client, temp_data_dir):
        """After import, session is cleared (user must re-login)."""
        self._login_as_admin(client, temp_data_dir)

        # Confirm we're logged in
        with client.session_transaction() as sess:
            assert sess.get('user') == 'admin'

        # Import a valid site ZIP
        new_users = {'users': [
            {'username': 'admin', 'password_hash': 'hash', 'created': '2026-01-01'}
        ]}
        user_tree = {
            'admin/tournaments.yaml': yaml.dump({
                'active': 'default',
                'tournaments': [{'slug': 'default', 'name': 'Default'}]
            }),
            'admin/tournaments/default/teams.yaml': '',
        }
        buf = _make_site_zip(users_yaml_content=new_users, user_tree=user_tree)

        response = client.post(
            '/api/import/site',
            data={'file': (buf, 'site_backup.zip')},
            content_type='multipart/form-data',
        )

        # Session should be cleared — next request to a protected page redirects to login
        resp = client.get('/', follow_redirects=False)
        assert resp.status_code in (302, 303)
        assert 'login' in resp.headers.get('Location', '').lower()


class TestDeleteAccount:
    """Tests for POST /api/delete-account endpoint."""

    def test_delete_account_success(self, client, temp_data_dir):
        """Deleting account removes user from users.yaml, removes dir, clears session."""
        import app as app_module

        users_file = pathlib.Path(app_module.USERS_FILE)
        users_dir = pathlib.Path(app_module.USERS_DIR)
        user_dir = users_dir / "testuser"

        # Preconditions
        assert user_dir.exists()
        users_data = yaml.safe_load(users_file.read_text())
        assert any(u['username'] == 'testuser' for u in users_data['users'])

        response = client.post('/api/delete-account')
        assert response.status_code == 200

        data = response.get_json()
        assert data['success'] is True
        assert 'redirect' in data

        # User removed from users.yaml
        users_data = yaml.safe_load(users_file.read_text())
        remaining = [u['username'] for u in users_data.get('users', [])]
        assert 'testuser' not in remaining

        # User directory removed
        assert not user_dir.exists()

        # Session cleared — subsequent request redirects to login
        resp = client.get('/teams', follow_redirects=False)
        assert resp.status_code in (302, 303)
        assert 'login' in resp.headers.get('Location', '').lower()

    def test_delete_account_removes_all_tournaments(self, client, temp_data_dir):
        """Deleting account removes the entire user directory tree including extra tournaments."""
        import app as app_module

        users_dir = pathlib.Path(app_module.USERS_DIR)
        user_dir = users_dir / "testuser"
        tournaments_dir = user_dir / "tournaments"

        # Create a second tournament directory
        second_tournament = tournaments_dir / "second-tourney"
        second_tournament.mkdir(parents=True, exist_ok=True)
        (second_tournament / "teams.yaml").write_text("")
        assert second_tournament.exists()

        response = client.post('/api/delete-account')
        assert response.status_code == 200

        # Entire user directory tree is gone
        assert not user_dir.exists()

    def test_delete_account_admin_prevented(self, client, temp_data_dir):
        """Admin user cannot delete their own account."""
        import app as app_module
        from werkzeug.security import generate_password_hash

        users_file = pathlib.Path(app_module.USERS_FILE)
        users_dir = pathlib.Path(app_module.USERS_DIR)

        # Add admin to users.yaml
        users_data = yaml.safe_load(users_file.read_text()) or {'users': []}
        if not any(u['username'] == 'admin' for u in users_data.get('users', [])):
            users_data['users'].append({
                'username': 'admin',
                'password_hash': generate_password_hash('admin'),
                'created': '2026-01-01'
            })
            users_file.write_text(yaml.dump(users_data, default_flow_style=False))

        # Create admin user directory tree
        admin_dir = users_dir / "admin"
        admin_default = admin_dir / "tournaments" / "default"
        admin_default.mkdir(parents=True, exist_ok=True)
        (admin_dir / "tournaments.yaml").write_text(yaml.dump({
            'active': 'default',
            'tournaments': [{'slug': 'default', 'name': 'Admin Default'}]
        }, default_flow_style=False))
        (admin_default / "teams.yaml").write_text("")
        (admin_default / "courts.csv").write_text("court_name,start_time,end_time\n")
        (admin_default / "constraints.yaml").write_text("")

        # Switch session to admin
        with client.session_transaction() as sess:
            sess['user'] = 'admin'

        response = client.post('/api/delete-account')
        assert response.status_code == 403

        # Admin still in users.yaml
        users_data = yaml.safe_load(users_file.read_text())
        assert any(u['username'] == 'admin' for u in users_data['users'])

        # Admin directory still exists
        assert admin_dir.exists()

    def test_delete_account_requires_login(self, client, temp_data_dir):
        """Unauthenticated request is redirected to login."""
        # Log out first
        client.get('/logout')

        response = client.post('/api/delete-account', follow_redirects=False)
        assert response.status_code in (302, 303)
        assert 'login' in response.headers.get('Location', '').lower()

    def test_delete_account_other_users_unaffected(self, client, temp_data_dir):
        """Deleting testuser does not affect other users."""
        import app as app_module

        users_file = pathlib.Path(app_module.USERS_FILE)
        users_dir = pathlib.Path(app_module.USERS_DIR)

        # Create a second user in users.yaml
        users_data = yaml.safe_load(users_file.read_text()) or {'users': []}
        users_data['users'].append({
            'username': 'otheruser',
            'password_hash': 'somehash',
            'created': '2026-01-01'
        })
        users_file.write_text(yaml.dump(users_data, default_flow_style=False))

        # Create otheruser's directory
        other_dir = users_dir / "otheruser"
        other_tournaments = other_dir / "tournaments" / "default"
        other_tournaments.mkdir(parents=True, exist_ok=True)
        (other_dir / "tournaments.yaml").write_text(yaml.dump({
            'active': 'default',
            'tournaments': [{'slug': 'default', 'name': 'Other Default'}]
        }, default_flow_style=False))
        (other_tournaments / "teams.yaml").write_text("")

        response = client.post('/api/delete-account')
        assert response.status_code == 200

        # otheruser still in users.yaml
        users_data = yaml.safe_load(users_file.read_text())
        assert any(u['username'] == 'otheruser' for u in users_data['users'])

        # otheruser directory still exists
        assert other_dir.exists()
        assert (other_tournaments / "teams.yaml").exists()


class TestShowTestButtons:
    """Tests for show_test_buttons constraint feature."""

    def test_show_test_buttons_default_false(self, client, temp_data_dir):
        """Test that show_test_buttons defaults to False in constraints."""
        constraints = load_constraints()
        assert constraints.get('show_test_buttons') is False

    def test_show_test_buttons_toggle_on(self, client, temp_data_dir):
        """Test POSTing with show_test_buttons in form data saves it as True."""
        response = client.post('/constraints', data={
            'action': 'update_general',
            'match_duration': '25',
            'days_number': '1',
            'min_break': '5',
            'day_end_time': '02:00',
            'bracket_type': 'double',
            'scoring_format': 'single_set',
            'show_test_buttons': 'on',
        }, follow_redirects=True)
        assert response.status_code == 200

        constraints = load_constraints()
        assert constraints['show_test_buttons'] is True

    def test_show_test_buttons_toggle_off(self, client, temp_data_dir):
        """Test that omitting show_test_buttons from form data (unchecked checkbox) saves it as False."""
        # First enable it
        constraints_file = temp_data_dir / "constraints.yaml"
        constraints_file.write_text(yaml.dump({'show_test_buttons': True}))

        # POST without show_test_buttons (simulates unchecked checkbox)
        response = client.post('/constraints', data={
            'action': 'update_general',
            'match_duration': '25',
            'days_number': '1',
            'min_break': '5',
            'day_end_time': '02:00',
            'bracket_type': 'double',
            'scoring_format': 'single_set',
        }, follow_redirects=True)
        assert response.status_code == 200

        constraints = load_constraints()
        assert constraints['show_test_buttons'] is False

    def test_teams_page_hides_test_button_by_default(self, client, temp_data_dir):
        """Test that GET /teams does NOT show the test button when show_test_buttons is False."""
        response = client.get('/teams')
        assert response.status_code == 200
        assert b'onclick="loadTestTeams()"' not in response.data

    def test_teams_page_shows_test_button_when_enabled(self, client, temp_data_dir):
        """Test that GET /teams shows the test button when show_test_buttons is True."""
        constraints_file = temp_data_dir / "constraints.yaml"
        constraints_file.write_text(yaml.dump({'show_test_buttons': True}))

        response = client.get('/teams')
        assert response.status_code == 200
        assert b'onclick="loadTestTeams()"' in response.data
