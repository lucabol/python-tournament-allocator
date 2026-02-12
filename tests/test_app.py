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
