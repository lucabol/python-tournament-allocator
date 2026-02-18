"""
Test to verify schedule generator and display generator produce identical matchups.

This is a critical integration test for the bug where Schedule/Live tabs show
different matches than the Brackets tab.
"""
import pytest
from src.core.double_elimination import (
    generate_double_elimination_bracket,
    generate_double_bracket_with_results,
    generate_double_elimination_matches_for_scheduling
)


def test_schedule_and_display_produce_identical_gold_bracket_matchups():
    """
    CRITICAL: Schedule and display generators must create identical first-round pairings.
    
    Regression test for: "Schedule shows Adam-Rob vs Derek-Lily but Brackets shows
    Adam-Rob vs Brian-Pat" bug.
    """
    # 4 pools, top 2 advance = 8 teams in bracket
    pools = {
        'Pool A': {'teams': ['A1', 'A2', 'A3', 'A4'], 'advance': 2},
        'Pool B': {'teams': ['B1', 'B2', 'B3', 'B4'], 'advance': 2},
        'Pool C': {'teams': ['C1', 'C2', 'C3', 'C4'], 'advance': 2},
        'Pool D': {'teams': ['D1', 'D2', 'D3', 'D4'], 'advance': 2}
    }
    
    # Mock standings (sorted, as would come from calculate_pool_standings)
    standings = {
        'Pool A': [
            {'team': 'A1', 'wins': 3, 'losses': 0, 'matches_played': 3, 'set_diff': 6, 'point_diff': 30},
            {'team': 'A2', 'wins': 2, 'losses': 1, 'matches_played': 3, 'set_diff': 2, 'point_diff': 10}
        ],
        'Pool B': [
            {'team': 'B1', 'wins': 3, 'losses': 0, 'matches_played': 3, 'set_diff': 6, 'point_diff': 30},
            {'team': 'B2', 'wins': 2, 'losses': 1, 'matches_played': 3, 'set_diff': 2, 'point_diff': 10}
        ],
        'Pool C': [
            {'team': 'C1', 'wins': 3, 'losses': 0, 'matches_played': 3, 'set_diff': 6, 'point_diff': 30},
            {'team': 'C2', 'wins': 2, 'losses': 1, 'matches_played': 3, 'set_diff': 2, 'point_diff': 10}
        ],
        'Pool D': [
            {'team': 'D1', 'wins': 3, 'losses': 0, 'matches_played': 3, 'set_diff': 6, 'point_diff': 30},
            {'team': 'D2', 'wins': 2, 'losses': 1, 'matches_played': 3, 'set_diff': 2, 'point_diff': 10}
        ]
    }
    
    # Generate bracket for scheduling (what goes into schedule.yaml)
    schedule_bracket = generate_double_elimination_bracket(pools, standings)
    
    # Generate bracket for display (what Brackets tab shows)
    display_bracket = generate_double_bracket_with_results(pools, standings, bracket_results={})
    
    # Extract first round winners bracket matchups from both
    schedule_first_round_name = list(schedule_bracket['winners_bracket'].keys())[0]
    display_first_round_name = list(display_bracket['winners_bracket'].keys())[0]
    
    assert schedule_first_round_name == display_first_round_name, \
        f"First round name mismatch: schedule={schedule_first_round_name}, display={display_first_round_name}"
    
    schedule_matches = schedule_bracket['winners_bracket'][schedule_first_round_name]
    display_matches = display_bracket['winners_bracket'][display_first_round_name]
    
    # Both should have same number of matches
    assert len(schedule_matches) == len(display_matches), \
        f"Match count mismatch: schedule has {len(schedule_matches)}, display has {len(display_matches)}"
    
    # Compare each match pairing (should be identical)
    for i, (sched_match, disp_match) in enumerate(zip(schedule_matches, display_matches)):
        sched_teams = tuple(sorted(sched_match['teams']))
        disp_teams = tuple(sorted(disp_match['teams']))
        
        assert sched_teams == disp_teams, \
            f"Match {i+1} pairing mismatch:\n  Schedule: {sched_match['teams']}\n  Display:  {disp_match['teams']}"


def test_schedule_matches_for_scheduling_matches_bracket_structure():
    """
    Verify that generate_double_elimination_matches_for_scheduling produces
    matches that match the bracket structure from generate_double_elimination_bracket.
    """
    pools = {
        'Pool A': {'teams': ['A1', 'A2', 'A3', 'A4'], 'advance': 2},
        'Pool B': {'teams': ['B1', 'B2', 'B3', 'B4'], 'advance': 2},
        'Pool C': {'teams': ['C1', 'C2', 'C3', 'C4'], 'advance': 2},
        'Pool D': {'teams': ['D1', 'D2', 'D3', 'D4'], 'advance': 2}
    }
    
    standings = {
        'Pool A': [
            {'team': 'A1', 'wins': 3, 'losses': 0, 'matches_played': 3, 'set_diff': 6, 'point_diff': 30},
            {'team': 'A2', 'wins': 2, 'losses': 1, 'matches_played': 3, 'set_diff': 2, 'point_diff': 10}
        ],
        'Pool B': [
            {'team': 'B1', 'wins': 3, 'losses': 0, 'matches_played': 3, 'set_diff': 6, 'point_diff': 30},
            {'team': 'B2', 'wins': 2, 'losses': 1, 'matches_played': 3, 'set_diff': 2, 'point_diff': 10}
        ],
        'Pool C': [
            {'team': 'C1', 'wins': 3, 'losses': 0, 'matches_played': 3, 'set_diff': 6, 'point_diff': 30},
            {'team': 'C2', 'wins': 2, 'losses': 1, 'matches_played': 3, 'set_diff': 2, 'point_diff': 10}
        ],
        'Pool D': [
            {'team': 'D1', 'wins': 3, 'losses': 0, 'matches_played': 3, 'set_diff': 6, 'point_diff': 30},
            {'team': 'D2', 'wins': 2, 'losses': 1, 'matches_played': 3, 'set_diff': 2, 'point_diff': 10}
        ]
    }
    
    # Get matches for scheduling
    schedule_matches = generate_double_elimination_matches_for_scheduling(pools, standings)
    
    # Get bracket structure
    bracket = generate_double_elimination_bracket(pools, standings)
    first_round = list(bracket['winners_bracket'].values())[0]
    
    # Extract non-bye matches from bracket
    bracket_match_pairs = []
    for match in first_round:
        if not match.get('is_bye') and not match.get('is_placeholder'):
            bracket_match_pairs.append(tuple(sorted(match['teams'])))
    
    # Extract match pairs from schedule matches
    schedule_match_pairs = [tuple(sorted(teams)) for teams, _ in schedule_matches]
    
    # Should have same matches
    assert set(schedule_match_pairs) == set(bracket_match_pairs), \
        f"Mismatch between scheduling and bracket:\n  Scheduling: {schedule_match_pairs}\n  Bracket: {bracket_match_pairs}"
