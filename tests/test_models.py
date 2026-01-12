"""
Unit tests for the data models (Team, Court, Constraint).
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from core.models import Team, Court, Constraint


class TestTeam:
    """Tests for the Team model."""
    
    def test_team_creation_with_name(self):
        """Test creating a team with just a name."""
        team = Team(name="Test Team")
        assert team.name == "Test Team"
        assert team.attributes == {}
    
    def test_team_creation_with_attributes(self):
        """Test creating a team with attributes."""
        team = Team(name="Test Team", attributes={"pool": "A", "seed": 1})
        assert team.name == "Test Team"
        assert team.attributes["pool"] == "A"
        assert team.attributes["seed"] == 1
    
    def test_team_repr(self):
        """Test team string representation."""
        team = Team(name="Test Team", attributes={"pool": "A"})
        repr_str = repr(team)
        assert "Test Team" in repr_str
        assert "pool" in repr_str


class TestCourt:
    """Tests for the Court model."""
    
    def test_court_creation(self):
        """Test creating a court."""
        court = Court(name="Court 1", start_time="08:00")
        assert court.name == "Court 1"
        assert court.start_time == "08:00"
        assert court.matches == []
    
    def test_court_repr(self):
        """Test court string representation."""
        court = Court(name="Court 1", start_time="09:00")
        repr_str = repr(court)
        assert "Court 1" in repr_str
        assert "09:00" in repr_str


class TestConstraint:
    """Tests for the Constraint model."""
    
    def test_constraint_creation(self):
        """Test creating a constraint."""
        constraint = Constraint(type="time_preference", value="after_10am")
        assert constraint.type == "time_preference"
        assert constraint.value == "after_10am"
    
    def test_constraint_repr(self):
        """Test constraint string representation."""
        constraint = Constraint(type="break_time", value=15)
        repr_str = repr(constraint)
        assert "break_time" in repr_str
        assert "15" in repr_str
