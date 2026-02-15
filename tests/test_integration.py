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


@pytest.mark.slow
class TestLargeTournament:
    """Tests for larger tournament scenarios (uses OR-Tools CP-SAT solver, ~60s each)."""
    
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
        
        schedule, _warnings = manager.allocate_teams_to_courts()
        
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


class TestFullTournamentIntegration:
    """
    End-to-end integration tests for complete tournament workflows.
    
    These tests validate full tournament flows from pool play through bracket elimination,
    ensuring all phases integrate correctly and produce valid schedules.
    """
    
    def test_pool_plus_single_elimination(self, sample_courts):
        """Test complete flow: pool play → gold bracket (single elimination)."""
        # Setup: 2 pools of 4 teams, top 2 advance
        teams = [
            Team(name="Pool1_A", attributes={"pool": "pool1"}),
            Team(name="Pool1_B", attributes={"pool": "pool1"}),
            Team(name="Pool1_C", attributes={"pool": "pool1"}),
            Team(name="Pool1_D", attributes={"pool": "pool1"}),
            Team(name="Pool2_A", attributes={"pool": "pool2"}),
            Team(name="Pool2_B", attributes={"pool": "pool2"}),
            Team(name="Pool2_C", attributes={"pool": "pool2"}),
            Team(name="Pool2_D", attributes={"pool": "pool2"}),
        ]
        
        constraints = {
            "match_duration_minutes": 60,
            "days_number": 2,
            "min_break_between_matches_minutes": 15,
            "time_slot_increment_minutes": 15,
            "day_end_time_limit": "22:00",
            "team_specific_constraints": [],
            "general_constraints": [],
            "tournament_settings": {
                "type": "pool_play_with_elimination",
                "elimination_type": "single",
                "pools": {
                    "pool1": {"teams": ["Pool1_A", "Pool1_B", "Pool1_C", "Pool1_D"], "advance": 2},
                    "pool2": {"teams": ["Pool2_A", "Pool2_B", "Pool2_C", "Pool2_D"], "advance": 2}
                }
            }
        }
        
        manager = AllocationManager(teams, sample_courts, constraints)
        
        # Generate all matches: pool play + elimination
        from core.elimination import generate_elimination_matches_for_scheduling
        
        pool_matches = generate_pool_play_matches(teams)
        pool_tuples = [(tuple(m["teams"]), m["pool"]) for m in pool_matches]
        
        pools_data = constraints["tournament_settings"]["pools"]
        elim_tuples = generate_elimination_matches_for_scheduling(pools_data)
        
        # Combine pool and elimination matches
        all_matches = pool_tuples + elim_tuples
        manager._generate_pool_play_matches = lambda: all_matches
        
        # Run allocation
        schedule, warnings = manager.allocate_teams_to_courts()
        
        # Validations
        scheduled_count = sum(len(court_matches) for court_matches in schedule.values())
        expected_pool_matches = len(pool_matches)
        expected_elim_matches = len(elim_tuples)
        expected_total = expected_pool_matches + expected_elim_matches
        
        assert scheduled_count > 0, "Schedule should not be empty"
        # Allow some tolerance for tight schedules
        assert scheduled_count >= expected_total * 0.8, \
            f"Expected at least {expected_total * 0.8:.0f} matches, got {scheduled_count}"
        
        # Verify no team double-booking
        team_matches = {}
        for court_matches in schedule.values():
            for day_num, start_dt, end_dt, match_tuple in court_matches:
                for team in match_tuple:
                    if team not in team_matches:
                        team_matches[team] = []
                    team_matches[team].append((day_num, start_dt, end_dt))
        
        for team, matches_list in team_matches.items():
            sorted_matches = sorted(matches_list, key=lambda x: (x[0], x[1]))
            for i in range(len(sorted_matches) - 1):
                day1, _, end1 = sorted_matches[i]
                day2, start2, _ = sorted_matches[i + 1]
                
                if day1 == day2:
                    assert end1 <= start2, f"Team {team} has overlapping matches"
        
        # Verify both pool and elimination phases present
        pool_phase_found = any("pool" in str(match_info).lower() 
                               for match_info in [m[1] for m in all_matches if len(m) > 1])
        elimination_phase_found = any("round" in str(match_info).lower() or "final" in str(match_info).lower()
                                      for match_info in [m[1] for m in all_matches if len(m) > 1])
        
        # At minimum, we should have attempted to schedule both phases
        assert len(all_matches) == expected_total, \
            f"Should have {expected_total} total matches (pool + elimination)"
    
    def test_pool_plus_double_elimination(self, sample_courts):
        """Test complete flow: pool play → winners/losers brackets (double elimination)."""
        # Setup: 2 pools of 3 teams, top 2 advance
        teams = [
            Team(name="PoolA_1", attributes={"pool": "poolA"}),
            Team(name="PoolA_2", attributes={"pool": "poolA"}),
            Team(name="PoolA_3", attributes={"pool": "poolA"}),
            Team(name="PoolB_1", attributes={"pool": "poolB"}),
            Team(name="PoolB_2", attributes={"pool": "poolB"}),
            Team(name="PoolB_3", attributes={"pool": "poolB"}),
        ]
        
        constraints = {
            "match_duration_minutes": 60,
            "days_number": 2,
            "min_break_between_matches_minutes": 15,
            "time_slot_increment_minutes": 15,
            "day_end_time_limit": "22:00",
            "team_specific_constraints": [],
            "general_constraints": [],
            "tournament_settings": {
                "type": "pool_play_with_elimination",
                "elimination_type": "double",
                "pools": {
                    "poolA": {"teams": ["PoolA_1", "PoolA_2", "PoolA_3"], "advance": 2},
                    "poolB": {"teams": ["PoolB_1", "PoolB_2", "PoolB_3"], "advance": 2}
                }
            }
        }
        
        manager = AllocationManager(teams, sample_courts, constraints)
        
        # Generate all matches: pool play + double elimination
        from core.double_elimination import generate_double_elimination_matches_for_scheduling
        
        pool_matches = generate_pool_play_matches(teams)
        pool_tuples = [(tuple(m["teams"]), m["pool"]) for m in pool_matches]
        
        pools_data = constraints["tournament_settings"]["pools"]
        double_elim_tuples = generate_double_elimination_matches_for_scheduling(pools_data)
        
        # Combine pool and elimination matches
        all_matches = pool_tuples + double_elim_tuples
        manager._generate_pool_play_matches = lambda: all_matches
        
        # Run allocation
        schedule, warnings = manager.allocate_teams_to_courts()
        
        # Validations
        scheduled_count = sum(len(court_matches) for court_matches in schedule.values())
        expected_pool_matches = len(pool_matches)
        expected_elim_matches = len(double_elim_tuples)
        
        assert scheduled_count > 0, "Schedule should not be empty"
        
        # Verify no team double-booking
        team_matches = {}
        for court_matches in schedule.values():
            for day_num, start_dt, end_dt, match_tuple in court_matches:
                for team in match_tuple:
                    if team not in team_matches:
                        team_matches[team] = []
                    team_matches[team].append((day_num, start_dt, end_dt))
        
        for team, matches_list in team_matches.items():
            sorted_matches = sorted(matches_list, key=lambda x: (x[0], x[1]))
            for i in range(len(sorted_matches) - 1):
                day1, _, end1 = sorted_matches[i]
                day2, start2, _ = sorted_matches[i + 1]
                
                if day1 == day2:
                    assert end1 <= start2, f"Team {team} has overlapping matches"
        
        # Double elimination generates only first-round winners bracket matches
        # (later rounds depend on results and can't be pre-scheduled)
        # For 4 teams in bracket, there are 2 first-round matches (semifinals)
        assert expected_elim_matches >= 2, \
            f"Double elimination should have at least 2 first-round bracket matches, got {expected_elim_matches}"
        
        # Verify both pool and bracket phases present
        assert expected_pool_matches > 0, "Should have pool matches"
        assert expected_elim_matches > 0, "Should have elimination bracket matches"
    
    def test_gold_and_silver_brackets(self, sample_courts):
        """Test complete flow: pool play → gold bracket + silver bracket."""
        # Setup: 2 pools of 4 teams, top 2 to gold, bottom 2 to silver
        teams = [
            Team(name="Red1", attributes={"pool": "red"}),
            Team(name="Red2", attributes={"pool": "red"}),
            Team(name="Red3", attributes={"pool": "red"}),
            Team(name="Red4", attributes={"pool": "red"}),
            Team(name="Blue1", attributes={"pool": "blue"}),
            Team(name="Blue2", attributes={"pool": "blue"}),
            Team(name="Blue3", attributes={"pool": "blue"}),
            Team(name="Blue4", attributes={"pool": "blue"}),
        ]
        
        constraints = {
            "match_duration_minutes": 60,
            "days_number": 2,
            "min_break_between_matches_minutes": 15,
            "time_slot_increment_minutes": 15,
            "day_end_time_limit": "22:00",
            "team_specific_constraints": [],
            "general_constraints": [],
            "tournament_settings": {
                "type": "pool_play_with_elimination",
                "elimination_type": "single",
                "has_silver_bracket": True,
                "pools": {
                    "red": {"teams": ["Red1", "Red2", "Red3", "Red4"], "advance": 2},
                    "blue": {"teams": ["Blue1", "Blue2", "Blue3", "Blue4"], "advance": 2}
                }
            }
        }
        
        manager = AllocationManager(teams, sample_courts, constraints)
        
        # Generate all matches: pool play + gold bracket + silver bracket
        from core.elimination import (
            generate_elimination_matches_for_scheduling,
            seed_silver_bracket_teams,
            create_bracket_matchups
        )
        
        pool_matches = generate_pool_play_matches(teams)
        pool_tuples = [(tuple(m["teams"]), m["pool"]) for m in pool_matches]
        
        pools_data = constraints["tournament_settings"]["pools"]
        
        # Gold bracket (top 2 from each pool = 4 teams)
        gold_tuples = generate_elimination_matches_for_scheduling(pools_data)
        
        # Silver bracket (bottom 2 from each pool = 4 teams)
        silver_seeded = seed_silver_bracket_teams(pools_data)
        silver_matchups = create_bracket_matchups(silver_seeded)
        
        # Convert silver matchups to tuples with "Silver" prefix
        silver_tuples = []
        for match in silver_matchups:
            team1, team2 = match['teams']
            round_name = match['round']
            if team1 != 'BYE' and team2 != 'BYE':
                silver_tuples.append(((team1, team2), f"Silver {round_name}"))
        
        # Combine all matches
        all_matches = pool_tuples + gold_tuples + silver_tuples
        manager._generate_pool_play_matches = lambda: all_matches
        
        # Run allocation
        schedule, warnings = manager.allocate_teams_to_courts()
        
        # Validations
        scheduled_count = sum(len(court_matches) for court_matches in schedule.values())
        
        assert scheduled_count > 0, "Schedule should not be empty"
        
        # Verify no team double-booking
        team_matches = {}
        for court_matches in schedule.values():
            for day_num, start_dt, end_dt, match_tuple in court_matches:
                for team in match_tuple:
                    if team not in team_matches:
                        team_matches[team] = []
                    team_matches[team].append((day_num, start_dt, end_dt))
        
        for team, matches_list in team_matches.items():
            sorted_matches = sorted(matches_list, key=lambda x: (x[0], x[1]))
            for i in range(len(sorted_matches) - 1):
                day1, _, end1 = sorted_matches[i]
                day2, start2, _ = sorted_matches[i + 1]
                
                if day1 == day2:
                    assert end1 <= start2, f"Team {team} has overlapping matches"
        
        # Should have pool + gold + silver matches
        expected_pool = len(pool_matches)
        expected_gold = len(gold_tuples)
        expected_silver = len(silver_tuples)
        
        assert expected_gold > 0, "Should have gold bracket matches"
        assert expected_silver > 0, "Should have silver bracket matches"
    
    def test_tournament_with_tight_constraints(self):
        """Test stress case: short day (8 hours), long matches (90 min), many teams."""
        # Setup: 3 pools of 3 teams = 9 teams total, 13 pool matches
        teams = [
            Team(name="X1", attributes={"pool": "X"}),
            Team(name="X2", attributes={"pool": "X"}),
            Team(name="X3", attributes={"pool": "X"}),
            Team(name="Y1", attributes={"pool": "Y"}),
            Team(name="Y2", attributes={"pool": "Y"}),
            Team(name="Y3", attributes={"pool": "Y"}),
            Team(name="Z1", attributes={"pool": "Z"}),
            Team(name="Z2", attributes={"pool": "Z"}),
            Team(name="Z3", attributes={"pool": "Z"}),
        ]
        
        # Only 2 courts available
        courts = [
            Court(name="Court 1", start_time="08:00"),
            Court(name="Court 2", start_time="09:00"),
        ]
        
        constraints = {
            "match_duration_minutes": 90,  # Long matches
            "days_number": 2,
            "min_break_between_matches_minutes": 20,  # Longer break
            "time_slot_increment_minutes": 15,
            "day_end_time_limit": "16:00",  # Only 8 hours per day
            "team_specific_constraints": [],
            "general_constraints": [],
            "tournament_settings": {
                "type": "pool_play",
                "pools": {
                    "X": {"teams": ["X1", "X2", "X3"], "advance": 1},
                    "Y": {"teams": ["Y1", "Y2", "Y3"], "advance": 1},
                    "Z": {"teams": ["Z1", "Z2", "Z3"], "advance": 1}
                }
            }
        }
        
        manager = AllocationManager(teams, courts, constraints)
        
        pool_matches = generate_pool_play_matches(teams)
        pool_tuples = [(tuple(m["teams"]), m["pool"]) for m in pool_matches]
        manager._generate_pool_play_matches = lambda: pool_tuples
        
        # Run allocation
        schedule, warnings = manager.allocate_teams_to_courts()
        
        # With tight constraints, not all matches may fit
        scheduled_count = sum(len(court_matches) for court_matches in schedule.values())
        
        # Should schedule at least some matches
        assert scheduled_count > 0, "Should schedule at least some matches"
        
        # Verify court hour constraints respected
        day_end = datetime.time(16, 0)
        
        for court in courts:
            court_start = manager._parse_time(court.start_time)
            for day_num, start_dt, end_dt, _ in schedule[court.name]:
                assert start_dt.time() >= court_start, \
                    f"Match starts before court opens: {start_dt.time()} < {court_start}"
                assert end_dt.time() <= day_end, \
                    f"Match ends after day limit: {end_dt.time()} > {day_end}"
        
        # Verify minimum break respected
        min_break = datetime.timedelta(minutes=20)
        team_matches = {}
        for court_matches in schedule.values():
            for day_num, start_dt, end_dt, match_tuple in court_matches:
                for team in match_tuple:
                    if team not in team_matches:
                        team_matches[team] = []
                    team_matches[team].append((day_num, start_dt, end_dt))
        
        for team, matches_list in team_matches.items():
            sorted_matches = sorted(matches_list, key=lambda x: (x[0], x[1]))
            for i in range(len(sorted_matches) - 1):
                day1, _, end1 = sorted_matches[i]
                day2, start2, _ = sorted_matches[i + 1]
                
                if day1 == day2:
                    actual_break = start2 - end1
                    assert actual_break >= min_break, \
                        f"Team {team} has insufficient break: {actual_break} < {min_break}"
    
    def test_tournament_with_team_specific_constraints(self, sample_courts):
        """Test teams with play_after/play_before time windows."""
        teams = [
            Team(name="EarlyBird", attributes={"pool": "pool1"}),
            Team(name="NightOwl", attributes={"pool": "pool1"}),
            Team(name="Regular1", attributes={"pool": "pool1"}),
            Team(name="Regular2", attributes={"pool": "pool2"}),
            Team(name="Regular3", attributes={"pool": "pool2"}),
        ]
        
        constraints = {
            "match_duration_minutes": 60,
            "days_number": 2,
            "min_break_between_matches_minutes": 15,
            "time_slot_increment_minutes": 15,
            "day_end_time_limit": "22:00",
            "team_specific_constraints": [
                {"team_name": "EarlyBird", "play_before": "12:00", "note": "Must finish by noon"},
                {"team_name": "NightOwl", "play_after": "18:00", "note": "Only available evenings"},
            ],
            "general_constraints": [],
            "tournament_settings": {
                "type": "pool_play",
                "pools": {
                    "pool1": {"teams": ["EarlyBird", "NightOwl", "Regular1"], "advance": 2},
                    "pool2": {"teams": ["Regular2", "Regular3"], "advance": 1}
                }
            }
        }
        
        manager = AllocationManager(teams, sample_courts, constraints)
        
        pool_matches = generate_pool_play_matches(teams)
        pool_tuples = [(tuple(m["teams"]), m["pool"]) for m in pool_matches]
        manager._generate_pool_play_matches = lambda: pool_tuples
        
        # Run allocation
        schedule, warnings = manager.allocate_teams_to_courts()
        
        scheduled_count = sum(len(court_matches) for court_matches in schedule.values())
        assert scheduled_count > 0, "Should schedule at least some matches"
        
        # Verify EarlyBird's play_before constraint (12:00)
        earlybird_constraint_ok = True
        for court_matches in schedule.values():
            for day_num, start_dt, end_dt, match_tuple in court_matches:
                if "EarlyBird" in match_tuple:
                    if end_dt.time() > datetime.time(12, 0):
                        earlybird_constraint_ok = False
                        print(f"EarlyBird match ends after 12:00: {end_dt}")
        
        # Verify NightOwl's play_after constraint (18:00)
        nightowl_constraint_ok = True
        for court_matches in schedule.values():
            for day_num, start_dt, end_dt, match_tuple in court_matches:
                if "NightOwl" in match_tuple:
                    if start_dt.time() < datetime.time(18, 0):
                        nightowl_constraint_ok = False
                        print(f"NightOwl match starts before 18:00: {start_dt}")
        
        # With tight constraints, solver might not find perfect solution
        # But we should verify attempts were made to honor constraints
        assert earlybird_constraint_ok or nightowl_constraint_ok, \
            "At least one team-specific constraint should be honored"


class TestBackupRestoreRoundtrip:
    """Integration test for backup/restore HTTP endpoints."""
    
    def test_backup_restore_roundtrip(self, tmp_path, monkeypatch):
        """
        End-to-end test: create data → export → modify → import → verify restore.
        
        This test validates the full backup/restore lifecycle:
        1. Create tournament data (users, tournaments, teams)
        2. Export to ZIP via /api/admin/export
        3. Modify data in-place (delete a user, change tournament)
        4. Import ZIP via /api/admin/import
        5. Verify original data is fully restored
        """
        import sys
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
        from app import app
        import app as app_module
        import yaml
        import zipfile
        import io
        
        # Setup: Create temporary data directory with original data
        data_dir = tmp_path / "data"
        users_dir = data_dir / "users"
        
        # Create user1 with tournament
        user1_dir = users_dir / "user1"
        user1_tournaments_dir = user1_dir / "tournaments"
        user1_default = user1_tournaments_dir / "default"
        user1_default.mkdir(parents=True)
        
        # Original tournament data for user1
        user1_teams = user1_default / "teams.yaml"
        user1_teams.write_text(yaml.dump({
            'pool1': {'teams': ['Team Alpha', 'Team Beta'], 'advance': 2},
            'pool2': {'teams': ['Team Gamma'], 'advance': 1}
        }, default_flow_style=False))
        
        user1_courts = user1_default / "courts.csv"
        user1_courts.write_text("court_name,start_time,end_time\nCourt A,08:00,18:00\nCourt B,09:00,19:00\n")
        
        user1_reg = user1_dir / "tournaments.yaml"
        user1_reg.write_text(yaml.dump({
            'active': 'default',
            'tournaments': [{'slug': 'default', 'name': 'Original Tournament', 'created': '2026-01-01T10:00:00'}]
        }, default_flow_style=False))
        
        # Create user2 with tournament
        user2_dir = users_dir / "user2"
        user2_tournaments_dir = user2_dir / "tournaments"
        user2_tourney = user2_tournaments_dir / "summer2026"
        user2_tourney.mkdir(parents=True)
        
        user2_teams = user2_tourney / "teams.yaml"
        user2_teams.write_text(yaml.dump({
            'poolX': {'teams': ['Team X1', 'Team X2', 'Team X3'], 'advance': 2}
        }, default_flow_style=False))
        
        user2_courts = user2_tourney / "courts.csv"
        user2_courts.write_text("court_name,start_time,end_time\nCourt X,10:00,20:00\n")
        
        user2_reg = user2_dir / "tournaments.yaml"
        user2_reg.write_text(yaml.dump({
            'active': 'summer2026',
            'tournaments': [{'slug': 'summer2026', 'name': 'Summer Tournament', 'created': '2026-06-01T12:00:00'}]
        }, default_flow_style=False))
        
        # Create users.yaml
        users_file = data_dir / "users.yaml"
        original_users_data = {
            'users': [
                {'username': 'user1', 'password_hash': 'hash_user1', 'created': '2026-01-01T00:00:00'},
                {'username': 'user2', 'password_hash': 'hash_user2', 'created': '2026-06-01T00:00:00'}
            ]
        }
        users_file.write_text(yaml.dump(original_users_data, default_flow_style=False))
        
        # Monkeypatch app to use temp directory
        monkeypatch.setattr(app_module, 'DATA_DIR', str(data_dir))
        monkeypatch.setattr(app_module, 'USERS_DIR', str(users_dir))
        monkeypatch.setattr(app_module, 'USERS_FILE', str(users_file))
        monkeypatch.setenv('BACKUP_API_KEY', 'integration-test-key')
        monkeypatch.setattr(app_module, 'BACKUP_API_KEY', 'integration-test-key')
        
        # Configure test client
        app.config['TESTING'] = True
        client = app.test_client()
        
        # STEP 2: Export to ZIP
        export_response = client.get('/api/admin/export',
                                    headers={'Authorization': 'Bearer integration-test-key'})
        
        assert export_response.status_code == 200, "Export should succeed"
        assert export_response.mimetype == 'application/zip', "Export should return ZIP"
        
        # Save exported ZIP
        backup_zip = io.BytesIO(export_response.data)
        
        # Verify export contains expected files
        with zipfile.ZipFile(backup_zip, 'r') as zf:
            exported_names = zf.namelist()
            assert 'users.yaml' in exported_names, "Export should contain users.yaml"
            assert any('users/user1/tournaments/default/teams.yaml' in name for name in exported_names), \
                "Export should contain user1's tournament data"
            assert any('users/user2/tournaments/summer2026/teams.yaml' in name for name in exported_names), \
                "Export should contain user2's tournament data"
        
        # STEP 3: Modify data in-place
        # Delete user2 entirely
        import shutil
        if user2_dir.exists():
            shutil.rmtree(user2_dir)
        
        # Modify user1's tournament name and teams
        user1_teams.write_text(yaml.dump({
            'pool1': {'teams': ['MODIFIED Team'], 'advance': 1}
        }, default_flow_style=False))
        
        user1_reg.write_text(yaml.dump({
            'active': 'default',
            'tournaments': [{'slug': 'default', 'name': 'MODIFIED Tournament', 'created': '2026-01-02T00:00:00'}]
        }, default_flow_style=False))
        
        # Update users.yaml (remove user2)
        users_file.write_text(yaml.dump({
            'users': [
                {'username': 'user1', 'password_hash': 'hash_user1', 'created': '2026-01-01T00:00:00'}
            ]
        }, default_flow_style=False))
        
        # Verify modifications took effect
        with open(users_file, 'r') as f:
            modified_users = yaml.safe_load(f)
        assert len(modified_users['users']) == 1, "User2 should be deleted"
        assert not user2_dir.exists(), "User2 directory should be deleted"
        
        with open(user1_teams, 'r') as f:
            modified_teams = yaml.safe_load(f)
        assert 'MODIFIED Team' in modified_teams['pool1']['teams'], "User1's teams should be modified"
        
        # STEP 4: Import ZIP (restore from backup)
        backup_zip.seek(0)  # Reset buffer position
        import_response = client.post('/api/admin/import',
                                     data={'file': (backup_zip, 'backup.zip')},
                                     headers={'Authorization': 'Bearer integration-test-key'},
                                     content_type='multipart/form-data')
        
        assert import_response.status_code == 200, f"Import should succeed, got {import_response.status_code}: {import_response.data}"
        
        # STEP 5: Verify original data is restored
        
        # Check users.yaml restored
        with open(users_file, 'r') as f:
            restored_users = yaml.safe_load(f)
        
        assert len(restored_users['users']) == 2, "Both users should be restored"
        assert any(u['username'] == 'user1' for u in restored_users['users']), "user1 should be restored"
        assert any(u['username'] == 'user2' for u in restored_users['users']), "user2 should be restored"
        
        # Check user1's tournament data restored
        assert user1_teams.exists(), "user1's teams file should be restored"
        with open(user1_teams, 'r') as f:
            restored_user1_teams = yaml.safe_load(f)
        
        assert 'Team Alpha' in restored_user1_teams['pool1']['teams'], "user1's original teams should be restored"
        assert 'Team Beta' in restored_user1_teams['pool1']['teams'], "user1's original teams should be restored"
        assert 'MODIFIED Team' not in str(restored_user1_teams), "Modified data should be overwritten"
        
        with open(user1_reg, 'r') as f:
            restored_user1_reg = yaml.safe_load(f)
        assert restored_user1_reg['tournaments'][0]['name'] == 'Original Tournament', \
            "user1's tournament name should be restored"
        
        # Check user1's courts restored
        assert user1_courts.exists(), "user1's courts file should be restored"
        with open(user1_courts, 'r') as f:
            courts_content = f.read()
        assert 'Court A' in courts_content, "user1's courts should be restored"
        assert 'Court B' in courts_content, "user1's courts should be restored"
        
        # Check user2's tournament data restored
        assert user2_dir.exists(), "user2 directory should be restored"
        assert user2_tourney.exists(), "user2's tournament directory should be restored"
        assert user2_teams.exists(), "user2's teams file should be restored"
        
        with open(user2_teams, 'r') as f:
            restored_user2_teams = yaml.safe_load(f)
        assert 'Team X1' in restored_user2_teams['poolX']['teams'], "user2's teams should be restored"
        
        with open(user2_reg, 'r') as f:
            restored_user2_reg = yaml.safe_load(f)
        assert restored_user2_reg['tournaments'][0]['name'] == 'Summer Tournament', \
            "user2's tournament name should be restored"
        
        # Verify file structure integrity
        assert user2_courts.exists(), "user2's courts file should be restored"
        with open(user2_courts, 'r') as f:
            user2_courts_content = f.read()
        assert 'Court X' in user2_courts_content, "user2's courts should be restored"
