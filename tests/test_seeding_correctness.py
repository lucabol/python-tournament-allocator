"""
Unit tests for gold bracket seeding correctness.

Tests validate that seed_teams_from_pools() correctly implements:
1. Position-based grouping (all #1 finishers before #2 finishers)
2. Tiebreaker hierarchy: wins > set_diff > point_diff > pool_name
3. Placeholder handling before standings are finalized
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from core.elimination import seed_teams_from_pools


class TestGoldBracketSeeding:
    """Tests for gold bracket seeding from pool standings."""
    
    def test_gold_seeding_single_pool_by_wins(self):
        """Test that teams within a single pool are ordered by wins."""
        pools = {
            'PoolA': {'teams': ['Team1', 'Team2', 'Team3'], 'advance': 2}
        }
        
        # Create standings with clear win hierarchy
        standings = {
            'PoolA': [
                {'team': 'Eagles', 'wins': 5, 'losses': 0, 'set_diff': 10, 'point_diff': 50, 'matches_played': 5},
                {'team': 'Hawks', 'wins': 3, 'losses': 2, 'set_diff': 2, 'point_diff': 10, 'matches_played': 5},
                {'team': 'Falcons', 'wins': 2, 'losses': 3, 'set_diff': -5, 'point_diff': -20, 'matches_played': 5},
            ]
        }
        
        seeded = seed_teams_from_pools(pools, standings)
        
        # Should have 2 teams (top 2 from PoolA)
        assert len(seeded) == 2
        
        # Verify team names are from standings
        assert seeded[0][0] == 'Eagles'  # 5 wins - seed 1
        assert seeded[1][0] == 'Hawks'   # 3 wins - seed 2
        
        # Verify seeds
        assert seeded[0][1] == 1
        assert seeded[1][1] == 2
        
        # Verify pool tracking
        assert seeded[0][2] == 'PoolA'
        assert seeded[1][2] == 'PoolA'
    
    def test_gold_seeding_multi_pool_position_priority(self):
        """Test that all #1 finishers are seeded before all #2 finishers."""
        pools = {
            'PoolA': {'teams': ['T1', 'T2', 'T3'], 'advance': 2},
            'PoolB': {'teams': ['T4', 'T5', 'T6'], 'advance': 2},
            'PoolC': {'teams': ['T7', 'T8', 'T9'], 'advance': 2}
        }
        
        # Pool winners vary in strength, but all should seed 1-3
        # Pool runners-up also vary, but all should seed 4-6
        standings = {
            'PoolA': [
                {'team': 'Strong1', 'wins': 6, 'losses': 0, 'set_diff': 15, 'point_diff': 80, 'matches_played': 6},
                {'team': 'Weak2', 'wins': 2, 'losses': 4, 'set_diff': -8, 'point_diff': -40, 'matches_played': 6},
            ],
            'PoolB': [
                {'team': 'Medium1', 'wins': 4, 'losses': 2, 'set_diff': 5, 'point_diff': 20, 'matches_played': 6},
                {'team': 'Strong2', 'wins': 5, 'losses': 1, 'set_diff': 12, 'point_diff': 60, 'matches_played': 6},
            ],
            'PoolC': [
                {'team': 'Weak1', 'wins': 3, 'losses': 3, 'set_diff': 0, 'point_diff': 5, 'matches_played': 6},
                {'team': 'Medium2', 'wins': 3, 'losses': 3, 'set_diff': 2, 'point_diff': 15, 'matches_played': 6},
            ]
        }
        
        seeded = seed_teams_from_pools(pools, standings)
        
        assert len(seeded) == 6
        
        # All #1 finishers must be seeded 1-3 (regardless of their stats)
        first_place_teams = {'Strong1', 'Medium1', 'Weak1'}
        top_3_seeds = {seeded[i][0] for i in range(3)}
        assert top_3_seeds == first_place_teams, "All pool winners must get seeds 1-3"
        
        # All #2 finishers must be seeded 4-6
        second_place_teams = {'Weak2', 'Strong2', 'Medium2'}
        bottom_3_seeds = {seeded[i][0] for i in range(3, 6)}
        assert bottom_3_seeds == second_place_teams, "All pool runners-up must get seeds 4-6"
        
        # Within position groups, verify tiebreaker order (wins desc)
        # Among #1 finishers: Strong1 (6w) > Medium1 (4w) > Weak1 (3w)
        assert seeded[0][0] == 'Strong1'  # seed 1
        assert seeded[1][0] == 'Medium1'  # seed 2
        assert seeded[2][0] == 'Weak1'    # seed 3
        
        # Among #2 finishers: Strong2 (5w) > Medium2 (3w) > Weak2 (2w)
        assert seeded[3][0] == 'Strong2'  # seed 4
        assert seeded[4][0] == 'Medium2'  # seed 5
        assert seeded[5][0] == 'Weak2'    # seed 6
    
    def test_gold_seeding_tiebreaker_wins_then_set_diff(self):
        """Test tiebreaker when teams have same position but different stats."""
        pools = {
            'PoolA': {'teams': ['T1', 'T2'], 'advance': 1},
            'PoolB': {'teams': ['T3', 'T4'], 'advance': 1},
            'PoolC': {'teams': ['T5', 'T6'], 'advance': 1},
            'PoolD': {'teams': ['T7', 'T8'], 'advance': 1}
        }
        
        # All #1 finishers, but with different wins and set_diff
        standings = {
            'PoolA': [
                {'team': 'TeamA1', 'wins': 5, 'losses': 0, 'set_diff': 8, 'point_diff': 40, 'matches_played': 5},
            ],
            'PoolB': [
                {'team': 'TeamB1', 'wins': 5, 'losses': 0, 'set_diff': 12, 'point_diff': 35, 'matches_played': 5},
            ],
            'PoolC': [
                {'team': 'TeamC1', 'wins': 4, 'losses': 1, 'set_diff': 10, 'point_diff': 50, 'matches_played': 5},
            ],
            'PoolD': [
                {'team': 'TeamD1', 'wins': 5, 'losses': 0, 'set_diff': 6, 'point_diff': 60, 'matches_played': 5},
            ],
        }
        
        seeded = seed_teams_from_pools(pools, standings)
        
        assert len(seeded) == 4
        
        # First tiebreaker: wins (higher is better)
        # 5-0 teams should beat 4-1 team
        assert seeded[3][0] == 'TeamC1', "4-1 record should be seeded last"
        
        # Among 5-0 teams, second tiebreaker: set_diff (higher is better)
        # TeamB1 (12) > TeamA1 (8) > TeamD1 (6)
        three_way_tie = [seeded[i][0] for i in range(3)]
        assert three_way_tie == ['TeamB1', 'TeamA1', 'TeamD1'], \
            "Among tied wins, higher set_diff should seed higher"
    
    def test_gold_seeding_tiebreaker_all_stats(self):
        """Test complete tiebreaker hierarchy: wins > set_diff > point_diff > pool_name."""
        pools = {
            'PoolA': {'teams': ['T1', 'T2'], 'advance': 1},
            'PoolB': {'teams': ['T3', 'T4'], 'advance': 1},
            'PoolC': {'teams': ['T5', 'T6'], 'advance': 1},
            'PoolD': {'teams': ['T7', 'T8'], 'advance': 1},
            'PoolE': {'teams': ['T9', 'T10'], 'advance': 1}
        }
        
        # Create standings that test all tiebreaker levels
        standings = {
            'PoolA': [
                {'team': 'Team1', 'wins': 4, 'losses': 1, 'set_diff': 6, 'point_diff': 30, 'matches_played': 5},
            ],
            'PoolB': [
                {'team': 'Team2', 'wins': 4, 'losses': 1, 'set_diff': 6, 'point_diff': 45, 'matches_played': 5},
            ],
            'PoolC': [
                {'team': 'Team3', 'wins': 4, 'losses': 1, 'set_diff': 8, 'point_diff': 25, 'matches_played': 5},
            ],
            'PoolD': [
                {'team': 'Team4', 'wins': 4, 'losses': 1, 'set_diff': 6, 'point_diff': 30, 'matches_played': 5},
            ],
            'PoolE': [
                {'team': 'Team5', 'wins': 5, 'losses': 0, 'set_diff': 4, 'point_diff': 20, 'matches_played': 5},
            ]
        }
        
        seeded = seed_teams_from_pools(pools, standings)
        
        assert len(seeded) == 5
        
        # 1. Wins tiebreaker: Team5 (5 wins) should be seed 1
        assert seeded[0][0] == 'Team5', "Most wins should be seed 1"
        
        # 2. Set_diff tiebreaker: Team3 (set_diff=8) should be seed 2
        assert seeded[1][0] == 'Team3', "Among 4-1 teams, highest set_diff should be seed 2"
        
        # 3. Point_diff tiebreaker: Team2 (point_diff=45) should beat others with set_diff=6
        assert seeded[2][0] == 'Team2', "Among set_diff=6 teams, highest point_diff should be seed 3"
        
        # 4. Pool_name tiebreaker: Team1 (PoolA) vs Team4 (PoolD) - both 4-1, set_diff=6, point_diff=30
        #    PoolA comes before PoolD alphabetically
        assert seeded[3][0] == 'Team1', "Alphabetically earlier pool should break final tie"
        assert seeded[4][0] == 'Team4'
    
    def test_gold_seeding_with_placeholder_teams(self):
        """Test seeding before standings are finalized (no matches played yet)."""
        pools = {
            'PoolA': {'teams': ['T1', 'T2', 'T3'], 'advance': 2},
            'PoolB': {'teams': ['T4', 'T5', 'T6'], 'advance': 2}
        }
        
        # Standings exist but no matches played yet (or some teams haven't played)
        standings = {
            'PoolA': [
                {'team': 'Eagles', 'wins': 3, 'losses': 0, 'set_diff': 8, 'point_diff': 40, 'matches_played': 3},
                {'team': 'Hawks', 'wins': 0, 'losses': 0, 'set_diff': 0, 'point_diff': 0, 'matches_played': 0},  # Not played
            ],
            'PoolB': [
                {'team': 'Falcons', 'wins': 0, 'losses': 0, 'set_diff': 0, 'point_diff': 0, 'matches_played': 0},
                {'team': 'Owls', 'wins': 0, 'losses': 0, 'set_diff': 0, 'point_diff': 0, 'matches_played': 0},
            ]
        }
        
        seeded = seed_teams_from_pools(pools, standings)
        
        assert len(seeded) == 4
        
        # Team that has played should use actual name
        assert seeded[0][0] == 'Eagles', "Team with matches_played > 0 should use actual name"
        
        # Teams without matches should use placeholder format
        assert seeded[1][0] == '#1 PoolB', "Team with matches_played=0 should use placeholder"
        assert seeded[2][0] == '#2 PoolA', "Second place unplayed team should use placeholder"
        assert seeded[3][0] == '#2 PoolB', "Second place unplayed team should use placeholder"
        
        # Verify seed numbers are sequential
        assert [s[1] for s in seeded] == [1, 2, 3, 4]
    
    def test_gold_seeding_empty_pools(self):
        """Test edge case with no pools."""
        seeded = seed_teams_from_pools({})
        assert seeded == []
    
    def test_gold_seeding_no_standings(self):
        """Test seeding without any standings data (all placeholders)."""
        pools = {
            'PoolA': {'teams': ['T1', 'T2'], 'advance': 1},
            'PoolB': {'teams': ['T3', 'T4'], 'advance': 1}
        }
        
        # No standings provided
        seeded = seed_teams_from_pools(pools, standings=None)
        
        assert len(seeded) == 2
        
        # Should use placeholder format, sorted by pool name
        assert seeded[0][0] == '#1 PoolA'
        assert seeded[1][0] == '#1 PoolB'
        
        # Pool name alphabetical sort should apply
        assert seeded[0][2] == 'PoolA'
        assert seeded[1][2] == 'PoolB'
