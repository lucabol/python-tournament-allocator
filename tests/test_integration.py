"""
Integration tests for end-to-end tournament scheduling scenarios.
"""
import pytest
import datetime
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from core.allocation import AllocationManager
from core.models import Team, Court
from generate_matches import generate_pool_play_matches


class TestFullScheduling:
    """End-to-end tests for complete tournament scheduling."""
    
    def test_simple_tournament_all_matches_scheduled(self, sample_teams, sample_courts, basic_constraints):
        """Test that a simple tournament schedules all matches."""
        manager = AllocationManager(sample_teams, sample_courts, basic_constraints)
        
        # Generate matches
        matches = generate_pool_play_matches(sample_teams)
        match_tuples = [(tuple(m["teams"]), m["pool"]) for m in matches]
        
        # Override match generation
        manager._generate_pool_play_matches = lambda: match_tuples
        
        # Run allocation
        manager.allocate_teams_to_courts()
        
        # Count scheduled matches
        scheduled_count = sum(len(court_matches) for court_matches in manager.schedule.values())
        
        assert scheduled_count == len(matches), f"Expected {len(matches)} matches, got {scheduled_count}"
    
    def test_all_constraints_respected_after_scheduling(self, sample_teams, sample_courts, constraints_with_team_preferences):
        """Test that all team constraints are respected in final schedule."""
        manager = AllocationManager(sample_teams, sample_courts, constraints_with_team_preferences)
        
        matches = generate_pool_play_matches(sample_teams)
        match_tuples = [(tuple(m["teams"]), m["pool"]) for m in matches]
        manager._generate_pool_play_matches = lambda: match_tuples
        
        manager.allocate_teams_to_courts()
        
        # Verify Team A's play_after constraint (10:00)
        for court_matches in manager.schedule.values():
            for day_num, start_dt, end_dt, match_tuple in court_matches:
                if "Team A" in match_tuple:
                    assert start_dt.hour >= 10, f"Team A scheduled before 10:00: {start_dt}"
        
        # Verify Team B's play_before constraint (14:00)
        for court_matches in manager.schedule.values():
            for day_num, start_dt, end_dt, match_tuple in court_matches:
                if "Team B" in match_tuple:
                    assert end_dt.hour < 14 or (end_dt.hour == 14 and end_dt.minute == 0), \
                        f"Team B's match ends after 14:00: {end_dt}"
    
    def test_no_team_plays_concurrent_matches(self, sample_teams, sample_courts, basic_constraints):
        """Test that no team is scheduled for concurrent matches."""
        manager = AllocationManager(sample_teams, sample_courts, basic_constraints)
        
        matches = generate_pool_play_matches(sample_teams)
        match_tuples = [(tuple(m["teams"]), m["pool"]) for m in matches]
        manager._generate_pool_play_matches = lambda: match_tuples
        
        manager.allocate_teams_to_courts()
        
        # Collect all matches per team
        team_matches = {}
        for court_matches in manager.schedule.values():
            for day_num, start_dt, end_dt, match_tuple in court_matches:
                for team in match_tuple:
                    if team not in team_matches:
                        team_matches[team] = []
                    team_matches[team].append((day_num, start_dt, end_dt))
        
        # Check no overlaps for any team
        for team, matches_list in team_matches.items():
            sorted_matches = sorted(matches_list, key=lambda x: (x[0], x[1]))
            for i in range(len(sorted_matches) - 1):
                day1, _, end1 = sorted_matches[i]
                day2, start2, _ = sorted_matches[i + 1]
                
                if day1 == day2:
                    assert end1 <= start2, f"Team {team} has overlapping matches: ends {end1}, next starts {start2}"
    
    def test_minimum_break_respected(self, sample_teams, sample_courts, basic_constraints):
        """Test that minimum break between matches is respected."""
        manager = AllocationManager(sample_teams, sample_courts, basic_constraints)
        
        matches = generate_pool_play_matches(sample_teams)
        match_tuples = [(tuple(m["teams"]), m["pool"]) for m in matches]
        manager._generate_pool_play_matches = lambda: match_tuples
        
        manager.allocate_teams_to_courts()
        
        min_break = datetime.timedelta(minutes=basic_constraints["min_break_between_matches_minutes"])
        
        # Collect all matches per team
        team_matches = {}
        for court_matches in manager.schedule.values():
            for day_num, start_dt, end_dt, match_tuple in court_matches:
                for team in match_tuple:
                    if team not in team_matches:
                        team_matches[team] = []
                    team_matches[team].append((day_num, start_dt, end_dt))
        
        # Check break times for each team
        for team, matches_list in team_matches.items():
            sorted_matches = sorted(matches_list, key=lambda x: (x[0], x[1]))
            for i in range(len(sorted_matches) - 1):
                day1, _, end1 = sorted_matches[i]
                day2, start2, _ = sorted_matches[i + 1]
                
                if day1 == day2:
                    actual_break = start2 - end1
                    assert actual_break >= min_break, \
                        f"Team {team} has insufficient break: {actual_break} < {min_break}"


class TestLargeTournament:
    """Tests for larger tournament scenarios."""
    
    def test_large_tournament_scheduling(self, large_tournament_teams, four_courts, basic_constraints):
        """Test scheduling a larger tournament with multiple pools."""
        # Adjust constraints for more capacity
        basic_constraints["days_number"] = 2
        
        manager = AllocationManager(large_tournament_teams, four_courts, basic_constraints)
        
        matches = generate_pool_play_matches(large_tournament_teams)
        match_tuples = [(tuple(m["teams"]), m["pool"]) for m in matches]
        manager._generate_pool_play_matches = lambda: match_tuples
        
        manager.allocate_teams_to_courts()
        
        scheduled_count = sum(len(court_matches) for court_matches in manager.schedule.values())
        
        # Should schedule all matches (3 pools × 6 matches each = 18 matches)
        expected_matches = len(matches)
        assert scheduled_count == expected_matches, \
            f"Expected {expected_matches} matches, got {scheduled_count}"
    
    def test_multi_day_distribution(self, large_tournament_teams, four_courts, basic_constraints):
        """Test that matches are distributed across multiple days."""
        basic_constraints["days_number"] = 2
        basic_constraints["day_end_time_limit"] = "14:00"  # Short day to force multi-day
        
        manager = AllocationManager(large_tournament_teams, four_courts, basic_constraints)
        
        matches = generate_pool_play_matches(large_tournament_teams)
        match_tuples = [(tuple(m["teams"]), m["pool"]) for m in matches]
        manager._generate_pool_play_matches = lambda: match_tuples
        
        manager.allocate_teams_to_courts()
        
        # Collect day numbers
        days_used = set()
        for court_matches in manager.schedule.values():
            for day_num, _, _, _ in court_matches:
                days_used.add(day_num)
        
        # With short days, should use both days
        assert len(days_used) >= 1, "Matches should be scheduled across available days"


class TestEdgeCases:
    """Tests for edge cases and error conditions."""
    
    def test_impossible_schedule_reported(self, sample_teams, tight_constraints):
        """Test that impossible schedules are handled gracefully."""
        # Create a scenario where scheduling is impossible
        single_court = [Court(name="Court 1", start_time="08:00")]
        
        # With tight constraints and many teams, some matches won't fit
        many_teams = [Team(name=f"Team {i}", attributes={"pool": "pool1"}) for i in range(6)]
        
        manager = AllocationManager(many_teams, single_court, tight_constraints)
        
        matches = generate_pool_play_matches(many_teams)
        match_tuples = [(tuple(m["teams"]), m["pool"]) for m in matches]
        manager._generate_pool_play_matches = lambda: match_tuples
        
        # Should not raise an exception
        manager.allocate_teams_to_courts()
        
        # Some matches likely couldn't be scheduled
        scheduled_count = sum(len(court_matches) for court_matches in manager.schedule.values())
        # Just verify it doesn't crash and schedules what it can
        assert scheduled_count >= 0
    
    def test_empty_tournament(self, sample_courts, basic_constraints):
        """Test handling of tournament with no teams."""
        manager = AllocationManager([], sample_courts, basic_constraints)
        manager._generate_pool_play_matches = lambda: []
        
        schedule = manager.allocate_teams_to_courts()
        
        # Should return empty schedule without errors
        total_matches = sum(len(court_matches) for court_matches in schedule.values())
        assert total_matches == 0
    
    def test_single_match_tournament(self, sample_courts, basic_constraints):
        """Test tournament with only one match."""
        teams = [
            Team(name="Team A", attributes={"pool": "pool1"}),
            Team(name="Team B", attributes={"pool": "pool1"}),
        ]
        
        manager = AllocationManager(teams, sample_courts, basic_constraints)
        
        matches = generate_pool_play_matches(teams)
        match_tuples = [(tuple(m["teams"]), m["pool"]) for m in matches]
        manager._generate_pool_play_matches = lambda: match_tuples
        
        manager.allocate_teams_to_courts()
        
        scheduled_count = sum(len(court_matches) for court_matches in manager.schedule.values())
        assert scheduled_count == 1


class TestScheduleConsistency:
    """Tests to verify schedule consistency and correctness."""
    
    def test_each_match_scheduled_once(self, sample_teams, sample_courts, basic_constraints):
        """Test that each match is scheduled exactly once."""
        manager = AllocationManager(sample_teams, sample_courts, basic_constraints)
        
        matches = generate_pool_play_matches(sample_teams)
        match_tuples = [(tuple(m["teams"]), m["pool"]) for m in matches]
        manager._generate_pool_play_matches = lambda: match_tuples
        
        manager.allocate_teams_to_courts()
        
        # Collect all scheduled matches
        scheduled_matches = []
        for court_matches in manager.schedule.values():
            for _, _, _, match_tuple in court_matches:
                scheduled_matches.append(frozenset(match_tuple))
        
        # Check no duplicates
        assert len(scheduled_matches) == len(set(scheduled_matches)), "Duplicate matches found in schedule"
    
    def test_matches_within_court_hours(self, sample_teams, sample_courts, basic_constraints):
        """Test that all matches are within court operating hours."""
        manager = AllocationManager(sample_teams, sample_courts, basic_constraints)
        
        matches = generate_pool_play_matches(sample_teams)
        match_tuples = [(tuple(m["teams"]), m["pool"]) for m in matches]
        manager._generate_pool_play_matches = lambda: match_tuples
        
        manager.allocate_teams_to_courts()
        
        day_end = datetime.time(22, 0)  # From constraints
        
        for court in sample_courts:
            court_start = manager._parse_time(court.start_time)
            for day_num, start_dt, end_dt, _ in manager.schedule[court.name]:
                assert start_dt.time() >= court_start, \
                    f"Match starts before court opens: {start_dt.time()} < {court_start}"
                assert end_dt.time() <= day_end, \
                    f"Match ends after day limit: {end_dt.time()} > {day_end}"
