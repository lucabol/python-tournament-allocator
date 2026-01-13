"""
Tests for double elimination bracket functionality.
"""
import pytest
from src.core.double_elimination import (
    get_losers_round_name,
    get_winners_round_name,
    calculate_losers_bracket_rounds,
    generate_double_elimination_bracket,
    generate_double_elimination_matches_for_scheduling,
    get_double_elimination_bracket_display,
    _generate_winners_bracket,
    _generate_losers_bracket
)


class TestLosersRoundName:
    """Tests for get_losers_round_name."""
    
    def test_losers_final(self):
        """Last round (round_num == total - 1) is Losers Final."""
        # For 5 rounds, round 4 (0-indexed) is the final
        assert get_losers_round_name(4, 5) == "Losers Final"
        # For 3 rounds, round 2 is the final
        assert get_losers_round_name(2, 3) == "Losers Final"
    
    def test_losers_semifinal(self):
        """Second to last is Losers Semifinal."""
        # For 5 rounds, round 3 is semifinal
        assert get_losers_round_name(3, 5) == "Losers Semifinal"
        # For 3 rounds, round 1 is semifinal
        assert get_losers_round_name(1, 3) == "Losers Semifinal"
    
    def test_losers_numbered_round(self):
        """Earlier rounds are numbered."""
        assert get_losers_round_name(0, 5) == "Losers Round 1"
        assert get_losers_round_name(1, 5) == "Losers Round 2"
        assert get_losers_round_name(2, 5) == "Losers Round 3"


class TestWinnersRoundName:
    """Tests for get_winners_round_name."""
    
    def test_winners_final(self):
        """Two teams means Winners Final."""
        assert get_winners_round_name(2, 16) == "Winners Final"
        assert get_winners_round_name(2, 8) == "Winners Final"
    
    def test_winners_semifinal(self):
        """Four teams means Winners Semifinal."""
        assert get_winners_round_name(4, 16) == "Winners Semifinal"
        assert get_winners_round_name(4, 8) == "Winners Semifinal"
    
    def test_winners_quarterfinal(self):
        """Eight teams means Winners Quarterfinal."""
        assert get_winners_round_name(8, 16) == "Winners Quarterfinal"
    
    def test_winners_round_of_n(self):
        """Larger counts are Round of N."""
        assert get_winners_round_name(16, 16) == "Winners Round of 16"
        assert get_winners_round_name(32, 32) == "Winners Round of 32"


class TestCalculateLosersRounds:
    """Tests for calculate_losers_bracket_rounds."""
    
    def test_no_teams(self):
        """Less than 2 teams means 0 losers rounds."""
        assert calculate_losers_bracket_rounds(1) == 0
        assert calculate_losers_bracket_rounds(0) == 0
    
    def test_four_teams(self):
        """4 team bracket: 2 winners rounds, so 3 losers rounds."""
        # Winners: Round of 4 -> Final (2 rounds)
        # Losers: 2 * 2 - 1 = 3 rounds
        assert calculate_losers_bracket_rounds(4) == 3
    
    def test_eight_teams(self):
        """8 team bracket: 3 winners rounds, so 5 losers rounds."""
        assert calculate_losers_bracket_rounds(8) == 5
    
    def test_sixteen_teams(self):
        """16 team bracket: 4 winners rounds, so 7 losers rounds."""
        assert calculate_losers_bracket_rounds(16) == 7
    
    def test_two_teams(self):
        """2 team bracket: 1 winners round, so 1 losers round."""
        assert calculate_losers_bracket_rounds(2) == 1


class TestGenerateDoubleEliminationBracket:
    """Tests for generate_double_elimination_bracket."""
    
    def test_empty_pools(self):
        """Empty pools returns empty bracket structure."""
        result = generate_double_elimination_bracket({})
        assert result['seeded_teams'] == []
        assert result['winners_bracket'] == {}
        assert result['losers_bracket'] == {}
        assert result['grand_final'] is None
        assert result['bracket_size'] == 0
    
    def test_single_team(self):
        """Single team returns minimal bracket."""
        pools = {'A': {'teams': ['Team1'], 'advance': 1}}
        result = generate_double_elimination_bracket(pools)
        assert len(result['seeded_teams']) == 1
        assert result['bracket_size'] == 0
    
    def test_two_teams(self):
        """Two teams creates minimal bracket."""
        pools = {'A': {'teams': ['Team1', 'Team2'], 'advance': 2}}
        result = generate_double_elimination_bracket(pools)
        assert result['bracket_size'] == 2
        assert result['total_winners_rounds'] == 1
        assert result['total_losers_rounds'] == 1
    
    def test_four_teams(self):
        """Four teams creates proper bracket."""
        pools = {
            'A': {'teams': ['A1', 'A2'], 'advance': 2},
            'B': {'teams': ['B1', 'B2'], 'advance': 2}
        }
        result = generate_double_elimination_bracket(pools)
        
        assert result['bracket_size'] == 4
        assert result['total_winners_rounds'] == 2
        assert result['total_losers_rounds'] == 3
        assert len(result['seeded_teams']) == 4
    
    def test_grand_final_present(self):
        """Grand final is always present for valid brackets."""
        pools = {'A': {'teams': ['Team1', 'Team2'], 'advance': 2}}
        result = generate_double_elimination_bracket(pools)
        
        assert result['grand_final'] is not None
        assert 'Winners Bracket Champion' in result['grand_final']['teams']
        assert 'Losers Bracket Champion' in result['grand_final']['teams']
    
    def test_bracket_reset_present(self):
        """Bracket reset is always present for valid brackets."""
        pools = {'A': {'teams': ['Team1', 'Team2'], 'advance': 2}}
        result = generate_double_elimination_bracket(pools)
        
        assert result['bracket_reset'] is not None
        assert result['bracket_reset']['is_conditional'] is True
    
    def test_seeding_order(self):
        """Teams are seeded in correct order."""
        pools = {
            'A': {'teams': ['A1', 'A2', 'A3', 'A4'], 'advance': 2},
            'B': {'teams': ['B1', 'B2', 'B3', 'B4'], 'advance': 2}
        }
        result = generate_double_elimination_bracket(pools)
        
        # First seeds from each pool first
        seeds = [seed for _, seed, _ in result['seeded_teams']]
        assert seeds == [1, 2, 3, 4]


class TestGenerateWinnersBracket:
    """Tests for _generate_winners_bracket."""
    
    def test_four_teams_winners_bracket(self):
        """4 team winners bracket structure."""
        seeded = [('A', 1, 'P1'), ('B', 2, 'P2'), ('C', 3, 'P1'), ('D', 4, 'P2')]
        result = _generate_winners_bracket(seeded, 4, 2)
        
        assert len(result) == 2  # 2 rounds
        # First round should have actual matchups
        first_round_name = get_winners_round_name(4, 4)
        assert first_round_name in result
        assert len(result[first_round_name]) == 2  # 2 matches
    
    def test_bye_handling(self):
        """Byes are correctly marked."""
        seeded = [('A', 1, 'P1'), ('B', 2, 'P2'), ('C', 3, 'P1')]
        result = _generate_winners_bracket(seeded, 4, 2)
        
        first_round = list(result.values())[0]
        bye_matches = [m for m in first_round if m.get('is_bye')]
        assert len(bye_matches) == 1


class TestGenerateLosersRracket:
    """Tests for _generate_losers_bracket."""
    
    def test_four_team_losers_bracket(self):
        """4 team losers bracket has 3 rounds."""
        result = _generate_losers_bracket(4, 2, 3)
        assert len(result) == 3
    
    def test_losers_bracket_has_notes(self):
        """Losers bracket rounds have explanatory notes."""
        result = _generate_losers_bracket(4, 2, 3)
        
        # All matches should have notes
        for round_matches in result.values():
            for match in round_matches:
                assert 'note' in match


class TestGenerateMatchesForScheduling:
    """Tests for generate_double_elimination_matches_for_scheduling."""
    
    def test_empty_pools(self):
        """Empty pools returns empty list."""
        result = generate_double_elimination_matches_for_scheduling({})
        assert result == []
    
    def test_only_first_round_winners(self):
        """Only first round winners bracket matches are returned."""
        pools = {
            'A': {'teams': ['A1', 'A2'], 'advance': 2},
            'B': {'teams': ['B1', 'B2'], 'advance': 2}
        }
        result = generate_double_elimination_matches_for_scheduling(pools)
        
        # Should only have first round winners bracket matches
        for match, round_name in result:
            assert 'Winners' in round_name
    
    def test_excludes_byes(self):
        """Bye matches are not included."""
        pools = {
            'A': {'teams': ['A1', 'A2', 'A3'], 'advance': 3}
        }
        result = generate_double_elimination_matches_for_scheduling(pools)
        
        # No match should have BYE
        for (team1, team2), _ in result:
            assert 'BYE' not in team1
            assert 'BYE' not in team2
    
    def test_match_format(self):
        """Matches are in correct format."""
        pools = {'A': {'teams': ['T1', 'T2'], 'advance': 2}}
        result = generate_double_elimination_matches_for_scheduling(pools)
        
        for match_tuple, round_name in result:
            assert isinstance(match_tuple, tuple)
            assert len(match_tuple) == 2
            assert isinstance(round_name, str)


class TestGetDisplayData:
    """Tests for get_double_elimination_bracket_display."""
    
    def test_empty_pools(self):
        """Empty pools returns empty display data."""
        result = get_double_elimination_bracket_display({})
        assert result['total_teams'] == 0
        assert result['seeded_teams'] == []
    
    def test_all_fields_present(self):
        """All expected fields are in display data."""
        pools = {'A': {'teams': ['T1', 'T2'], 'advance': 2}}
        result = get_double_elimination_bracket_display(pools)
        
        expected_fields = [
            'seeded_teams', 'winners_bracket', 'losers_bracket',
            'grand_final', 'bracket_reset', 'bracket_size',
            'total_winners_rounds', 'total_losers_rounds',
            'total_teams', 'byes', 'total_matches'
        ]
        for field in expected_fields:
            assert field in result
    
    def test_total_teams_correct(self):
        """Total teams matches advancing teams."""
        pools = {
            'A': {'teams': ['A1', 'A2', 'A3'], 'advance': 2},
            'B': {'teams': ['B1', 'B2', 'B3'], 'advance': 3}
        }
        result = get_double_elimination_bracket_display(pools)
        assert result['total_teams'] == 5  # 2 + 3
    
    def test_total_matches_calculation(self):
        """Total matches calculation is correct."""
        pools = {'A': {'teams': ['T1', 'T2', 'T3', 'T4'], 'advance': 4}}
        result = get_double_elimination_bracket_display(pools)
        
        # For 4 team double elimination:
        # Winners: 3 matches
        # Losers: 3 matches
        # Grand Final: 1
        # Total: 7 (bracket reset not counted as it's conditional)
        assert result['total_matches'] == 7


class TestDoubleEliminationIntegration:
    """Integration tests for double elimination."""
    
    def test_full_tournament_flow(self):
        """Test complete bracket generation for realistic tournament."""
        pools = {
            'Pool A': {'teams': ['Beach Bums', 'Sand Stars', 'Wave Riders', 'Sun Devils'], 'advance': 2},
            'Pool B': {'teams': ['Net Ninjas', 'Spike Squad', 'Bump Brigade', 'Set Stars'], 'advance': 2},
            'Pool C': {'teams': ['Dig Kings', 'Block Party', 'Serve Aces', 'Rally Pros'], 'advance': 2}
        }
        result = generate_double_elimination_bracket(pools)
        
        # 6 teams advancing
        assert len(result['seeded_teams']) == 6
        
        # Bracket should be rounded up to 8
        assert result['bracket_size'] == 8
        
        # Winners: 3 rounds (8->4->2)
        assert result['total_winners_rounds'] == 3
        
        # Losers: 5 rounds
        assert result['total_losers_rounds'] == 5
        
        # Grand final and reset present
        assert result['grand_final'] is not None
        assert result['bracket_reset'] is not None
    
    def test_byes_assigned_to_top_seeds(self):
        """Byes should be assigned to top seeded teams."""
        pools = {
            'A': {'teams': ['A1', 'A2', 'A3'], 'advance': 3}
        }
        result = generate_double_elimination_bracket(pools)
        
        # 3 teams -> 4 bracket size -> 1 bye
        assert result['bracket_size'] == 4
        
        # Find bye matches
        first_round = list(result['winners_bracket'].values())[0]
        bye_matches = [m for m in first_round if m.get('is_bye')]
        
        assert len(bye_matches) == 1
        # Seed 1 should get the bye (playing against seed 4 which is missing)
    
    def test_scheduling_matches(self):
        """Scheduling returns appropriate matches."""
        pools = {
            'A': {'teams': ['T1', 'T2', 'T3', 'T4'], 'advance': 4}
        }
        matches = generate_double_elimination_matches_for_scheduling(pools)
        
        # First round of 4-team winners bracket has 2 matches
        assert len(matches) == 2
        
        # Check teams are correct placeholders
        all_teams = []
        for (t1, t2), _ in matches:
            all_teams.extend([t1, t2])
        
        # Should have the 4 advancing teams
        assert len(all_teams) == 4


class TestEdgeCases:
    """Test edge cases for double elimination."""
    
    def test_single_pool_all_advance(self):
        """Single pool with all teams advancing."""
        pools = {'A': {'teams': ['T1', 'T2', 'T3', 'T4'], 'advance': 4}}
        result = generate_double_elimination_bracket(pools)
        
        assert len(result['seeded_teams']) == 4
        assert result['bracket_size'] == 4
    
    def test_many_pools_few_advance(self):
        """Many pools with few teams advancing from each."""
        pools = {f'Pool{i}': {'teams': [f'P{i}T{j}' for j in range(4)], 'advance': 1}
                 for i in range(8)}
        result = generate_double_elimination_bracket(pools)
        
        # 8 teams advancing, one from each pool
        assert len(result['seeded_teams']) == 8
        assert result['bracket_size'] == 8
    
    def test_large_bracket(self):
        """Test larger bracket size."""
        pools = {
            f'Pool{i}': {'teams': [f'P{i}T{j}' for j in range(4)], 'advance': 2}
            for i in range(8)
        }
        result = generate_double_elimination_bracket(pools)
        
        # 16 teams advancing
        assert len(result['seeded_teams']) == 16
        assert result['bracket_size'] == 16
        assert result['total_winners_rounds'] == 4
        assert result['total_losers_rounds'] == 7
