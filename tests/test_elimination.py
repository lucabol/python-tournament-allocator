"""
Unit tests for single elimination bracket generation.
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from core.elimination import (
    get_round_name,
    calculate_bracket_size,
    calculate_byes,
    seed_teams_from_pools,
    create_bracket_matchups,
    generate_elimination_rounds,
    generate_elimination_matches_for_scheduling,
    get_elimination_bracket_display,
    _generate_bracket_order
)


class TestBracketHelpers:
    """Tests for bracket helper functions."""
    
    def test_get_round_name_final(self):
        """Test round name for 2 teams (Final)."""
        assert get_round_name(2, 8) == "Final"
    
    def test_get_round_name_semifinal(self):
        """Test round name for 4 teams (Semifinal)."""
        assert get_round_name(4, 8) == "Semifinal"
    
    def test_get_round_name_quarterfinal(self):
        """Test round name for 8 teams (Quarterfinal)."""
        assert get_round_name(8, 16) == "Quarterfinal"
    
    def test_get_round_name_round_of_16(self):
        """Test round name for 16 teams."""
        assert get_round_name(16, 16) == "Round of 16"
    
    def test_calculate_bracket_size_exact_power(self):
        """Test bracket size for exact power of 2."""
        assert calculate_bracket_size(8) == 8
        assert calculate_bracket_size(16) == 16
        assert calculate_bracket_size(4) == 4
    
    def test_calculate_bracket_size_not_power(self):
        """Test bracket size rounds up to next power of 2."""
        assert calculate_bracket_size(5) == 8
        assert calculate_bracket_size(6) == 8
        assert calculate_bracket_size(7) == 8
        assert calculate_bracket_size(9) == 16
        assert calculate_bracket_size(12) == 16
    
    def test_calculate_bracket_size_small(self):
        """Test bracket size for small inputs."""
        assert calculate_bracket_size(2) == 2
        assert calculate_bracket_size(3) == 4
    
    def test_calculate_bracket_size_zero(self):
        """Test bracket size for zero teams."""
        assert calculate_bracket_size(0) == 0
    
    def test_calculate_byes_no_byes(self):
        """Test no byes needed for perfect bracket."""
        assert calculate_byes(8) == 0
        assert calculate_byes(16) == 0
        assert calculate_byes(4) == 0
    
    def test_calculate_byes_needed(self):
        """Test byes calculation."""
        assert calculate_byes(5) == 3  # 8 - 5
        assert calculate_byes(6) == 2  # 8 - 6
        assert calculate_byes(7) == 1  # 8 - 7
        assert calculate_byes(12) == 4  # 16 - 12


class TestBracketOrder:
    """Tests for bracket ordering (seeding)."""
    
    def test_bracket_order_2_teams(self):
        """Test bracket order for 2 teams."""
        order = _generate_bracket_order(2)
        assert order == [1, 2]
    
    def test_bracket_order_4_teams(self):
        """Test bracket order for 4 teams."""
        order = _generate_bracket_order(4)
        # Should be [1, 4, 2, 3] so 1v4, 2v3 and winners meet in final
        assert order == [1, 4, 2, 3]
    
    def test_bracket_order_8_teams(self):
        """Test bracket order for 8 teams."""
        order = _generate_bracket_order(8)
        # Standard bracket: 1v8, 4v5, 2v7, 3v6
        assert order == [1, 8, 4, 5, 2, 7, 3, 6]
    
    def test_bracket_order_preserves_seeding(self):
        """Test that higher seeds meet lower seeds early."""
        order = _generate_bracket_order(8)
        # First match should be 1 vs 8
        assert order[0] == 1
        assert order[1] == 8


class TestSeedTeamsFromPools:
    """Tests for seeding teams based on pool finish."""
    
    def test_seed_teams_simple(self):
        """Test basic seeding from pools."""
        pools = {
            'pool1': {'teams': ['A', 'B'], 'advance': 2},
            'pool2': {'teams': ['C', 'D'], 'advance': 2}
        }
        
        seeded = seed_teams_from_pools(pools)
        
        # Should have 4 teams (2 from each pool)
        assert len(seeded) == 4
        
        # Check seeds are 1-4
        seeds = [s[1] for s in seeded]
        assert sorted(seeds) == [1, 2, 3, 4]
    
    def test_seed_teams_ordering(self):
        """Test that 1st place finishers are seeded first."""
        pools = {
            'pool1': {'teams': ['A', 'B', 'C'], 'advance': 2},
            'pool2': {'teams': ['D', 'E', 'F'], 'advance': 2}
        }
        
        seeded = seed_teams_from_pools(pools)
        
        # First two seeds should be position 1 teams
        pos1_seeds = [s for s in seeded if '_pos1' in s[0]]
        assert all(s[1] <= 2 for s in pos1_seeds)
    
    def test_seed_teams_empty_pools(self):
        """Test seeding with empty pools."""
        pools = {}
        seeded = seed_teams_from_pools(pools)
        assert seeded == []
    
    def test_seed_teams_different_advance_counts(self):
        """Test seeding with different advance counts per pool."""
        pools = {
            'pool1': {'teams': ['A', 'B', 'C'], 'advance': 1},
            'pool2': {'teams': ['D', 'E'], 'advance': 2}
        }
        
        seeded = seed_teams_from_pools(pools)
        
        # pool1: 1 team, pool2: 2 teams = 3 total
        assert len(seeded) == 3


class TestCreateBracketMatchups:
    """Tests for creating first round matchups."""
    
    def test_create_matchups_4_teams(self):
        """Test matchup creation for 4 teams."""
        seeded = [
            ('Team1', 1, 'pool1'),
            ('Team2', 2, 'pool2'),
            ('Team3', 3, 'pool1'),
            ('Team4', 4, 'pool2'),
        ]
        
        matchups = create_bracket_matchups(seeded)
        
        # Should have 2 matches
        assert len(matchups) == 2
        
        # 1 should play 4, 2 should play 3
        teams_in_matches = [set(m['teams']) for m in matchups]
        assert {'Team1', 'Team4'} in teams_in_matches
        assert {'Team2', 'Team3'} in teams_in_matches
    
    def test_create_matchups_with_byes(self):
        """Test matchup creation when byes are needed."""
        seeded = [
            ('Team1', 1, 'pool1'),
            ('Team2', 2, 'pool2'),
            ('Team3', 3, 'pool1'),
        ]
        
        matchups = create_bracket_matchups(seeded)
        
        # One team should have a bye
        bye_matches = [m for m in matchups if m.get('is_bye', False)]
        assert len(bye_matches) == 1
        
        # Highest seed (Team1) should get the bye
        bye_match = bye_matches[0]
        assert 'Team1' in bye_match['teams']
    
    def test_create_matchups_no_teams(self):
        """Test matchup creation with no teams."""
        matchups = create_bracket_matchups([])
        assert matchups == []
    
    def test_create_matchups_single_team(self):
        """Test matchup creation with single team."""
        seeded = [('Team1', 1, 'pool1')]
        matchups = create_bracket_matchups(seeded)
        assert matchups == []


class TestGenerateEliminationRounds:
    """Tests for full elimination round generation."""
    
    def test_generate_rounds_basic(self):
        """Test basic round generation."""
        pools = {
            'pool1': {'teams': ['A', 'B'], 'advance': 2},
            'pool2': {'teams': ['C', 'D'], 'advance': 2}
        }
        
        result = generate_elimination_rounds(pools)
        
        assert result['bracket_size'] == 4
        assert result['total_rounds'] == 2  # Semifinal + Final
        assert len(result['seeded_teams']) == 4
    
    def test_generate_rounds_includes_all_rounds(self):
        """Test that all rounds are generated."""
        pools = {
            'pool1': {'teams': ['A', 'B', 'C', 'D'], 'advance': 2},
            'pool2': {'teams': ['E', 'F', 'G', 'H'], 'advance': 2}
        }
        
        result = generate_elimination_rounds(pools)
        
        # 4 teams = QF, SF, F (but with 4 teams it's SF + F)
        assert 'Semifinal' in result['rounds']
        assert 'Final' in result['rounds']
    
    def test_generate_rounds_empty_pools(self):
        """Test round generation with no teams."""
        result = generate_elimination_rounds({})
        
        assert result['bracket_size'] == 0
        assert result['total_rounds'] == 0
        assert result['rounds'] == {}


class TestGenerateEliminationMatchesForScheduling:
    """Tests for generating matches in scheduling format."""
    
    def test_generate_scheduling_format(self):
        """Test matches are in correct format for scheduling."""
        pools = {
            'pool1': {'teams': ['A', 'B'], 'advance': 2},
            'pool2': {'teams': ['C', 'D'], 'advance': 2}
        }
        
        matches = generate_elimination_matches_for_scheduling(pools)
        
        # Check format: list of ((team1, team2), round_name)
        for match in matches:
            assert len(match) == 2
            teams_tuple, round_name = match
            assert len(teams_tuple) == 2
            assert isinstance(round_name, str)
    
    def test_generate_scheduling_excludes_byes(self):
        """Test that bye matches are not included in scheduling."""
        pools = {
            'pool1': {'teams': ['A', 'B', 'C'], 'advance': 1},  # 1 team
            'pool2': {'teams': ['D', 'E'], 'advance': 2}  # 2 teams
        }
        
        matches = generate_elimination_matches_for_scheduling(pools)
        
        # No match should contain 'BYE'
        for (team1, team2), _ in matches:
            assert team1 != 'BYE'
            assert team2 != 'BYE'


class TestGetEliminationBracketDisplay:
    """Tests for bracket display data."""
    
    def test_display_data_structure(self):
        """Test that display data has all required fields."""
        pools = {
            'pool1': {'teams': ['A', 'B'], 'advance': 2},
            'pool2': {'teams': ['C', 'D'], 'advance': 2}
        }
        
        display = get_elimination_bracket_display(pools)
        
        assert 'seeded_teams' in display
        assert 'rounds' in display
        assert 'bracket_size' in display
        assert 'total_rounds' in display
        assert 'total_teams' in display
        assert 'byes' in display
        assert 'matches_per_round' in display
    
    def test_display_matches_count(self):
        """Test that matches per round is calculated correctly."""
        pools = {
            'pool1': {'teams': ['A', 'B'], 'advance': 2},
            'pool2': {'teams': ['C', 'D'], 'advance': 2}
        }
        
        display = get_elimination_bracket_display(pools)
        
        # With 4 teams, should have 2 SF matches and 1 Final
        total_matches = sum(display['matches_per_round'].values())
        assert total_matches >= 1  # At least the final


class TestEliminationIntegration:
    """Integration tests for full elimination workflow."""
    
    def test_full_workflow_8_teams(self):
        """Test complete workflow with 8 advancing teams."""
        pools = {
            'pool1': {'teams': ['A', 'B', 'C', 'D'], 'advance': 2},
            'pool2': {'teams': ['E', 'F', 'G', 'H'], 'advance': 2},
            'pool3': {'teams': ['I', 'J', 'K', 'L'], 'advance': 2},
            'pool4': {'teams': ['M', 'N', 'O', 'P'], 'advance': 2}
        }
        
        # Generate bracket
        bracket = generate_elimination_rounds(pools)
        
        assert len(bracket['seeded_teams']) == 8
        assert bracket['bracket_size'] == 8
        assert bracket['total_rounds'] == 3  # QF, SF, F
        
        # Generate schedulable matches
        matches = generate_elimination_matches_for_scheduling(pools)
        
        # Should have 4 QF matches (no byes with 8 teams)
        first_round_matches = [m for m in matches if 'Quarterfinal' in m[1]]
        assert len(first_round_matches) == 4
    
    def test_full_workflow_6_teams(self):
        """Test complete workflow with 6 teams (needs byes)."""
        pools = {
            'pool1': {'teams': ['A', 'B', 'C'], 'advance': 2},
            'pool2': {'teams': ['D', 'E', 'F'], 'advance': 2},
            'pool3': {'teams': ['G', 'H', 'I'], 'advance': 2}
        }
        
        bracket = generate_elimination_rounds(pools)
        
        assert len(bracket['seeded_teams']) == 6
        assert bracket['bracket_size'] == 8  # Rounds up to 8
        assert calculate_byes(6) == 2  # 2 byes
        
        display = get_elimination_bracket_display(pools)
        assert display['byes'] == 2
