"""
Tests for consecutive match avoidance feature.

When pool_in_same_court is enabled, teams should not play 3+ matches
consecutively when there is sufficient time to interleave matches.
"""
import pytest
import datetime
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from core.allocation import AllocationManager
from core.models import Team, Court


def count_consecutive_runs(schedule, team_name):
    """
    Count how many times a team plays consecutive matches.
    
    Returns:
        max_run: Maximum consecutive matches played
        run_counts: Dictionary of {run_length: count}
    """
    # Extract all matches for this team, sorted by start time
    team_matches = []
    for court_name, matches in schedule.items():
        for day_num, start_time, end_time, (t1, t2) in matches:
            if team_name in (t1, t2):
                team_matches.append((start_time, end_time))
    
    if not team_matches:
        return 0, {}
    
    # Sort by start time
    team_matches.sort(key=lambda x: x[0])
    
    # Count consecutive runs
    max_run = 1
    current_run = 1
    run_counts = {}
    
    for i in range(1, len(team_matches)):
        prev_end = team_matches[i-1][1]
        curr_start = team_matches[i][0]
        
        # If current match starts within a short window after previous ends,
        # consider them consecutive (using 20-minute threshold to account for breaks)
        time_gap = (curr_start - prev_end).total_seconds() / 60
        
        if time_gap <= 20:  # Close enough to be "consecutive"
            current_run += 1
            max_run = max(max_run, current_run)
        else:
            # Run ended, record it
            if current_run > 1:
                run_counts[current_run] = run_counts.get(current_run, 0) + 1
            current_run = 1
    
    # Record final run
    if current_run > 1:
        run_counts[current_run] = run_counts.get(current_run, 0) + 1
    
    return max_run, run_counts


def verify_schedule_valid(manager, schedule):
    """
    Verify that the schedule satisfies basic constraints.
    
    Returns True if valid, raises AssertionError with details if not.
    """
    min_break = manager.constraints.get('min_break_between_matches_minutes', 0)
    
    # Check 1: No team plays overlapping matches
    for team_name in manager.teams.keys():
        team_times = []
        for court_name, matches in schedule.items():
            for day_num, start_time, end_time, (t1, t2) in matches:
                if team_name in (t1, t2):
                    team_times.append((start_time, end_time))
        
        team_times.sort()
        for i in range(1, len(team_times)):
            prev_end = team_times[i-1][1]
            curr_start = team_times[i][0]
            gap_minutes = (curr_start - prev_end).total_seconds() / 60
            
            assert gap_minutes >= min_break, \
                f"{team_name} has insufficient break: {gap_minutes}min < {min_break}min"
    
    # Check 2: No court has overlapping matches
    for court_name, matches in schedule.items():
        sorted_matches = sorted(matches, key=lambda x: x[1])  # Sort by start time
        for i in range(1, len(sorted_matches)):
            prev_end = sorted_matches[i-1][2]
            curr_start = sorted_matches[i][1]
            
            assert curr_start >= prev_end, \
                f"{court_name} has overlapping matches"
    
    return True


class TestConsecutiveMatchAvoidance:
    """Tests for avoiding consecutive matches when pool_in_same_court is enabled."""
    
    def test_four_team_pool_generous_time_no_three_in_row(self):
        """
        With pool_in_same_court and generous time window, no team should play 3 in a row.
        
        Setup: 4 teams, 1 pool, 1 court, 12-hour window (08:00-20:00)
        Expected: All teams avoid 3+ consecutive matches
        """
        teams = [
            Team(name="Team A", attributes={"pool": "pool1"}),
            Team(name="Team B", attributes={"pool": "pool1"}),
            Team(name="Team C", attributes={"pool": "pool1"}),
            Team(name="Team D", attributes={"pool": "pool1"}),
        ]
        
        courts = [Court(name="Court 1", start_time="08:00", end_time="20:00")]
        
        constraints = {
            "match_duration_minutes": 30,
            "days_number": 1,
            "min_break_between_matches_minutes": 15,
            "time_slot_increment_minutes": 5,
            "day_end_time_limit": "20:00",
            "team_specific_constraints": [],
            "general_constraints": [],
            "pool_in_same_court": True,
        }
        
        manager = AllocationManager(teams, courts, constraints)
        matches = [
            (("Team A", "Team B"), "pool1"),
            (("Team A", "Team C"), "pool1"),
            (("Team A", "Team D"), "pool1"),
            (("Team B", "Team C"), "pool1"),
            (("Team B", "Team D"), "pool1"),
            (("Team C", "Team D"), "pool1"),
        ]
        
        # Monkey-patch to use our custom matches
        manager._generate_pool_play_matches = lambda: matches
        
        schedule, warnings = manager.allocate_teams_to_courts()
        
        # Verify schedule is valid
        assert schedule is not None, "Schedule should be feasible"
        verify_schedule_valid(manager, schedule)
        
        # Check that no team plays 3+ consecutive matches
        for team in ["Team A", "Team B", "Team C", "Team D"]:
            max_run, run_counts = count_consecutive_runs(schedule, team)
            assert max_run < 3, \
                f"{team} plays {max_run} consecutive matches (expected < 3). Runs: {run_counts}"
    
    def test_four_team_pool_tight_time_still_feasible(self):
        """
        With pool_in_same_court and tight time constraints, schedule should still be valid.
        
        Setup: 4 teams, 1 pool, 1 court, 3-hour window
        Expected: Valid schedule exists even if some teams play consecutively
        """
        teams = [
            Team(name="Team A", attributes={"pool": "pool1"}),
            Team(name="Team B", attributes={"pool": "pool1"}),
            Team(name="Team C", attributes={"pool": "pool1"}),
            Team(name="Team D", attributes={"pool": "pool1"}),
        ]
        
        courts = [Court(name="Court 1", start_time="08:00", end_time="11:00")]
        
        constraints = {
            "match_duration_minutes": 30,
            "days_number": 1,
            "min_break_between_matches_minutes": 0,  # No break required for tight fit
            "time_slot_increment_minutes": 5,
            "day_end_time_limit": "11:00",
            "team_specific_constraints": [],
            "general_constraints": [],
            "pool_in_same_court": True,
        }
        
        manager = AllocationManager(teams, courts, constraints)
        matches = [
            (("Team A", "Team B"), "pool1"),
            (("Team A", "Team C"), "pool1"),
            (("Team A", "Team D"), "pool1"),
            (("Team B", "Team C"), "pool1"),
            (("Team B", "Team D"), "pool1"),
            (("Team C", "Team D"), "pool1"),
        ]
        
        # Monkey-patch to use our custom matches
        manager._generate_pool_play_matches = lambda: matches
        
        schedule, warnings = manager.allocate_teams_to_courts()
        
        # Primary check: schedule should exist and be valid
        assert schedule is not None, "Schedule should be feasible even with tight constraints"
        verify_schedule_valid(manager, schedule)
        
        # All 6 matches should be scheduled
        total_matches = sum(len(matches) for matches in schedule.values())
        assert total_matches == 6, f"Expected 6 matches, got {total_matches}"
    
    def test_without_pool_in_same_court_spreads_across_courts(self):
        """
        Without pool_in_same_court, matches should spread across available courts.
        
        Setup: 4 teams, 1 pool, 2 courts, pool_in_same_court=False
        Expected: Matches distributed across both courts
        """
        teams = [
            Team(name="Team A", attributes={"pool": "pool1"}),
            Team(name="Team B", attributes={"pool": "pool1"}),
            Team(name="Team C", attributes={"pool": "pool1"}),
            Team(name="Team D", attributes={"pool": "pool1"}),
        ]
        
        courts = [
            Court(name="Court 1", start_time="08:00"),
            Court(name="Court 2", start_time="08:00"),
        ]
        
        constraints = {
            "match_duration_minutes": 30,
            "days_number": 1,
            "min_break_between_matches_minutes": 15,
            "time_slot_increment_minutes": 5,
            "day_end_time_limit": "20:00",
            "team_specific_constraints": [],
            "general_constraints": [],
            "pool_in_same_court": False,  # Allow spreading
        }
        
        manager = AllocationManager(teams, courts, constraints)
        matches = [
            (("Team A", "Team B"), "pool1"),
            (("Team A", "Team C"), "pool1"),
            (("Team A", "Team D"), "pool1"),
            (("Team B", "Team C"), "pool1"),
            (("Team B", "Team D"), "pool1"),
            (("Team C", "Team D"), "pool1"),
        ]
        
        # Monkey-patch to use our custom matches
        manager._generate_pool_play_matches = lambda: matches
        
        schedule, warnings = manager.allocate_teams_to_courts()
        
        assert schedule is not None, "Schedule should be feasible"
        verify_schedule_valid(manager, schedule)
        
        # Check that both courts are used
        court1_matches = len(schedule["Court 1"])
        court2_matches = len(schedule["Court 2"])
        
        assert court1_matches > 0 and court2_matches > 0, \
            f"Matches should spread across courts: Court 1={court1_matches}, Court 2={court2_matches}"
    
    def test_six_team_pool_with_same_court_constraint(self):
        """
        Larger pool (6 teams = 15 matches) should still avoid 3+ consecutive.
        
        Setup: 6 teams, 1 pool, 1 court, generous time
        Expected: No team plays 3+ consecutive matches
        """
        teams = [
            Team(name=f"Team {chr(65+i)}", attributes={"pool": "pool1"})
            for i in range(6)
        ]
        
        courts = [Court(name="Court 1", start_time="08:00", end_time="22:00")]
        
        constraints = {
            "match_duration_minutes": 30,
            "days_number": 1,
            "min_break_between_matches_minutes": 10,
            "time_slot_increment_minutes": 5,
            "day_end_time_limit": "22:00",
            "team_specific_constraints": [],
            "general_constraints": [],
            "pool_in_same_court": True,
        }
        
        manager = AllocationManager(teams, courts, constraints)
        
        # Generate all matches for 6-team round robin
        match_list = []
        team_names = [f"Team {chr(65+i)}" for i in range(6)]
        for i in range(len(team_names)):
            for j in range(i+1, len(team_names)):
                match_list.append(((team_names[i], team_names[j]), "pool1"))
        
        assert len(match_list) == 15, "6 teams should generate 15 matches"
        
        # Monkey-patch to use our custom matches
        manager._generate_pool_play_matches = lambda: match_list
        
        schedule, warnings = manager.allocate_teams_to_courts()
        
        assert schedule is not None, "Schedule should be feasible"
        verify_schedule_valid(manager, schedule)
        
        # Check consecutive runs for all teams
        for team in team_names:
            max_run, run_counts = count_consecutive_runs(schedule, team)
            # With 15 matches in 14 hours and 10-minute breaks, should avoid 3-in-a-row
            assert max_run < 3, \
                f"{team} plays {max_run} consecutive matches. Runs: {run_counts}"
    
    def test_two_pools_different_courts_independent(self):
        """
        Two pools with pool_in_same_court should each get their own court.
        
        Setup: 2 pools (3 teams each), 2 courts, pool_in_same_court=True
        Expected: Pool1 on Court1, Pool2 on Court2 (or vice versa)
        """
        teams = [
            Team(name="A1", attributes={"pool": "pool1"}),
            Team(name="A2", attributes={"pool": "pool1"}),
            Team(name="A3", attributes={"pool": "pool1"}),
            Team(name="B1", attributes={"pool": "pool2"}),
            Team(name="B2", attributes={"pool": "pool2"}),
            Team(name="B3", attributes={"pool": "pool2"}),
        ]
        
        courts = [
            Court(name="Court 1", start_time="08:00"),
            Court(name="Court 2", start_time="08:00"),
        ]
        
        constraints = {
            "match_duration_minutes": 30,
            "days_number": 1,
            "min_break_between_matches_minutes": 15,
            "time_slot_increment_minutes": 5,
            "day_end_time_limit": "20:00",
            "team_specific_constraints": [],
            "general_constraints": [],
            "pool_in_same_court": True,
        }
        
        manager = AllocationManager(teams, courts, constraints)
        
        # Pool 1 matches
        pool1_matches = [
            (("A1", "A2"), "pool1"),
            (("A1", "A3"), "pool1"),
            (("A2", "A3"), "pool1"),
        ]
        
        # Pool 2 matches
        pool2_matches = [
            (("B1", "B2"), "pool2"),
            (("B1", "B3"), "pool2"),
            (("B2", "B3"), "pool2"),
        ]
        
        all_matches = pool1_matches + pool2_matches
        
        # Monkey-patch to use our custom matches
        manager._generate_pool_play_matches = lambda: all_matches
        
        schedule, warnings = manager.allocate_teams_to_courts()
        
        assert schedule is not None, "Schedule should be feasible"
        verify_schedule_valid(manager, schedule)
        
        # Check that each pool is confined to one court
        pool1_courts = set()
        pool2_courts = set()
        
        for court_name, matches in schedule.items():
            for day_num, start_time, end_time, (t1, t2) in matches:
                if t1.startswith("A") or t2.startswith("A"):
                    pool1_courts.add(court_name)
                if t1.startswith("B") or t2.startswith("B"):
                    pool2_courts.add(court_name)
        
        assert len(pool1_courts) == 1, f"Pool 1 should use exactly one court, used: {pool1_courts}"
        assert len(pool2_courts) == 1, f"Pool 2 should use exactly one court, used: {pool2_courts}"
        assert pool1_courts != pool2_courts, "Pools should use different courts"


class TestConsecutiveMatchDetection:
    """Tests for the consecutive match detection helper function."""
    
    def test_count_consecutive_no_matches(self):
        """Test counting with no matches for a team."""
        schedule = {"Court 1": []}
        max_run, run_counts = count_consecutive_runs(schedule, "Team A")
        assert max_run == 0
        assert run_counts == {}
    
    def test_count_consecutive_single_match(self):
        """Test counting with only one match."""
        base_date = datetime.date.today()
        schedule = {
            "Court 1": [
                (1, datetime.datetime.combine(base_date, datetime.time(9, 0)),
                 datetime.datetime.combine(base_date, datetime.time(9, 30)),
                 ("Team A", "Team B"))
            ]
        }
        max_run, run_counts = count_consecutive_runs(schedule, "Team A")
        assert max_run == 1
        assert run_counts == {}
    
    def test_count_consecutive_two_back_to_back(self):
        """Test detecting two consecutive matches."""
        base_date = datetime.date.today()
        schedule = {
            "Court 1": [
                (1, datetime.datetime.combine(base_date, datetime.time(9, 0)),
                 datetime.datetime.combine(base_date, datetime.time(9, 30)),
                 ("Team A", "Team B")),
                (1, datetime.datetime.combine(base_date, datetime.time(9, 45)),
                 datetime.datetime.combine(base_date, datetime.time(10, 15)),
                 ("Team A", "Team C")),
            ]
        }
        max_run, run_counts = count_consecutive_runs(schedule, "Team A")
        assert max_run == 2
        assert run_counts[2] == 1
    
    def test_count_consecutive_three_in_row(self):
        """Test detecting three consecutive matches."""
        base_date = datetime.date.today()
        schedule = {
            "Court 1": [
                (1, datetime.datetime.combine(base_date, datetime.time(9, 0)),
                 datetime.datetime.combine(base_date, datetime.time(9, 30)),
                 ("Team A", "Team B")),
                (1, datetime.datetime.combine(base_date, datetime.time(9, 45)),
                 datetime.datetime.combine(base_date, datetime.time(10, 15)),
                 ("Team A", "Team C")),
                (1, datetime.datetime.combine(base_date, datetime.time(10, 30)),
                 datetime.datetime.combine(base_date, datetime.time(11, 0)),
                 ("Team A", "Team D")),
            ]
        }
        max_run, run_counts = count_consecutive_runs(schedule, "Team A")
        assert max_run == 3
        assert run_counts[3] == 1
    
    def test_count_consecutive_with_rest_between(self):
        """Test that matches with sufficient rest are not consecutive."""
        base_date = datetime.date.today()
        schedule = {
            "Court 1": [
                (1, datetime.datetime.combine(base_date, datetime.time(9, 0)),
                 datetime.datetime.combine(base_date, datetime.time(9, 30)),
                 ("Team A", "Team B")),
                (1, datetime.datetime.combine(base_date, datetime.time(11, 0)),
                 datetime.datetime.combine(base_date, datetime.time(11, 30)),
                 ("Team A", "Team C")),
            ]
        }
        max_run, run_counts = count_consecutive_runs(schedule, "Team A")
        assert max_run == 1
        assert run_counts == {}
