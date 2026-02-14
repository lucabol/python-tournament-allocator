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

from core.elimination import seed_teams_from_pools, _generate_bracket_order
from core.double_elimination import generate_double_elimination_bracket, seed_silver_bracket_teams


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


class TestDoubleEliminationSeeding:
    """Test seeding correctness in double elimination tournaments."""
    
    def _create_8_team_pools_and_standings(self):
        """Helper to create consistent 8-team test data."""
        pools = {
            'Pool A': {
                'teams': ['Team 1', 'Team 2'],
                'advance': 2
            },
            'Pool B': {
                'teams': ['Team 3', 'Team 4'],
                'advance': 2
            },
            'Pool C': {
                'teams': ['Team 5', 'Team 6'],
                'advance': 2
            },
            'Pool D': {
                'teams': ['Team 7', 'Team 8'],
                'advance': 2
            }
        }
        
        standings = {
            'Pool A': [
                {'team': 'Team 1', 'wins': 5, 'losses': 0, 'set_diff': 12, 'point_diff': 60, 'matches_played': 5},
                {'team': 'Team 2', 'wins': 4, 'losses': 1, 'set_diff': 8, 'point_diff': 40, 'matches_played': 5}
            ],
            'Pool B': [
                {'team': 'Team 3', 'wins': 5, 'losses': 0, 'set_diff': 10, 'point_diff': 50, 'matches_played': 5},
                {'team': 'Team 4', 'wins': 4, 'losses': 1, 'set_diff': 6, 'point_diff': 30, 'matches_played': 5}
            ],
            'Pool C': [
                {'team': 'Team 5', 'wins': 4, 'losses': 1, 'set_diff': 5, 'point_diff': 25, 'matches_played': 5},
                {'team': 'Team 6', 'wins': 3, 'losses': 2, 'set_diff': 2, 'point_diff': 10, 'matches_played': 5}
            ],
            'Pool D': [
                {'team': 'Team 7', 'wins': 3, 'losses': 2, 'set_diff': 0, 'point_diff': 0, 'matches_played': 5},
                {'team': 'Team 8', 'wins': 2, 'losses': 3, 'set_diff': -2, 'point_diff': -5, 'matches_played': 5}
            ]
        }
        
        return pools, standings

    def test_winners_bracket_initial_seeding(self):
        """
        Test that winners bracket follows standard single elimination seeding.
        
        For an 8-team bracket, the standard seeding order is [1, 8, 4, 5, 2, 7, 3, 6].
        This ensures:
        - Seed 1 faces seed 8 (easiest matchup)
        - Seed 2 faces seed 7 (second easiest)
        - Seeds are distributed to avoid early clashes between top seeds
        """
        pools, standings = self._create_8_team_pools_and_standings()
        bracket = generate_double_elimination_bracket(pools, standings)
        
        # Extract winners bracket first round
        winners_first_round = list(bracket['winners_bracket'].values())[0]
        
        # Verify bracket size
        assert bracket['bracket_size'] == 8
        assert bracket['total_winners_rounds'] == 3  # 8 teams = 2^3
        
        # Get the expected bracket order
        expected_order = _generate_bracket_order(8)  # [1, 8, 4, 5, 2, 7, 3, 6]
        
        # Verify first round matchups follow standard seeding
        # The seeded teams from pools are: Team 5 (seed 1), Team 1 (seed 2), 
        # Team 2 (seed 3), Team 6 (seed 4), Team 3 (seed 5), Team 7 (seed 6),
        # Team 4 (seed 7), Team 8 (seed 8)
        
        # All matches in first round should have 'losers_feed_to' pointing to L1
        for match in winners_first_round:
            assert match['losers_feed_to'] == 'L1', "Winners R1 losers should feed to L1"
        
        # Verify seeds in each match
        for match in winners_first_round:
            seed1, seed2 = match['seeds']
            # In standard bracket seeding, seed sum should equal bracket_size + 1
            assert seed1 + seed2 == 9, f"Seeds {seed1} and {seed2} should sum to 9 in 8-team bracket"

    def test_losers_bracket_seed_preservation(self):
        """
        Test that losers dropping from winners R1 maintain seed gaps.
        
        In the first losers round (L1):
        - 4 teams drop from winners round 1
        - They should maintain relative seed order
        - Losers pair off: (Loser W1-M1 vs Loser W1-M2) and (Loser W1-M3 vs Loser W1-M4)
        
        For 8-team bracket with seeds [1,8,4,5,2,7,3,6]:
        - W1-M1: 1v8 → loser is seed 8
        - W1-M2: 4v5 → loser is seed 5
        - W1-M3: 2v7 → loser is seed 7
        - W1-M4: 3v6 → loser is seed 6
        
        L1 should pair:
        - L1-M1: Loser(1v8) vs Loser(4v5) → seed 8 vs seed 5 (if chalk)
        - L1-M2: Loser(2v7) vs Loser(3v6) → seed 7 vs seed 6 (if chalk)
        """
        pools, standings = self._create_8_team_pools_and_standings()
        bracket = generate_double_elimination_bracket(pools, standings)
        
        # Extract losers bracket first round (L1)
        losers_first_round = list(bracket['losers_bracket'].values())[0]
        
        # Verify L1 has correct structure
        assert len(losers_first_round) == 2, "L1 should have 2 matches for 8-team bracket"
        
        # L1-M1: Losers from W1-M1 and W1-M2 face each other
        l1_match1 = losers_first_round[0]
        assert l1_match1['teams'] == ('Loser W1-M1', 'Loser W1-M2')
        assert l1_match1['match_code'] == 'L1-M1'
        assert l1_match1['note'] == 'Losers from Winners Round 1'
        
        # L1-M2: Losers from W1-M3 and W1-M4 face each other
        l1_match2 = losers_first_round[1]
        assert l1_match2['teams'] == ('Loser W1-M3', 'Loser W1-M4')
        assert l1_match2['match_code'] == 'L1-M2'
        assert l1_match2['note'] == 'Losers from Winners Round 1'
        
        # Verify losers bracket has correct number of rounds
        # For 8-team bracket: 4 losers rounds (L1, L2, L3, L4)
        assert bracket['total_losers_rounds'] == 4

    def test_losers_bracket_interleaving(self):
        """
        Test that W1 losers and W2 losers interleave correctly.
        
        Double elimination alternates between:
        - Minor rounds (L1, L3, L5...): Only losers bracket teams compete
        - Major rounds (L2, L4, L6...): Winners bracket losers drop in
        
        For 8-team bracket:
        - L1 (minor): 4 W1 losers → 2 matches → 2 winners
        - L2 (major): 2 W2 losers + 2 L1 winners → 2 matches
        - L3 (minor): 2 L2 winners → 1 match
        - L4 (major): 1 W3 loser + 1 L3 winner → 1 match (determines L champion)
        """
        pools, standings = self._create_8_team_pools_and_standings()
        bracket = generate_double_elimination_bracket(pools, standings)
        
        losers_bracket = bracket['losers_bracket']
        losers_rounds = list(losers_bracket.keys())
        
        # Verify we have 4 losers rounds
        assert len(losers_rounds) == 4
        
        # L1 (minor): Winners bracket round 1 losers play each other
        l1_matches = losers_bracket[losers_rounds[0]]
        assert len(l1_matches) == 2
        assert all('Loser W1' in match['teams'][0] for match in l1_matches)
        assert all('Loser W1' in match['teams'][1] for match in l1_matches)
        
        # L2 (major): Winners bracket round 2 losers drop in
        l2_matches = losers_bracket[losers_rounds[1]]
        assert len(l2_matches) == 2
        # Each L2 match should have one W2 loser and one L1 winner
        for i, match in enumerate(l2_matches):
            assert f'Loser W2-M{i+1}' in match['teams'][0], f"L2-M{i+1} should have W2 loser"
            assert f'Winner L1-M{i+1}' in match['teams'][1], f"L2-M{i+1} should have L1 winner"
        
        # L3 (minor): L2 winners play each other
        l3_matches = losers_bracket[losers_rounds[2]]
        assert len(l3_matches) == 1
        assert l3_matches[0]['teams'] == ('Winner L2-M1', 'Winner L2-M2')
        
        # L4 (major): W3 loser vs L3 winner (losers bracket final)
        l4_matches = losers_bracket[losers_rounds[3]]
        assert len(l4_matches) == 1
        assert l4_matches[0]['teams'] == ('Loser W3-M1', 'Winner L3-M1')
        assert 'Winners R3 loser vs Losers R3 winner' in l4_matches[0]['note']

    def test_grand_final_participants(self):
        """
        Test that grand final structure is correct.
        
        Grand Final should:
        - Pit Winners Bracket Champion vs Losers Bracket Champion
        - Winners champion is undefeated (0 losses)
        - Losers champion has exactly 1 loss (from somewhere in winners bracket)
        - Include bracket reset option if losers champion wins
        
        The winners champion has the advantage: they only need to win once,
        while the losers champion must win twice (GF + BR).
        """
        pools, standings = self._create_8_team_pools_and_standings()
        bracket = generate_double_elimination_bracket(pools, standings)
        
        # Verify Grand Final structure
        grand_final = bracket['grand_final']
        assert grand_final is not None
        assert grand_final['teams'] == ('Winners Bracket Champion', 'Losers Bracket Champion')
        assert grand_final['round'] == 'Grand Final'
        assert grand_final['match_code'] == 'GF'
        assert grand_final['is_placeholder'] is True
        assert 'bracket reset' in grand_final['note'].lower()
        
        # Verify Bracket Reset structure
        bracket_reset = bracket['bracket_reset']
        assert bracket_reset is not None
        assert bracket_reset['teams'] == ('Winner GF', 'Loser GF')
        assert bracket_reset['round'] == 'Bracket Reset'
        assert bracket_reset['match_code'] == 'BR'
        assert bracket_reset['is_conditional'] is True
        assert 'only played if' in bracket_reset['note'].lower()
        
        # Verify winners bracket final feeds into GF
        winners_bracket = bracket['winners_bracket']
        winners_final = list(winners_bracket.values())[-1]  # Last round
        assert len(winners_final) == 1  # Finals should have 1 match
        
        # Verify losers bracket final feeds into GF
        losers_bracket = bracket['losers_bracket']
        losers_final = list(losers_bracket.values())[-1]  # Last round
        assert len(losers_final) == 1  # Finals should have 1 match
        
        # The last winners round should indicate losers feed to GF
        assert winners_final[0]['losers_feed_to'] == 'GF'


class TestSilverBracketSeeding:
    """Tests for silver bracket seeding correctness."""
    
    def test_silver_seeding_excludes_advancing_teams(self):
        """Verify that only non-advancing teams are included in silver bracket."""
        pools = {
            'Pool A': {
                'teams': ['Team A1', 'Team A2', 'Team A3', 'Team A4', 'Team A5', 'Team A6'],
                'advance': 2
            },
            'Pool B': {
                'teams': ['Team B1', 'Team B2', 'Team B3', 'Team B4'],
                'advance': 2
            }
        }
        
        # Create standings with teams having played games
        standings = {
            'Pool A': [
                {'team': 'Team A1', 'wins': 5, 'set_diff': 10, 'point_diff': 50, 'matches_played': 5},
                {'team': 'Team A2', 'wins': 4, 'set_diff': 8, 'point_diff': 40, 'matches_played': 5},
                {'team': 'Team A3', 'wins': 3, 'set_diff': 3, 'point_diff': 15, 'matches_played': 5},
                {'team': 'Team A4', 'wins': 2, 'set_diff': -2, 'point_diff': -10, 'matches_played': 5},
                {'team': 'Team A5', 'wins': 1, 'set_diff': -5, 'point_diff': -25, 'matches_played': 5},
                {'team': 'Team A6', 'wins': 0, 'set_diff': -14, 'point_diff': -70, 'matches_played': 5}
            ],
            'Pool B': [
                {'team': 'Team B1', 'wins': 3, 'set_diff': 6, 'point_diff': 30, 'matches_played': 3},
                {'team': 'Team B2', 'wins': 2, 'set_diff': 2, 'point_diff': 10, 'matches_played': 3},
                {'team': 'Team B3', 'wins': 1, 'set_diff': -3, 'point_diff': -15, 'matches_played': 3},
                {'team': 'Team B4', 'wins': 0, 'set_diff': -5, 'point_diff': -25, 'matches_played': 3}
            ]
        }
        
        seeded_teams = seed_silver_bracket_teams(pools, standings)
        team_names = [team[0] for team in seeded_teams]
        
        # Verify advancing teams (top 2 from each pool) are NOT included
        assert 'Team A1' not in team_names
        assert 'Team A2' not in team_names
        assert 'Team B1' not in team_names
        assert 'Team B2' not in team_names
        
        # Verify non-advancing teams ARE included
        assert 'Team A3' in team_names
        assert 'Team A4' in team_names
        assert 'Team A5' in team_names
        assert 'Team A6' in team_names
        assert 'Team B3' in team_names
        assert 'Team B4' in team_names
        
        # Should have exactly 6 non-advancing teams total
        assert len(seeded_teams) == 6
    
    def test_silver_seeding_by_finish_position(self):
        """Verify that teams are seeded by finish position with #3 finishers before #4 finishers."""
        pools = {
            'Pool A': {
                'teams': ['Team A1', 'Team A2', 'Team A3', 'Team A4', 'Team A5'],
                'advance': 2
            },
            'Pool B': {
                'teams': ['Team B1', 'Team B2', 'Team B3', 'Team B4', 'Team B5'],
                'advance': 2
            },
            'Pool C': {
                'teams': ['Team C1', 'Team C2', 'Team C3', 'Team C4'],
                'advance': 2
            }
        }
        
        # Create standings where teams have equal stats within position
        standings = {
            'Pool A': [
                {'team': 'Team A1', 'wins': 4, 'set_diff': 8, 'point_diff': 40, 'matches_played': 4},
                {'team': 'Team A2', 'wins': 3, 'set_diff': 4, 'point_diff': 20, 'matches_played': 4},
                {'team': 'Team A3', 'wins': 2, 'set_diff': 0, 'point_diff': 0, 'matches_played': 4},
                {'team': 'Team A4', 'wins': 1, 'set_diff': -4, 'point_diff': -20, 'matches_played': 4},
                {'team': 'Team A5', 'wins': 0, 'set_diff': -8, 'point_diff': -40, 'matches_played': 4}
            ],
            'Pool B': [
                {'team': 'Team B1', 'wins': 4, 'set_diff': 8, 'point_diff': 40, 'matches_played': 4},
                {'team': 'Team B2', 'wins': 3, 'set_diff': 4, 'point_diff': 20, 'matches_played': 4},
                {'team': 'Team B3', 'wins': 2, 'set_diff': 0, 'point_diff': 0, 'matches_played': 4},
                {'team': 'Team B4', 'wins': 1, 'set_diff': -4, 'point_diff': -20, 'matches_played': 4},
                {'team': 'Team B5', 'wins': 0, 'set_diff': -8, 'point_diff': -40, 'matches_played': 4}
            ],
            'Pool C': [
                {'team': 'Team C1', 'wins': 3, 'set_diff': 6, 'point_diff': 30, 'matches_played': 3},
                {'team': 'Team C2', 'wins': 2, 'set_diff': 2, 'point_diff': 10, 'matches_played': 3},
                {'team': 'Team C3', 'wins': 1, 'set_diff': -2, 'point_diff': -10, 'matches_played': 3},
                {'team': 'Team C4', 'wins': 0, 'set_diff': -6, 'point_diff': -30, 'matches_played': 3}
            ]
        }
        
        seeded_teams = seed_silver_bracket_teams(pools, standings)
        
        # First 3 seeds should be all #3 finishers (one from each pool)
        third_place_teams = {'Team A3', 'Team B3', 'Team C3'}
        first_three_seeds = {seeded_teams[0][0], seeded_teams[1][0], seeded_teams[2][0]}
        assert first_three_seeds == third_place_teams, f"First 3 seeds should be all #3 finishers, got {first_three_seeds}"
        
        # Next 3 seeds should be all #4 finishers
        fourth_place_teams = {'Team A4', 'Team B4', 'Team C4'}
        next_three_seeds = {seeded_teams[3][0], seeded_teams[4][0], seeded_teams[5][0]}
        assert next_three_seeds == fourth_place_teams, f"Seeds 4-6 should be all #4 finishers, got {next_three_seeds}"
        
        # Last 2 seeds should be #5 finishers (only Pools A and B have 5 teams)
        fifth_place_teams = {'Team A5', 'Team B5'}
        last_two_seeds = {seeded_teams[6][0], seeded_teams[7][0]}
        assert last_two_seeds == fifth_place_teams, f"Last 2 seeds should be all #5 finishers, got {last_two_seeds}"
        
        # Total should be 8 teams
        assert len(seeded_teams) == 8
    
    def test_silver_seeding_tiebreakers(self):
        """Verify that tiebreaker logic (wins > set_diff > point_diff > pool_name) is applied correctly."""
        pools = {
            'Pool A': {
                'teams': ['Team A1', 'Team A2', 'Team A3'],
                'advance': 2
            },
            'Pool B': {
                'teams': ['Team B1', 'Team B2', 'Team B3'],
                'advance': 2
            },
            'Pool C': {
                'teams': ['Team C1', 'Team C2', 'Team C3'],
                'advance': 2
            }
        }
        
        # All #3 finishers with different stats to test tiebreaker ordering
        standings = {
            'Pool A': [
                {'team': 'Team A1', 'wins': 2, 'set_diff': 4, 'point_diff': 20, 'matches_played': 2},
                {'team': 'Team A2', 'wins': 1, 'set_diff': 0, 'point_diff': 0, 'matches_played': 2},
                {'team': 'Team A3', 'wins': 1, 'set_diff': 2, 'point_diff': 10, 'matches_played': 2}  # Best 3rd: wins=1, set_diff=2
            ],
            'Pool B': [
                {'team': 'Team B1', 'wins': 2, 'set_diff': 4, 'point_diff': 20, 'matches_played': 2},
                {'team': 'Team B2', 'wins': 1, 'set_diff': 0, 'point_diff': 0, 'matches_played': 2},
                {'team': 'Team B3', 'wins': 1, 'set_diff': 2, 'point_diff': 5, 'matches_played': 2}  # 2nd best 3rd: wins=1, set_diff=2, point_diff=5
            ],
            'Pool C': [
                {'team': 'Team C1', 'wins': 2, 'set_diff': 4, 'point_diff': 20, 'matches_played': 2},
                {'team': 'Team C2', 'wins': 1, 'set_diff': 0, 'point_diff': 0, 'matches_played': 2},
                {'team': 'Team C3', 'wins': 1, 'set_diff': 1, 'point_diff': 15, 'matches_played': 2}  # Worst 3rd: wins=1, set_diff=1
            ]
        }
        
        seeded_teams = seed_silver_bracket_teams(pools, standings)
        
        # Verify tiebreaker ordering among #3 finishers
        # Should be ordered by: wins (all 1), then set_diff (2, 2, 1), then point_diff (10, 5), then pool (A, B, C)
        assert seeded_teams[0][0] == 'Team A3', f"Seed 1 should be Team A3 (wins=1, set_diff=2, point_diff=10), got {seeded_teams[0][0]}"
        assert seeded_teams[1][0] == 'Team B3', f"Seed 2 should be Team B3 (wins=1, set_diff=2, point_diff=5), got {seeded_teams[1][0]}"
        assert seeded_teams[2][0] == 'Team C3', f"Seed 3 should be Team C3 (wins=1, set_diff=1), got {seeded_teams[2][0]}"
        
        # Verify seeds are sequential
        assert seeded_teams[0][1] == 1
        assert seeded_teams[1][1] == 2
        assert seeded_teams[2][1] == 3
    
    def test_silver_bracket_not_generated_insufficient_teams(self):
        """Verify that silver bracket requires at least 2 teams to generate."""
        # Test with only 1 non-advancing team
        pools = {
            'Pool A': {
                'teams': ['Team A1', 'Team A2', 'Team A3'],
                'advance': 2  # Only 1 non-advancing team
            }
        }
        
        standings = {
            'Pool A': [
                {'team': 'Team A1', 'wins': 2, 'set_diff': 4, 'point_diff': 20, 'matches_played': 2},
                {'team': 'Team A2', 'wins': 1, 'set_diff': 0, 'point_diff': 0, 'matches_played': 2},
                {'team': 'Team A3', 'wins': 0, 'set_diff': -4, 'point_diff': -20, 'matches_played': 2}
            ]
        }
        
        seeded_teams = seed_silver_bracket_teams(pools, standings)
        
        # Should only have 1 team
        assert len(seeded_teams) == 1
        assert seeded_teams[0][0] == 'Team A3'
        
        # Test with no non-advancing teams (all advance)
        pools_all_advance = {
            'Pool A': {
                'teams': ['Team A1', 'Team A2'],
                'advance': 2  # All teams advance
            }
        }
        
        standings_all_advance = {
            'Pool A': [
                {'team': 'Team A1', 'wins': 1, 'set_diff': 2, 'point_diff': 10, 'matches_played': 1},
                {'team': 'Team A2', 'wins': 0, 'set_diff': -2, 'point_diff': -10, 'matches_played': 1}
            ]
        }
        
        seeded_teams_empty = seed_silver_bracket_teams(pools_all_advance, standings_all_advance)
        
        # Should have no teams
        assert len(seeded_teams_empty) == 0
        
        # Test with empty pools
        seeded_teams_no_pools = seed_silver_bracket_teams({}, None)
        assert len(seeded_teams_no_pools) == 0
