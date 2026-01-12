"""
Shared pytest fixtures for tournament allocator tests.
"""
import pytest
import sys
import os

# Add src directory to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from core.models import Team, Court, Constraint


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
