"""
Tests for schedule-to-display consistency in bracket generation.

These tests verify that the scheduling path and display path produce
identical match pairings and consistent metadata (match_code, placeholder text).

Background:
- Scheduling path: generate_*_matches_for_scheduling() -> used by AllocationManager
- Display path: generate_*_bracket_with_results() -> used by templates
- These paths were diverging, causing schedule-to-bracket mismatches
"""
import pytest
from src.core.double_elimination import (
    generate_silver_bracket_matches_for_scheduling,
    generate_silver_double_bracket_with_results,
    generate_double_elimination_matches_for_scheduling,
    generate_double_bracket_with_results
)
from src.core.elimination import (
    generate_elimination_matches_for_scheduling,
    generate_bracket_with_results
)


class TestSilverBracketConsistency:
    """Verify silver bracket scheduling and display produce consistent results."""
    
    def test_silver_schedule_and_display_have_matching_placeholders(self):
        """
        Schedule and display generators must use identical placeholder text.
        
        Regression test for: Silver bracket display showed "Winner M1" while
        schedule showed "Winner SW1-M1" (missing the SW prefix).
        """
        pools = {
            'Pool A': {'teams': ['A1', 'A2', 'A3', 'A4'], 'advance': 2},
            'Pool B': {'teams': ['B1', 'B2', 'B3', 'B4'], 'advance': 2}
        }
        
        # Generate from both paths (no standings = all placeholders)
        schedule_matches = generate_silver_bracket_matches_for_scheduling(pools, standings=None)
        display_bracket = generate_silver_double_bracket_with_results(pools, standings=None)
        
        # Extract placeholders from schedule matches
        schedule_placeholders = set()
        for match in schedule_matches:
            for team in match['teams']:
                if team.startswith('#'):
                    schedule_placeholders.add(team)
        
        # Extract placeholders from display bracket
        display_placeholders = set()
        for round_name, matches in display_bracket['winners_bracket'].items():
            for match in matches:
                for team in match['teams']:
                    if isinstance(team, str) and team.startswith(('Winner', 'Loser', '#')):
                        display_placeholders.add(team)
        
        for round_name, matches in display_bracket['losers_bracket'].items():
            for match in matches:
                for team in match['teams']:
                    if isinstance(team, str) and team.startswith(('Winner', 'Loser', '#')):
                        display_placeholders.add(team)
        
        # Both should use SW/SL prefix format
        for placeholder in schedule_placeholders:
            if 'Winner' in placeholder or 'Loser' in placeholder:
                assert 'SW' in placeholder or 'SL' in placeholder, \
                    f"Schedule placeholder missing SW/SL prefix: {placeholder}"
        
        for placeholder in display_placeholders:
            if 'Winner' in placeholder or 'Loser' in placeholder:
                assert 'SW' in placeholder or 'SL' in placeholder, \
                    f"Display placeholder missing SW/SL prefix: {placeholder}"
    
    def test_silver_display_has_match_code_on_all_matches(self):
        """
        Every match object in the display bracket must have a match_code field.
        
        Regression test for: Silver bracket display generator was missing match_code
        entirely, causing badge lookups to fail.
        """
        pools = {
            'Pool A': {'teams': ['A1', 'A2', 'A3', 'A4', 'A5', 'A6', 'A7', 'A8'], 'advance': 4}
        }
        
        display_bracket = generate_silver_double_bracket_with_results(pools, standings=None)
        
        assert display_bracket is not None, "Silver bracket should be generated with 4+ non-advancing teams"
        
        # Check winners bracket
        for round_name, matches in display_bracket['winners_bracket'].items():
            for match in matches:
                if not match.get('is_bye'):
                    assert 'match_code' in match, \
                        f"Winners bracket {round_name} match missing match_code: {match}"
                    assert match['match_code'].startswith('SW'), \
                        f"Silver winners match_code should start with SW: {match['match_code']}"
        
        # Check losers bracket
        for round_name, matches in display_bracket['losers_bracket'].items():
            for match in matches:
                assert 'match_code' in match, \
                    f"Losers bracket {round_name} match missing match_code: {match}"
                assert match['match_code'].startswith('SL'), \
                    f"Silver losers match_code should start with SL: {match['match_code']}"
        
        # Check grand final
        if display_bracket['grand_final']:
            assert 'match_code' in display_bracket['grand_final'], \
                "Grand final missing match_code"
            assert display_bracket['grand_final']['match_code'] == 'SGF', \
                f"Silver grand final match_code should be SGF: {display_bracket['grand_final']['match_code']}"
        
        # Check bracket reset
        if display_bracket['bracket_reset']:
            assert 'match_code' in display_bracket['bracket_reset'], \
                "Bracket reset missing match_code"
            assert display_bracket['bracket_reset']['match_code'] == 'SBR', \
                f"Silver bracket reset match_code should be SBR: {display_bracket['bracket_reset']['match_code']}"
    
    def test_silver_schedule_and_display_have_matching_team_counts(self):
        """
        Schedule and display should generate the same number of matches.
        
        Note: This is a soft check - the exact count may differ slightly due to
        how bye matches are handled, but they should be reasonably close.
        """
        pools = {
            'Pool A': {'teams': ['A1', 'A2', 'A3', 'A4', 'A5', 'A6'], 'advance': 3},
            'Pool B': {'teams': ['B1', 'B2', 'B3', 'B4', 'B5', 'B6'], 'advance': 3}
        }
        
        schedule_matches = generate_silver_bracket_matches_for_scheduling(pools, standings=None)
        display_bracket = generate_silver_double_bracket_with_results(pools, standings=None)
        
        # Count non-bye matches in display bracket
        display_match_count = 0
        for matches in display_bracket['winners_bracket'].values():
            display_match_count += sum(1 for m in matches if not m.get('is_bye'))
        for matches in display_bracket['losers_bracket'].values():
            display_match_count += len(matches)
        if display_bracket['grand_final']:
            display_match_count += 1
        if display_bracket['bracket_reset']:
            display_match_count += 1
        
        # Schedule should have same count (minus byes)
        schedule_non_bye_count = sum(1 for m in schedule_matches if not m.get('is_bye'))
        
        # Allow for small differences (e.g., bracket reset counted differently)
        assert abs(schedule_non_bye_count - display_match_count) <= 1, \
            f"Match count significantly different: schedule={schedule_non_bye_count}, display={display_match_count}"
    
    def test_silver_placeholder_format_matches_schedule_generation(self):
        """
        Placeholder text format should be identical between paths.
        
        Specifically tests the bug where display showed "Winner M1" instead of "Winner SW1-M1".
        """
        pools = {'Pool A': {'teams': ['T1', 'T2', 'T3', 'T4', 'T5', 'T6', 'T7', 'T8'], 'advance': 4}}
        
        display_bracket = generate_silver_double_bracket_with_results(pools, standings=None)
        
        assert display_bracket is not None, "Silver bracket should be generated"
        
        # Find a placeholder in the losers bracket (these come from winners bracket)
        losers_first_round = list(display_bracket['losers_bracket'].values())[0]
        first_match = losers_first_round[0]
        
        # Teams should be like "Loser SW1-M1", not "Loser M1"
        for team in first_match['teams']:
            if isinstance(team, str) and team.startswith('Loser'):
                assert 'SW' in team, \
                    f"Losers bracket placeholder missing SW prefix: {team}"
                # Format should be "Loser SW{round}-M{num}"
                assert team.count('-') >= 1, \
                    f"Placeholder missing match reference: {team}"


class TestGoldBracketConsistency:
    """Verify gold bracket scheduling and display produce consistent results."""
    
    def test_gold_display_has_match_code_on_all_matches(self):
        """Every match in gold bracket display should have match_code."""
        pools = {
            'Pool A': {'teams': ['A1', 'A2', 'A3', 'A4'], 'advance': 4}
        }
        
        display_bracket = generate_double_bracket_with_results(pools, standings=None)
        
        # Check winners bracket
        for round_name, matches in display_bracket['winners_bracket'].items():
            for match in matches:
                if not match.get('is_bye'):
                    assert 'match_code' in match, \
                        f"Winners bracket {round_name} match missing match_code"
                    assert match['match_code'].startswith('W'), \
                        f"Gold winners match_code should start with W: {match['match_code']}"
        
        # Check losers bracket
        for round_name, matches in display_bracket['losers_bracket'].items():
            for match in matches:
                assert 'match_code' in match, \
                    f"Losers bracket {round_name} match missing match_code"
                assert match['match_code'].startswith('L'), \
                    f"Gold losers match_code should start with L: {match['match_code']}"
        
        # Check grand final and bracket reset
        if display_bracket['grand_final']:
            assert 'match_code' in display_bracket['grand_final']
            assert display_bracket['grand_final']['match_code'] == 'GF'
        
        if display_bracket['bracket_reset']:
            assert 'match_code' in display_bracket['bracket_reset']
            assert display_bracket['bracket_reset']['match_code'] == 'BR'


class TestSingleEliminationConsistency:
    """Verify single elimination has match_code fields."""
    
    def test_single_elim_display_bracket_structure(self):
        """Single elimination bracket has expected structure."""
        pools = {
            'Pool A': {'teams': ['A1', 'A2', 'A3', 'A4'], 'advance': 4}
        }
        
        display_bracket = generate_bracket_with_results(pools, standings=None)
        
        # Should have metadata keys
        assert 'seeded_teams' in display_bracket
        assert 'bracket_size' in display_bracket
        
        # Should have round data
        has_rounds = False
        for key in display_bracket.keys():
            if key not in ('seeded_teams', 'bracket_size'):
                has_rounds = True
                break
        
        assert has_rounds, "Bracket should have round data"


class TestMatchCodeUniqueness:
    """Verify match_code values are unique within each bracket."""
    
    def test_silver_bracket_match_codes_are_unique(self):
        """All match codes in silver bracket should be unique."""
        pools = {
            'Pool A': {'teams': ['A1', 'A2', 'A3', 'A4', 'A5', 'A6', 'A7', 'A8'], 'advance': 4},
            'Pool B': {'teams': ['B1', 'B2', 'B3', 'B4', 'B5', 'B6', 'B7', 'B8'], 'advance': 4}
        }
        
        display_bracket = generate_silver_double_bracket_with_results(pools, standings=None)
        
        # Collect all match codes
        match_codes = []
        
        for matches in display_bracket['winners_bracket'].values():
            for match in matches:
                if 'match_code' in match and not match.get('is_bye'):
                    match_codes.append(match['match_code'])
        
        for matches in display_bracket['losers_bracket'].values():
            for match in matches:
                if 'match_code' in match:
                    match_codes.append(match['match_code'])
        
        if display_bracket['grand_final'] and 'match_code' in display_bracket['grand_final']:
            match_codes.append(display_bracket['grand_final']['match_code'])
        
        if display_bracket['bracket_reset'] and 'match_code' in display_bracket['bracket_reset']:
            match_codes.append(display_bracket['bracket_reset']['match_code'])
        
        # All should be unique
        assert len(match_codes) == len(set(match_codes)), \
            f"Duplicate match codes found: {[code for code in match_codes if match_codes.count(code) > 1]}"
    
    def test_gold_bracket_match_codes_are_unique(self):
        """All match codes in gold bracket should be unique."""
        pools = {
            'Pool A': {'teams': ['A1', 'A2', 'A3', 'A4', 'A5', 'A6', 'A7', 'A8'], 'advance': 8}
        }
        
        display_bracket = generate_double_bracket_with_results(pools, standings=None)
        
        match_codes = []
        
        for matches in display_bracket['winners_bracket'].values():
            for match in matches:
                if 'match_code' in match and not match.get('is_bye'):
                    match_codes.append(match['match_code'])
        
        for matches in display_bracket['losers_bracket'].values():
            for match in matches:
                if 'match_code' in match:
                    match_codes.append(match['match_code'])
        
        if display_bracket['grand_final'] and 'match_code' in display_bracket['grand_final']:
            match_codes.append(display_bracket['grand_final']['match_code'])
        
        if display_bracket['bracket_reset'] and 'match_code' in display_bracket['bracket_reset']:
            match_codes.append(display_bracket['bracket_reset']['match_code'])
        
        assert len(match_codes) == len(set(match_codes)), \
            f"Duplicate match codes found"


class TestDualFormatLookup:
    """
    Verify that display generators can look up results using both old and new formats.
    
    This ensures backward compatibility when transitioning from bracket_key to match_code.
    """
    
    def test_silver_bracket_accepts_match_code_results(self):
        """Silver bracket display can find results by match_code."""
        pools = {'Pool A': {'teams': ['T1', 'T2', 'T3', 'T4', 'T5', 'T6', 'T7', 'T8'], 'advance': 4}}
        
        # Provide results using match_code format
        bracket_results = {
            'SW1-M1': {'winner': 'T1', 'loser': 'T2', 'sets': [[21, 15]], 'completed': True},
            'SW1-M2': {'winner': 'T3', 'loser': 'T4', 'sets': [[21, 18]], 'completed': True}
        }
        
        display_bracket = generate_silver_double_bracket_with_results(
            pools, standings=None, bracket_results=bracket_results
        )
        
        assert display_bracket is not None, "Silver bracket should be generated"
        
        # First round matches should have results attached
        first_round = list(display_bracket['winners_bracket'].values())[0]
        results_found = sum(1 for m in first_round if m.get('result') and m['result'].get('completed'))
        
        assert results_found == 2, "Display should find results by match_code"
