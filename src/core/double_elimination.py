"""
Double elimination bracket generation and management.

In double elimination:
- Teams must lose twice to be eliminated
- Winners Bracket: Teams that haven't lost yet
- Losers Bracket: Teams that have lost once
- Grand Final: Winners bracket champion vs Losers bracket champion
- Bracket Reset: If losers bracket winner wins Grand Final, a final match decides the champion
"""
import math
from typing import List, Dict, Tuple, Optional
from .elimination import (
    calculate_bracket_size,
    calculate_byes,
    seed_teams_from_pools,
    _generate_bracket_order,
    get_round_name
)


def get_losers_round_name(round_num: int, total_losers_rounds: int) -> str:
    """Get the name for a losers bracket round (0-indexed)."""
    rounds_from_end = total_losers_rounds - round_num - 1
    if rounds_from_end == 0:
        return "Losers Final"
    elif rounds_from_end == 1:
        return "Losers Semifinal"
    else:
        return f"Losers Round {round_num + 1}"


def get_winners_round_name(teams_in_round: int, bracket_size: int) -> str:
    """Get the name for a winners bracket round."""
    if teams_in_round == 2:
        return "Winners Final"
    elif teams_in_round == 4:
        return "Winners Semifinal"
    elif teams_in_round == 8:
        return "Winners Quarterfinal"
    else:
        return f"Winners Round of {teams_in_round}"


def calculate_losers_bracket_rounds(bracket_size: int) -> int:
    """
    Calculate number of rounds in losers bracket.
    For N teams in winners bracket (power of 2):
    - Losers bracket has (2 * log2(N)) - 1 rounds
    """
    if bracket_size < 2:
        return 0
    winners_rounds = int(math.log2(bracket_size))
    return (2 * winners_rounds) - 1


def generate_double_elimination_bracket(pools: Dict[str, Dict]) -> Dict:
    """
    Generate complete double elimination bracket structure.
    
    Returns dict with:
    - 'seeded_teams': list of (team, seed, pool) tuples
    - 'winners_bracket': dict of round_name -> list of matches
    - 'losers_bracket': dict of round_name -> list of matches  
    - 'grand_final': Grand Final match info
    - 'bracket_reset': Potential bracket reset match
    - 'bracket_size': bracket size
    - 'total_winners_rounds': number of winners bracket rounds
    - 'total_losers_rounds': number of losers bracket rounds
    """
    seeded_teams = seed_teams_from_pools(pools)
    
    if len(seeded_teams) < 2:
        return {
            'seeded_teams': seeded_teams,
            'winners_bracket': {},
            'losers_bracket': {},
            'grand_final': None,
            'bracket_reset': None,
            'bracket_size': 0,
            'total_winners_rounds': 0,
            'total_losers_rounds': 0
        }
    
    bracket_size = calculate_bracket_size(len(seeded_teams))
    total_winners_rounds = int(math.log2(bracket_size))
    total_losers_rounds = calculate_losers_bracket_rounds(bracket_size)
    
    # Generate winners bracket (same as single elimination first round)
    winners_bracket = _generate_winners_bracket(seeded_teams, bracket_size, total_winners_rounds)
    
    # Generate losers bracket structure
    losers_bracket = _generate_losers_bracket(bracket_size, total_winners_rounds, total_losers_rounds)
    
    # Grand Final
    grand_final = {
        'teams': ('Winners Bracket Champion', 'Losers Bracket Champion'),
        'round': 'Grand Final',
        'match_number': 1,
        'is_placeholder': True,
        'note': 'If Losers Bracket Champion wins, bracket reset occurs'
    }
    
    # Bracket Reset (only played if losers bracket winner wins Grand Final)
    bracket_reset = {
        'teams': ('Grand Final Winner', 'Grand Final Loser'),
        'round': 'Bracket Reset',
        'match_number': 1,
        'is_placeholder': True,
        'is_conditional': True,
        'note': 'Only played if Losers Bracket Champion wins Grand Final'
    }
    
    return {
        'seeded_teams': seeded_teams,
        'winners_bracket': winners_bracket,
        'losers_bracket': losers_bracket,
        'grand_final': grand_final,
        'bracket_reset': bracket_reset,
        'bracket_size': bracket_size,
        'total_winners_rounds': total_winners_rounds,
        'total_losers_rounds': total_losers_rounds
    }


def _generate_winners_bracket(seeded_teams: List[Tuple], bracket_size: int, total_rounds: int) -> Dict[str, List[Dict]]:
    """Generate winners bracket rounds."""
    winners_bracket = {}
    
    # Create seed-to-team mapping
    seed_to_team = {seed: team for team, seed, _ in seeded_teams}
    
    # Generate bracket order for first round
    bracket_order = _generate_bracket_order(bracket_size)
    
    current_teams_count = bracket_size
    match_num_offset = 0
    
    for round_num in range(total_rounds):
        round_name = get_winners_round_name(current_teams_count, bracket_size)
        round_matches = []
        
        if round_num == 0:
            # First round with actual seeded teams
            match_number = 1
            for i in range(0, len(bracket_order), 2):
                seed1 = bracket_order[i]
                seed2 = bracket_order[i + 1]
                
                team1 = seed_to_team.get(seed1)
                team2 = seed_to_team.get(seed2)
                
                if team1 is None and team2 is None:
                    continue
                elif team2 is None:
                    round_matches.append({
                        'teams': (team1, 'BYE'),
                        'round': round_name,
                        'match_number': match_number,
                        'seeds': (seed1, seed2),
                        'is_bye': True,
                        'losers_feed_to': f"Losers Round 1"
                    })
                elif team1 is None:
                    round_matches.append({
                        'teams': ('BYE', team2),
                        'round': round_name,
                        'match_number': match_number,
                        'seeds': (seed1, seed2),
                        'is_bye': True,
                        'losers_feed_to': f"Losers Round 1"
                    })
                else:
                    round_matches.append({
                        'teams': (team1, team2),
                        'round': round_name,
                        'match_number': match_number,
                        'seeds': (seed1, seed2),
                        'is_bye': False,
                        'losers_feed_to': f"Losers Round 1"
                    })
                match_number += 1
        else:
            # Subsequent rounds with placeholders
            num_matches = current_teams_count // 2
            losers_round = round_num * 2  # Losers from winners round N go to losers round 2N
            for i in range(num_matches):
                round_matches.append({
                    'teams': (f'W{round_num}M{i*2+1}', f'W{round_num}M{i*2+2}'),
                    'round': round_name,
                    'match_number': i + 1,
                    'seeds': None,
                    'is_bye': False,
                    'is_placeholder': True,
                    'losers_feed_to': f"Losers Round {losers_round}" if round_num < total_rounds - 1 else "Grand Final"
                })
        
        winners_bracket[round_name] = round_matches
        match_num_offset += len(round_matches)
        current_teams_count //= 2
    
    return winners_bracket


def _generate_losers_bracket(bracket_size: int, total_winners_rounds: int, total_losers_rounds: int) -> Dict[str, List[Dict]]:
    """
    Generate losers bracket structure.
    
    Losers bracket alternates between:
    - Rounds where losers from winners bracket drop in
    - Rounds where only losers bracket teams compete
    """
    losers_bracket = {}
    
    if total_losers_rounds <= 0:
        return losers_bracket
    
    # Calculate matches per losers round
    # Round 1: bracket_size/2 teams (losers from W Round 1)
    # Round 2: winners of L Round 1 (bracket_size/4 matches)
    # Round 3: bracket_size/4 teams from W Round 2 drop in + L Round 2 winners
    # etc.
    
    current_losers_teams = bracket_size // 2  # Losers from first winners round
    
    for round_num in range(total_losers_rounds):
        round_name = get_losers_round_name(round_num, total_losers_rounds)
        round_matches = []
        
        # Determine if this round has teams dropping from winners bracket
        # Odd rounds (1, 3, 5...) have dropdowns from winners bracket
        has_dropdown = (round_num % 2 == 0) and (round_num > 0)
        
        if round_num == 0:
            # First losers round - losers from winners round 1
            num_matches = current_losers_teams // 2
            for i in range(num_matches):
                round_matches.append({
                    'teams': (f'L-W1M{i*2+1}', f'L-W1M{i*2+2}'),
                    'round': round_name,
                    'match_number': i + 1,
                    'is_placeholder': True,
                    'note': 'Losers from Winners Round 1'
                })
            current_losers_teams = num_matches  # Winners advance
        elif has_dropdown:
            # Dropdown round - losers from winners bracket join
            winners_round = (round_num // 2) + 1
            num_matches = current_losers_teams
            for i in range(num_matches):
                round_matches.append({
                    'teams': (f'L-W{winners_round}M{i+1}', f'L{round_num}M{i+1}'),
                    'round': round_name,
                    'match_number': i + 1,
                    'is_placeholder': True,
                    'note': f'Winners R{winners_round} loser vs Losers R{round_num} winner'
                })
            # Same number advance
        else:
            # Regular losers round - only losers bracket teams
            num_matches = current_losers_teams // 2
            for i in range(num_matches):
                round_matches.append({
                    'teams': (f'L{round_num}M{i*2+1}', f'L{round_num}M{i*2+2}'),
                    'round': round_name,
                    'match_number': i + 1,
                    'is_placeholder': True,
                    'note': f'Losers Round {round_num} winners'
                })
            current_losers_teams = num_matches
        
        losers_bracket[round_name] = round_matches
    
    return losers_bracket


def generate_double_elimination_matches_for_scheduling(pools: Dict[str, Dict]) -> List[Tuple[Tuple[str, str], str]]:
    """
    Generate all double elimination matches in format suitable for scheduling.
    Only returns first-round winners bracket matches (non-byes).
    
    Later rounds depend on results so can't be pre-scheduled.
    
    Returns list of ((team1, team2), round_name) tuples.
    """
    bracket_data = generate_double_elimination_bracket(pools)
    matches = []
    
    # Only schedule first round of winners bracket (actual teams, not placeholders)
    for round_name, round_matches in bracket_data['winners_bracket'].items():
        for match in round_matches:
            if match.get('is_bye', False):
                continue
            if match.get('is_placeholder', False):
                continue
            
            team1, team2 = match['teams']
            matches.append(((team1, team2), round_name))
    
    return matches


def get_double_elimination_bracket_display(pools: Dict[str, Dict]) -> Dict:
    """
    Get double elimination bracket data formatted for UI display.
    """
    bracket_data = generate_double_elimination_bracket(pools)
    
    if not bracket_data['seeded_teams']:
        return {
            'seeded_teams': [],
            'winners_bracket': {},
            'losers_bracket': {},
            'grand_final': None,
            'bracket_reset': None,
            'bracket_size': 0,
            'total_winners_rounds': 0,
            'total_losers_rounds': 0,
            'total_teams': 0,
            'byes': 0,
            'total_matches': 0
        }
    
    total_teams = len(bracket_data['seeded_teams'])
    bracket_size = bracket_data['bracket_size']
    byes = calculate_byes(total_teams)
    
    # Count total matches
    # Winners bracket: bracket_size - 1 matches
    # Losers bracket: bracket_size - 1 matches  
    # Grand Final: 1
    # Bracket Reset: 1 (conditional)
    winners_matches = bracket_size - 1
    losers_matches = bracket_size - 1
    total_matches = winners_matches + losers_matches + 1  # +1 for Grand Final
    
    # Count first round byes
    first_round_byes = 0
    first_round_name = get_winners_round_name(bracket_size, bracket_size)
    if first_round_name in bracket_data['winners_bracket']:
        first_round_byes = sum(
            1 for m in bracket_data['winners_bracket'][first_round_name]
            if m.get('is_bye', False)
        )
    
    return {
        'seeded_teams': bracket_data['seeded_teams'],
        'winners_bracket': bracket_data['winners_bracket'],
        'losers_bracket': bracket_data['losers_bracket'],
        'grand_final': bracket_data['grand_final'],
        'bracket_reset': bracket_data['bracket_reset'],
        'bracket_size': bracket_size,
        'total_winners_rounds': bracket_data['total_winners_rounds'],
        'total_losers_rounds': bracket_data['total_losers_rounds'],
        'total_teams': total_teams,
        'byes': first_round_byes,
        'total_matches': total_matches
    }
