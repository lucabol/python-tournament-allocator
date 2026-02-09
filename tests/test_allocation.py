"""
Unit tests for the AllocationManager class.
"""
import pytest
import datetime
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from core.allocation import AllocationManager
from core.models import Team, Court


class TestAllocationManagerHelpers:
    """Tests for helper methods in AllocationManager."""
    
    def test_parse_time(self, sample_teams, sample_courts, basic_constraints):
        """Test time string parsing."""
        manager = AllocationManager(sample_teams, sample_courts, basic_constraints)
        
        time_obj = manager._parse_time("08:00")
        assert time_obj.hour == 8
        assert time_obj.minute == 0
        
        time_obj = manager._parse_time("14:30")
        assert time_obj.hour == 14
        assert time_obj.minute == 30
    
    def test_datetime_from_time(self, sample_teams, sample_courts, basic_constraints):
        """Test converting time to datetime with base date."""
        manager = AllocationManager(sample_teams, sample_courts, basic_constraints)
        
        time_obj = manager._parse_time("10:00")
        base_date = datetime.date(2026, 1, 15)
        dt = manager._datetime_from_time(time_obj, base_date)
        
        assert dt.year == 2026
        assert dt.month == 1
        assert dt.day == 15
        assert dt.hour == 10
        assert dt.minute == 0


class TestCourtAvailability:
    """Tests for court availability checking."""
    
    def test_court_available_empty_schedule(self, sample_teams, sample_courts, basic_constraints):
        """Test that court is available when schedule is empty."""
        manager = AllocationManager(sample_teams, sample_courts, basic_constraints)
        court = sample_courts[0]
        
        base_date = datetime.date.today()
        start = datetime.datetime.combine(base_date, datetime.time(9, 0))
        end = datetime.datetime.combine(base_date, datetime.time(10, 0))
        
        assert manager._check_court_availability(court, start, end) is True
    
    def test_court_unavailable_before_open(self, sample_teams, sample_courts, basic_constraints):
        """Test that court is unavailable before its start time."""
        manager = AllocationManager(sample_teams, sample_courts, basic_constraints)
        court = sample_courts[0]  # Opens at 08:00
        
        base_date = datetime.date.today()
        start = datetime.datetime.combine(base_date, datetime.time(7, 0))
        end = datetime.datetime.combine(base_date, datetime.time(8, 0))
        
        assert manager._check_court_availability(court, start, end) is False
    
    def test_court_unavailable_when_booked(self, sample_teams, sample_courts, basic_constraints):
        """Test that court is unavailable when already booked."""
        manager = AllocationManager(sample_teams, sample_courts, basic_constraints)
        court = sample_courts[0]
        
        base_date = datetime.date.today()
        existing_start = datetime.datetime.combine(base_date, datetime.time(9, 0))
        existing_end = datetime.datetime.combine(base_date, datetime.time(10, 0))
        
        # Add an existing match to the schedule
        manager.schedule[court.name].append((1, existing_start, existing_end, ("Team A", "Team B")))
        
        # Try to book overlapping time
        new_start = datetime.datetime.combine(base_date, datetime.time(9, 30))
        new_end = datetime.datetime.combine(base_date, datetime.time(10, 30))
        
        assert manager._check_court_availability(court, new_start, new_end) is False
    
    def test_court_available_adjacent_slot(self, sample_teams, sample_courts, basic_constraints):
        """Test that court is available for adjacent time slot."""
        manager = AllocationManager(sample_teams, sample_courts, basic_constraints)
        court = sample_courts[0]
        
        base_date = datetime.date.today()
        existing_start = datetime.datetime.combine(base_date, datetime.time(9, 0))
        existing_end = datetime.datetime.combine(base_date, datetime.time(10, 0))
        
        # Add an existing match
        manager.schedule[court.name].append((1, existing_start, existing_end, ("Team A", "Team B")))
        
        # Try to book right after (accounting for min_break_between_matches_minutes=15)
        new_start = datetime.datetime.combine(base_date, datetime.time(10, 15))
        new_end = datetime.datetime.combine(base_date, datetime.time(11, 15))
        
        assert manager._check_court_availability(court, new_start, new_end) is True
    
    def test_court_unavailable_after_end_time(self, sample_teams, basic_constraints):
        """Test that court is unavailable after its end time."""
        # Create a court that closes at 10:00
        courts = [Court(name="Court 1", start_time="08:00", end_time="10:00")]
        manager = AllocationManager(sample_teams, courts, basic_constraints)
        court = courts[0]
        
        base_date = datetime.date.today()
        # Match that ends after court closes
        start = datetime.datetime.combine(base_date, datetime.time(9, 30))
        end = datetime.datetime.combine(base_date, datetime.time(10, 30))
        
        assert manager._check_court_availability(court, start, end) is False
    
    def test_court_available_before_end_time(self, sample_teams, basic_constraints):
        """Test that court is available when match ends before court closes."""
        # Create a court that closes at 10:00
        courts = [Court(name="Court 1", start_time="08:00", end_time="10:00")]
        manager = AllocationManager(sample_teams, courts, basic_constraints)
        court = courts[0]
        
        base_date = datetime.date.today()
        # Match that ends exactly at court close
        start = datetime.datetime.combine(base_date, datetime.time(9, 0))
        end = datetime.datetime.combine(base_date, datetime.time(10, 0))
        
        assert manager._check_court_availability(court, start, end) is True
    
    def test_court_no_end_time_allows_all_times(self, sample_teams, basic_constraints):
        """Test that court with no end_time allows matches at any time."""
        courts = [Court(name="Court 1", start_time="08:00")]  # No end_time
        manager = AllocationManager(sample_teams, courts, basic_constraints)
        court = courts[0]
        
        base_date = datetime.date.today()
        # Late evening match
        start = datetime.datetime.combine(base_date, datetime.time(20, 0))
        end = datetime.datetime.combine(base_date, datetime.time(21, 0))
        
        assert manager._check_court_availability(court, start, end) is True


class TestTeamConstraints:
    """Tests for team constraint validation."""
    
    def test_play_after_constraint_satisfied(self, sample_teams, sample_courts, constraints_with_team_preferences):
        """Test play_after constraint is satisfied."""
        manager = AllocationManager(sample_teams, sample_courts, constraints_with_team_preferences)
        
        base_date = datetime.date.today()
        # Team A has play_after: 10:00, scheduling at 10:30 should work
        match_start = datetime.datetime.combine(base_date, datetime.time(10, 30))
        
        assert manager._check_team_constraints(("Team A", "Team C"), match_start) is True
    
    def test_play_after_constraint_violated(self, sample_teams, sample_courts, constraints_with_team_preferences):
        """Test play_after constraint is violated."""
        manager = AllocationManager(sample_teams, sample_courts, constraints_with_team_preferences)
        
        base_date = datetime.date.today()
        # Team A has play_after: 10:00, scheduling at 09:00 should fail
        match_start = datetime.datetime.combine(base_date, datetime.time(9, 0))
        
        assert manager._check_team_constraints(("Team A", "Team C"), match_start) is False
    
    def test_play_before_constraint_satisfied(self, sample_teams, sample_courts, constraints_with_team_preferences):
        """Test play_before constraint is satisfied."""
        manager = AllocationManager(sample_teams, sample_courts, constraints_with_team_preferences)
        
        base_date = datetime.date.today()
        # Team B has play_before: 14:00, match at 12:00 ending at 13:00 should work
        match_start = datetime.datetime.combine(base_date, datetime.time(12, 0))
        
        assert manager._check_team_constraints(("Team B", "Team C"), match_start) is True
    
    def test_play_before_constraint_violated(self, sample_teams, sample_courts, constraints_with_team_preferences):
        """Test play_before constraint is violated."""
        manager = AllocationManager(sample_teams, sample_courts, constraints_with_team_preferences)
        
        base_date = datetime.date.today()
        # Team B has play_before: 14:00, match at 13:30 ending at 14:30 should fail
        match_start = datetime.datetime.combine(base_date, datetime.time(13, 30))
        
        assert manager._check_team_constraints(("Team B", "Team C"), match_start) is False
    
    def test_no_overlapping_matches_for_same_team(self, sample_teams, sample_courts, basic_constraints):
        """Test that a team can't have overlapping matches."""
        manager = AllocationManager(sample_teams, sample_courts, basic_constraints)
        
        base_date = datetime.date.today()
        existing_start = datetime.datetime.combine(base_date, datetime.time(9, 0))
        existing_end = datetime.datetime.combine(base_date, datetime.time(10, 0))
        
        # Schedule Team A vs Team B
        manager.schedule["Court 1"].append((1, existing_start, existing_end, ("Team A", "Team B")))
        
        # Try to schedule Team A vs Team C at overlapping time
        new_start = datetime.datetime.combine(base_date, datetime.time(9, 30))
        
        assert manager._check_team_constraints(("Team A", "Team C"), new_start) is False
    
    def test_minimum_break_between_matches_satisfied(self, sample_teams, sample_courts, basic_constraints):
        """Test minimum break between matches is satisfied."""
        manager = AllocationManager(sample_teams, sample_courts, basic_constraints)
        
        base_date = datetime.date.today()
        existing_start = datetime.datetime.combine(base_date, datetime.time(9, 0))
        existing_end = datetime.datetime.combine(base_date, datetime.time(10, 0))
        
        # Schedule Team A vs Team B (ends at 10:00)
        manager.schedule["Court 1"].append((1, existing_start, existing_end, ("Team A", "Team B")))
        
        # Try to schedule Team A vs Team C at 10:15 (15 min break, matches constraint)
        new_start = datetime.datetime.combine(base_date, datetime.time(10, 15))
        
        assert manager._check_team_constraints(("Team A", "Team C"), new_start) is True
    
    def test_minimum_break_between_matches_violated(self, sample_teams, sample_courts, basic_constraints):
        """Test minimum break between matches is violated."""
        manager = AllocationManager(sample_teams, sample_courts, basic_constraints)
        
        base_date = datetime.date.today()
        existing_start = datetime.datetime.combine(base_date, datetime.time(9, 0))
        existing_end = datetime.datetime.combine(base_date, datetime.time(10, 0))
        
        # Schedule Team A vs Team B (ends at 10:00)
        manager.schedule["Court 1"].append((1, existing_start, existing_end, ("Team A", "Team B")))
        
        # Try to schedule Team A vs Team C at 10:10 (only 10 min break, needs 15)
        new_start = datetime.datetime.combine(base_date, datetime.time(10, 10))
        
        assert manager._check_team_constraints(("Team A", "Team C"), new_start) is False


class TestTeamOverlap:
    """Tests for team overlap detection."""
    
    def test_no_overlap_empty_schedule(self, sample_teams, sample_courts, basic_constraints):
        """Test no overlap when schedule is empty."""
        manager = AllocationManager(sample_teams, sample_courts, basic_constraints)
        
        base_date = datetime.date.today()
        start = datetime.datetime.combine(base_date, datetime.time(9, 0))
        end = datetime.datetime.combine(base_date, datetime.time(10, 0))
        
        assert manager._has_team_overlap(("Team A", "Team B"), start, end) is False
    
    def test_overlap_detected(self, sample_teams, sample_courts, basic_constraints):
        """Test overlap is detected when team has concurrent match."""
        manager = AllocationManager(sample_teams, sample_courts, basic_constraints)
        
        base_date = datetime.date.today()
        existing_start = datetime.datetime.combine(base_date, datetime.time(9, 0))
        existing_end = datetime.datetime.combine(base_date, datetime.time(10, 0))
        
        # Schedule Team A vs Team B on Court 1
        manager.schedule["Court 1"].append((1, existing_start, existing_end, ("Team A", "Team B")))
        
        # Check if Team A can play at overlapping time (should detect overlap)
        new_start = datetime.datetime.combine(base_date, datetime.time(9, 30))
        new_end = datetime.datetime.combine(base_date, datetime.time(10, 30))
        
        assert manager._has_team_overlap(("Team A", "Team C"), new_start, new_end) is True
    
    def test_no_overlap_different_teams(self, sample_teams, sample_courts, basic_constraints):
        """Test no overlap when different teams play at same time."""
        manager = AllocationManager(sample_teams, sample_courts, basic_constraints)
        
        base_date = datetime.date.today()
        existing_start = datetime.datetime.combine(base_date, datetime.time(9, 0))
        existing_end = datetime.datetime.combine(base_date, datetime.time(10, 0))
        
        # Schedule Team A vs Team B on Court 1
        manager.schedule["Court 1"].append((1, existing_start, existing_end, ("Team A", "Team B")))
        
        # Check if Team C vs Team D can play at same time (should be fine)
        assert manager._has_team_overlap(("Team C", "Team D"), existing_start, existing_end) is False


class TestScheduleOutput:
    """Tests for schedule output generation."""
    
    def test_get_schedule_output_empty(self, sample_teams, sample_courts, basic_constraints):
        """Test schedule output when no matches scheduled."""
        manager = AllocationManager(sample_teams, sample_courts, basic_constraints)
        
        output = manager.get_schedule_output()
        
        assert len(output) == 2  # Two courts
        for court_info in output:
            assert "court_name" in court_info
            assert "matches" in court_info
            assert court_info["matches"] == []
    
    def test_get_schedule_output_with_matches(self, sample_teams, sample_courts, basic_constraints):
        """Test schedule output with scheduled matches."""
        manager = AllocationManager(sample_teams, sample_courts, basic_constraints)
        
        base_date = datetime.date.today()
        start = datetime.datetime.combine(base_date, datetime.time(9, 0))
        end = datetime.datetime.combine(base_date, datetime.time(10, 0))
        
        manager.schedule["Court 1"].append((1, start, end, ("Team A", "Team B")))
        
        output = manager.get_schedule_output()
        
        court1_info = next(c for c in output if c["court_name"] == "Court 1")
        assert len(court1_info["matches"]) == 1
        assert court1_info["matches"][0]["teams"] == ("Team A", "Team B")
        assert court1_info["matches"][0]["start_time"] == "09:00"
        assert court1_info["matches"][0]["end_time"] == "10:00"
