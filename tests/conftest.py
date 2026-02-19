"""
Shared pytest fixtures for tournament allocator tests.

Running tests:
    pytest tests/                  - full suite (~2 min)
    pytest tests/ -m "not slow"   - fast subset (~10s, for small changes)
"""
import pytest
import sys
import os
import yaml

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from core.models import Team, Court, Constraint


@pytest.fixture
def client():
    """Create an authenticated test client."""
    from app import app
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

    return str(tournament_data)


@pytest.fixture
def sample_teams():
    """Create a simple set of teams in two pools."""
    return [
        Team(name="Team A", attributes={"pool": "pool1"}),
        Team(name="Team B", attributes={"pool": "pool1"}),
        Team(name="Team C", attributes={"pool": "pool1"}),
        Team(name="Team D", attributes={"pool": "pool2"}),
        Team(name="Team E", attributes={"pool": "pool2"}),
    ]


@pytest.fixture
def sample_courts():
    """Create a simple set of courts."""
    return [
        Court(name="Court 1", start_time="08:00"),
        Court(name="Court 2", start_time="08:00"),
    ]


@pytest.fixture
def basic_constraints():
    """Basic constraints with no team-specific requirements."""
    return {
        "match_duration_minutes": 60,
        "days_number": 1,
        "min_break_between_matches_minutes": 15,
        "time_slot_increment_minutes": 15,
        "day_end_time_limit": "22:00",
        "team_specific_constraints": [],
        "general_constraints": [],
        "tournament_settings": {
            "type": "pool_play",
            "advancement_rules": {
                "top_teams_per_pool_to_advance": 2
            }
        }
    }


@pytest.fixture
def constraints_with_team_preferences():
    """Constraints including team-specific time preferences."""
    return {
        "match_duration_minutes": 60,
        "days_number": 2,
        "min_break_between_matches_minutes": 15,
        "time_slot_increment_minutes": 15,
        "day_end_time_limit": "22:00",
        "team_specific_constraints": [
            {"team_name": "Team A", "play_after": "10:00", "note": "Team A prefers late start"},
            {"team_name": "Team B", "play_before": "14:00", "note": "Team B prefers early games"},
        ],
        "general_constraints": [],
        "tournament_settings": {
            "type": "pool_play"
        }
    }


@pytest.fixture
def large_tournament_teams():
    """Create a larger tournament with multiple pools."""
    teams = []
    pools = ["pool1", "pool2", "pool3"]
    for pool in pools:
        for i in range(4):
            teams.append(Team(name=f"{pool}_Team{i+1}", attributes={"pool": pool}))
    return teams


@pytest.fixture
def four_courts():
    """Create four courts for larger tournaments."""
    return [
        Court(name="Court 1", start_time="08:00"),
        Court(name="Court 2", start_time="08:00"),
        Court(name="Court 3", start_time="09:00"),
        Court(name="Court 4", start_time="09:00"),
    ]


@pytest.fixture
def tight_constraints():
    """Constraints that create a tight scheduling scenario."""
    return {
        "match_duration_minutes": 60,
        "days_number": 1,
        "min_break_between_matches_minutes": 30,
        "time_slot_increment_minutes": 15,
        "day_end_time_limit": "12:00",  # Very short day
        "team_specific_constraints": [],
        "general_constraints": [],
        "tournament_settings": {
            "type": "pool_play"
        }
    }
