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
    seed_silver_bracket_teams,
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
    - Winners bracket has log2(N) rounds
    - Losers bracket has 2 * (log2(N) - 1) rounds
    
    Pattern: minor, major, minor, major, ... ending with a major round
    """
    if bracket_size < 2:
        return 0
    winners_rounds = int(math.log2(bracket_size))
    return 2 * (winners_rounds - 1)


def generate_double_elimination_bracket(pools: Dict[str, Dict], standings: Optional[Dict] = None, prefix: str = "") -> Dict:
    """
    Generate complete double elimination bracket structure.
    
    Args:
        pools: Pool configuration
        standings: Pool standings
        prefix: Prefix for match codes ("" for Gold, "S" for Silver)
    
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
    seeded_teams = seed_teams_from_pools(pools, standings)
    
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
    
    # Generate winners bracket with prefix
    winners_bracket = _generate_winners_bracket(seeded_teams, bracket_size, total_winners_rounds, prefix)
    
    # Generate losers bracket structure with prefix
    losers_bracket = _generate_losers_bracket(bracket_size, total_winners_rounds, total_losers_rounds, prefix)
    
    # Grand Final
    grand_final = {
        'teams': (f'Winner of {prefix}Winners Bracket', f'Winner of {prefix}Losers Bracket'),
        'round': 'Grand Final',
        'match_number': 1,
        'match_code': f'{prefix}GF',
        'is_placeholder': True,
        'note': 'If Losers Bracket Champion wins, bracket reset occurs'
    }
    
    # Bracket Reset (only played if losers bracket winner wins Grand Final)
    bracket_reset = {
        'teams': (f'Winner {prefix}GF', f'Loser {prefix}GF'),
        'round': 'Bracket Reset',
        'match_number': 1,
        'match_code': f'{prefix}BR',
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


def _generate_winners_bracket(seeded_teams: List[Tuple], bracket_size: int, total_rounds: int, prefix: str = "") -> Dict[str, List[Dict]]:
    """Generate winners bracket rounds.
    
    Args:
        seeded_teams: List of (team_name, seed, pool) tuples
        bracket_size: Power of 2 bracket size
        total_rounds: Number of rounds in winners bracket
        prefix: Prefix for match codes ("" for Gold, "S" for Silver)
    """
    winners_bracket = {}
    
    # Create seed-to-team mapping
    seed_to_team = {seed: team for team, seed, _ in seeded_teams}
    
    # Generate bracket order for first round
    bracket_order = _generate_bracket_order(bracket_size)
    
    current_teams_count = bracket_size
    
    for round_num in range(total_rounds):
        round_name = get_winners_round_name(current_teams_count, bracket_size)
        round_matches = []
        round_code = f"{prefix}W{round_num + 1}"  # W1, W2, W3 or SW1, SW2, SW3
        
        if round_num == 0:
            # First round with actual seeded teams
            match_in_round = 1
            for i in range(0, len(bracket_order), 2):
                seed1 = bracket_order[i]
                seed2 = bracket_order[i + 1]
                
                team1 = seed_to_team.get(seed1)
                team2 = seed_to_team.get(seed2)
                
                match_code = f"{round_code}-M{match_in_round}"
                
                if team1 is None and team2 is None:
                    continue
                elif team2 is None:
                    round_matches.append({
                        'teams': (team1, 'BYE'),
                        'round': round_name,
                        'match_number': match_in_round,
                        'match_code': match_code,
                        'seeds': (seed1, seed2),
                        'is_bye': True,
                        'losers_feed_to': f"{prefix}L1"
                    })
                elif team1 is None:
                    round_matches.append({
                        'teams': ('BYE', team2),
                        'round': round_name,
                        'match_number': match_in_round,
                        'match_code': match_code,
                        'seeds': (seed1, seed2),
                        'is_bye': True,
                        'losers_feed_to': f"{prefix}L1"
                    })
                else:
                    round_matches.append({
                        'teams': (team1, team2),
                        'round': round_name,
                        'match_number': match_in_round,
                        'match_code': match_code,
                        'seeds': (seed1, seed2),
                        'is_bye': False,
                        'losers_feed_to': f"{prefix}L1"
                    })
                match_in_round += 1
        else:
            # Subsequent rounds with placeholders
            num_matches = current_teams_count // 2
            prev_round_code = f"{prefix}W{round_num}"
            for i in range(num_matches):
                match_code = f"{round_code}-M{i + 1}"
                round_matches.append({
                    'teams': (f'Winner {prev_round_code}-M{i*2+1}', f'Winner {prev_round_code}-M{i*2+2}'),
                    'round': round_name,
                    'match_number': i + 1,
                    'match_code': match_code,
                    'seeds': None,
                    'is_bye': False,
                    'is_placeholder': True,
                    'losers_feed_to': f"{prefix}L{round_num * 2}" if round_num < total_rounds - 1 else f"{prefix}GF"
                })
        
        winners_bracket[round_name] = round_matches
        current_teams_count //= 2
    
    return winners_bracket


def _generate_losers_bracket(bracket_size: int, total_winners_rounds: int, total_losers_rounds: int, prefix: str = "") -> Dict[str, List[Dict]]:
    """
    Generate losers bracket structure following standard double elimination format.
    
    Args:
        bracket_size: Power of 2 bracket size
        total_winners_rounds: Number of rounds in winners bracket
        total_losers_rounds: Number of rounds in losers bracket
        prefix: Prefix for match codes ("" for Gold, "S" for Silver)
    
    The losers bracket alternates between:
    - Minor rounds (even indices: 0, 2, 4...): Only losers bracket teams compete
    - Major rounds (odd indices: 1, 3, 5...): Losers from winners bracket drop in
    
    For 8-team bracket:
    - L Round 1 (minor): 4 W-QF losers pair off → 2 matches → 2 winners
    - L Round 2 (major): 2 W-SF losers + 2 L-R1 winners → 2 matches → 2 winners  
    - L Round 3 (minor): 2 L-R2 winners pair off → 1 match → 1 winner
    - L Round 4 (major): 1 W-F loser + 1 L-R3 winner → 1 match → 1 winner (L champion)
    """
    losers_bracket = {}
    
    if total_losers_rounds <= 0:
        return losers_bracket
    
    current_losers_count = bracket_size // 2  # Losers from first winners round
    winners_round_idx = 1  # Track which winners round feeds losers (starts after W Round 1)
    
    for round_num in range(total_losers_rounds):
        round_name = get_losers_round_name(round_num, total_losers_rounds)
        round_code = f"{prefix}L{round_num + 1}"  # L1, L2, L3 or SL1, SL2, SL3
        round_matches = []
        
        # Major rounds (odd: 1, 3, 5...) have dropdowns from winners bracket
        is_major_round = (round_num % 2 == 1)
        
        if round_num == 0:
            # First losers round (minor) - losers from winners round 1 play each other
            num_matches = current_losers_count // 2
            for i in range(num_matches):
                match_code = f"{round_code}-M{i + 1}"
                round_matches.append({
                    'teams': (f'Loser {prefix}W1-M{i*2+1}', f'Loser {prefix}W1-M{i*2+2}'),
                    'round': round_name,
                    'match_number': i + 1,
                    'match_code': match_code,
                    'is_placeholder': True,
                    'note': 'Losers from Winners Round 1'
                })
            current_losers_count = num_matches  # Winners advance
            
        elif is_major_round:
            # Major/dropdown round - losers from winners bracket join
            winners_round_idx += 1
            w_round = winners_round_idx
            prev_losers_round = round_num  # Previous losers round number (1-indexed for display)
            
            num_matches = current_losers_count
            for i in range(num_matches):
                match_code = f"{round_code}-M{i + 1}"
                round_matches.append({
                    'teams': (f'Loser {prefix}W{w_round}-M{i+1}', f'Winner {prefix}L{prev_losers_round}-M{i+1}'),
                    'round': round_name,
                    'match_number': i + 1,
                    'match_code': match_code,
                    'is_placeholder': True,
                    'note': f'Winners R{w_round} loser vs Losers R{prev_losers_round} winner'
                })
            
        else:
            # Minor round - only losers bracket teams compete (winners from previous round)
            prev_losers_round = round_num  # Previous L round (1-indexed: L2 comes after L1, references L1)
            num_matches = current_losers_count // 2
            for i in range(num_matches):
                match_code = f"{round_code}-M{i + 1}"
                round_matches.append({
                    'teams': (f'Winner {prefix}L{prev_losers_round}-M{i*2+1}', f'Winner {prefix}L{prev_losers_round}-M{i*2+2}'),
                    'round': round_name,
                    'match_number': i + 1,
                    'match_code': match_code,
                    'is_placeholder': True,
                    'note': f'Losers Round {prev_losers_round} winners'
                })
            current_losers_count = num_matches
        
        losers_bracket[round_name] = round_matches
    
    return losers_bracket


def generate_all_bracket_matches_for_scheduling(pools: Dict[str, Dict], standings: Optional[Dict] = None, include_silver: bool = False) -> List[Dict]:
    """
    Generate ALL double elimination matches for scheduling, including placeholders.
    
    Returns list of match dicts with:
    - teams: [team1, team2] (may be placeholders like "Winner W1-M1")
    - round: round name (e.g., "Winners Round of 8", "Losers Round 1")
    - match_number: match number within round
    - match_code: unique code like "W1-M1", "L2-M3", "GF"
    - phase: "Bracket" or "Silver Bracket"
    - is_placeholder: True if teams are not yet determined
    - is_bye: True if this is a bye match
    """
    bracket_data = generate_double_elimination_bracket(pools, standings)
    matches = []
    
    if not bracket_data['seeded_teams']:
        return matches
    
    # Winners bracket matches
    for round_name, round_matches in bracket_data['winners_bracket'].items():
        for match in round_matches:
            if match.get('is_bye', False):
                continue
            matches.append({
                'teams': list(match['teams']),
                'round': round_name,
                'match_number': match.get('match_number', 0),
                'match_code': match.get('match_code', ''),
                'phase': 'Bracket',
                'is_placeholder': match.get('is_placeholder', False),
                'is_bye': False
            })
    
    # Losers bracket matches
    for round_name, round_matches in bracket_data['losers_bracket'].items():
        for match in round_matches:
            matches.append({
                'teams': list(match['teams']),
                'round': round_name,
                'match_number': match.get('match_number', 0),
                'match_code': match.get('match_code', ''),
                'phase': 'Bracket',
                'is_placeholder': True,  # All losers bracket matches are placeholders initially
                'is_bye': False
            })
    
    # Grand Final
    if bracket_data['grand_final']:
        matches.append({
            'teams': list(bracket_data['grand_final']['teams']),
            'round': 'Grand Final',
            'match_number': 1,
            'match_code': bracket_data['grand_final'].get('match_code', 'GF'),
            'phase': 'Bracket',
            'is_placeholder': True,
            'is_bye': False
        })
    
    # Bracket Reset (conditional)
    if bracket_data['bracket_reset']:
        matches.append({
            'teams': list(bracket_data['bracket_reset']['teams']),
            'round': 'Bracket Reset',
            'match_number': 1,
            'match_code': bracket_data['bracket_reset'].get('match_code', 'BR'),
            'phase': 'Bracket',
            'is_placeholder': True,
            'is_bye': False,
            'is_conditional': True
        })
    
    # Silver bracket if enabled
    if include_silver:
        silver_matches = generate_silver_bracket_matches_for_scheduling(pools, standings)
        matches.extend(silver_matches)
    
    return matches


def generate_silver_bracket_matches_for_scheduling(pools: Dict[str, Dict], standings: Optional[Dict] = None) -> List[Dict]:
    """Generate all silver bracket matches for scheduling with placeholders using prefix="S"."""
    seeded_teams = seed_silver_bracket_teams(pools, standings)
    
    if len(seeded_teams) < 2:
        return []
    
    bracket_size = calculate_bracket_size(len(seeded_teams))
    total_winners_rounds = int(math.log2(bracket_size))
    total_losers_rounds = calculate_losers_bracket_rounds(bracket_size)
    
    # Use prefix="S" so match codes and placeholders are correct for Silver
    winners_bracket = _generate_winners_bracket(seeded_teams, bracket_size, total_winners_rounds, prefix="S")
    losers_bracket = _generate_losers_bracket(bracket_size, total_winners_rounds, total_losers_rounds, prefix="S")
    
    matches = []
    
    # Silver Winners bracket - codes already have S prefix
    for round_name, round_matches in winners_bracket.items():
        for match in round_matches:
            if match.get('is_bye', False):
                continue
            matches.append({
                'teams': list(match['teams']),
                'round': f"Silver {round_name}",
                'match_number': match.get('match_number', 0),
                'match_code': match.get('match_code', ''),
                'phase': 'Silver Bracket',
                'is_placeholder': match.get('is_placeholder', False),
                'is_bye': False
            })
    
    # Silver Losers bracket - codes already have S prefix
    for round_name, round_matches in losers_bracket.items():
        for match in round_matches:
            matches.append({
                'teams': list(match['teams']),
                'round': f"Silver {round_name}",
                'match_number': match.get('match_number', 0),
                'match_code': match.get('match_code', ''),
                'phase': 'Silver Bracket',
                'is_placeholder': True,
                'is_bye': False
            })
    
    # Silver Grand Final
    matches.append({
        'teams': ['Winner of SWinners Bracket', 'Winner of SLosers Bracket'],
        'round': 'Silver Grand Final',
        'match_number': 1,
        'match_code': 'SGF',
        'phase': 'Silver Bracket',
        'is_placeholder': True,
        'is_bye': False
    })
    
    return matches


def generate_double_elimination_matches_for_scheduling(pools: Dict[str, Dict], standings: Optional[Dict] = None) -> List[Tuple[Tuple[str, str], str]]:
    """
    Generate all double elimination matches in format suitable for scheduling.
    Only returns first-round winners bracket matches (non-byes).
    
    Later rounds depend on results so can't be pre-scheduled.
    
    Returns list of ((team1, team2), round_name) tuples.
    """
    bracket_data = generate_double_elimination_bracket(pools, standings)
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


def generate_silver_double_matches_for_scheduling(pools: Dict[str, Dict], standings: Optional[Dict] = None) -> List[Tuple[Tuple[str, str], str]]:
    """
    Generate silver bracket double elimination matches for scheduling.
    Only returns first-round silver winners bracket matches (non-byes).
    
    Returns list of ((team1, team2), "Silver " + round_name) tuples.
    """
    seeded_teams = seed_silver_bracket_teams(pools, standings)
    
    if len(seeded_teams) < 2:
        return []
    
    bracket_data = generate_double_elimination_bracket.__wrapped__(seeded_teams) if hasattr(generate_double_elimination_bracket, '__wrapped__') else None
    
    # Generate bracket manually for silver teams
    bracket_size = calculate_bracket_size(len(seeded_teams))
    seed_to_team = {seed: team for team, seed, _ in seeded_teams}
    bracket_order = _generate_bracket_order(bracket_size)
    
    matches = []
    first_round_name = get_winners_round_name(bracket_size, bracket_size)
    
    match_number = 1
    for i in range(0, len(bracket_order), 2):
        seed1 = bracket_order[i]
        seed2 = bracket_order[i + 1]
        
        team1 = seed_to_team.get(seed1)
        team2 = seed_to_team.get(seed2)
        
        if team1 is None and team2 is None:
            continue
        
        # Skip byes
        if team1 is None or team2 is None:
            continue
        
        matches.append(((team1, team2), f"Silver {first_round_name}"))
        match_number += 1
    
    return matches


def get_double_elimination_bracket_display(pools: Dict[str, Dict], standings: Optional[Dict] = None) -> Dict:
    """
    Get double elimination bracket data formatted for UI display.
    """
    bracket_data = generate_double_elimination_bracket(pools, standings)
    
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


def generate_double_bracket_with_results(pools: Dict[str, Dict], standings: Optional[Dict] = None,
                                          bracket_results: Optional[Dict] = None) -> Dict:
    """
    Generate double elimination bracket with results applied, advancing winners and losers.
    
    Args:
        pools: Pool configuration
        standings: Pool standings with team placements
        bracket_results: Dict of match results keyed by "bracket_type_round_match_number"
    
    Returns:
        Complete bracket data with results applied and teams advanced
    """
    if bracket_results is None:
        bracket_results = {}
    
    seeded_teams = seed_teams_from_pools(pools, standings)
    
    if len(seeded_teams) < 2:
        return {
            'seeded_teams': seeded_teams,
            'winners_bracket': {},
            'losers_bracket': {},
            'grand_final': None,
            'bracket_reset': None,
            'bracket_size': 0,
            'total_winners_rounds': 0,
            'total_losers_rounds': 0,
            'total_teams': 0,
            'byes': 0,
            'total_matches': 0,
            'champion': None
        }
    
    bracket_size = calculate_bracket_size(len(seeded_teams))
    total_winners_rounds = int(math.log2(bracket_size))
    total_losers_rounds = calculate_losers_bracket_rounds(bracket_size)
    
    # Create seed-to-team mapping
    seed_to_team = {seed: team for team, seed, _ in seeded_teams}
    
    # Generate bracket order for first round
    bracket_order = _generate_bracket_order(bracket_size)
    
    # Track winners and losers from each match
    winners_match_winners = {}  # "round_name_match" -> winner
    winners_match_losers = {}   # "round_name_match" -> loser
    losers_match_winners = {}   # "round_name_match" -> winner
    
    # Generate winners bracket round names
    winners_round_names = []
    temp_count = bracket_size
    for _ in range(total_winners_rounds):
        winners_round_names.append(get_winners_round_name(temp_count, bracket_size))
        temp_count //= 2
    
    # Generate losers bracket round names
    losers_round_names = []
    for i in range(total_losers_rounds):
        losers_round_names.append(get_losers_round_name(i, total_losers_rounds))
    
    # Build winners bracket with results
    winners_bracket = {}
    current_teams_count = bracket_size
    
    for round_idx, round_name in enumerate(winners_round_names):
        round_matches = []
        num_matches = current_teams_count // 2
        
        if round_idx == 0:
            # First round with actual seeded teams
            match_number = 1
            for i in range(0, len(bracket_order), 2):
                seed1 = bracket_order[i]
                seed2 = bracket_order[i + 1]
                
                team1 = seed_to_team.get(seed1)
                team2 = seed_to_team.get(seed2)
                
                if team1 is None and team2 is None:
                    continue
                
                is_bye = (team2 is None) or (team1 is None)
                if team2 is None:
                    actual_team1, actual_team2 = team1, 'BYE'
                    bye_winner = team1
                elif team1 is None:
                    actual_team1, actual_team2 = 'BYE', team2
                    bye_winner = team2
                else:
                    actual_team1, actual_team2 = team1, team2
                    bye_winner = None
                
                match_key = f"winners_{round_name}_{match_number}"
                result = bracket_results.get(match_key, {})
                
                if is_bye:
                    winner = bye_winner
                    loser = None
                    is_playable = False
                elif result.get('completed'):
                    winner = result.get('winner')
                    loser = result.get('loser')
                    is_playable = False
                else:
                    winner = None
                    loser = None
                    is_playable = True
                
                match_data = {
                    'teams': (actual_team1, actual_team2),
                    'round': round_name,
                    'match_number': match_number,
                    'seeds': (seed1, seed2),
                    'is_bye': is_bye,
                    'is_playable': is_playable,
                    'winner': winner,
                    'loser': loser,
                    'result': result if result else None,
                    'losers_feed_to': 'Losers Round 1' if not is_bye else None
                }
                round_matches.append(match_data)
                
                if winner:
                    winners_match_winners[f"{round_name}_{match_number}"] = winner
                if loser:
                    winners_match_losers[f"{round_name}_{match_number}"] = loser
                
                match_number += 1
        else:
            prev_round_name = winners_round_names[round_idx - 1]
            
            for i in range(num_matches):
                prev_match1 = i * 2 + 1
                prev_match2 = i * 2 + 2
                
                team1_key = f"{prev_round_name}_{prev_match1}"
                team2_key = f"{prev_round_name}_{prev_match2}"
                
                team1 = winners_match_winners.get(team1_key)
                team2 = winners_match_winners.get(team2_key)
                
                match_number = i + 1
                match_key = f"winners_{round_name}_{match_number}"
                result = bracket_results.get(match_key, {})
                
                if team1 and team2:
                    if result.get('completed'):
                        winner = result.get('winner')
                        loser = result.get('loser')
                        is_playable = False
                    else:
                        winner = None
                        loser = None
                        is_playable = True
                    is_placeholder = False
                else:
                    winner = None
                    loser = None
                    is_playable = False
                    is_placeholder = True
                    team1 = team1 or f'W{round_idx}M{prev_match1}'
                    team2 = team2 or f'W{round_idx}M{prev_match2}'
                
                losers_round = round_idx * 2 if round_idx < total_winners_rounds - 1 else None
                
                match_data = {
                    'teams': (team1, team2),
                    'round': round_name,
                    'match_number': match_number,
                    'seeds': None,
                    'is_bye': False,
                    'is_placeholder': is_placeholder,
                    'is_playable': is_playable,
                    'winner': winner,
                    'loser': loser,
                    'result': result if result else None,
                    'losers_feed_to': f"Losers Round {losers_round + 1}" if losers_round is not None else "Grand Final"
                }
                round_matches.append(match_data)
                
                if winner:
                    winners_match_winners[f"{round_name}_{match_number}"] = winner
                if loser:
                    winners_match_losers[f"{round_name}_{match_number}"] = loser
        
        winners_bracket[round_name] = round_matches
        current_teams_count //= 2
    
    # Build losers bracket with results
    losers_bracket = {}
    
    for round_idx, round_name in enumerate(losers_round_names):
        round_matches = []
        
        # Major/dropdown rounds are odd indices (1, 3, 5...)
        is_major_round = (round_idx % 2 == 1)
        
        if round_idx == 0:
            # First losers round - losers from winners round 1
            winners_round1_name = winners_round_names[0]
            winners_round1_matches = winners_bracket.get(winners_round1_name, [])
            
            # Pair up losers from adjacent winners matches
            losers_from_w1 = []
            for m in winners_round1_matches:
                if not m.get('is_bye'):
                    # Add loser if known, otherwise None as placeholder
                    losers_from_w1.append(m.get('loser'))
            
            # Calculate expected number of matches based on bracket structure
            num_matches = len(losers_from_w1) // 2
            if num_matches == 0:
                num_matches = bracket_size // 4  # Fallback based on bracket size
            
            for i in range(num_matches):
                team1 = losers_from_w1[i * 2] if i * 2 < len(losers_from_w1) else None
                team2 = losers_from_w1[i * 2 + 1] if i * 2 + 1 < len(losers_from_w1) else None
                
                match_number = i + 1
                match_key = f"losers_{round_name}_{match_number}"
                result = bracket_results.get(match_key, {})
                
                if team1 and team2:
                    if result.get('completed'):
                        winner = result.get('winner')
                        is_playable = False
                    else:
                        winner = None
                        is_playable = True
                    is_placeholder = False
                else:
                    winner = None
                    is_playable = False
                    is_placeholder = True
                    team1 = team1 or f'Loser W1-M{i*2+1}'
                    team2 = team2 or f'Loser W1-M{i*2+2}'
                
                match_data = {
                    'teams': (team1, team2),
                    'round': round_name,
                    'match_number': match_number,
                    'is_placeholder': is_placeholder,
                    'is_playable': is_playable,
                    'winner': winner,
                    'result': result if result else None,
                    'note': 'Losers from Winners Round 1'
                }
                round_matches.append(match_data)
                
                if winner:
                    losers_match_winners[f"{round_name}_{match_number}"] = winner
        
        elif is_major_round:
            # Major/dropdown round - losers from winners bracket join
            # Winners round that feeds: (round_idx // 2) + 1
            winners_round_idx = (round_idx // 2) + 1
            prev_losers_round = losers_round_names[round_idx - 1]
            
            # Get winners from previous losers round (or placeholders)
            prev_losers_matches = losers_bracket.get(prev_losers_round, [])
            prev_losers = []
            for m in prev_losers_matches:
                prev_losers.append(m.get('winner'))  # May be None
            
            # Get losers from corresponding winners round (or placeholders)
            w_losers = []
            if winners_round_idx < len(winners_round_names):
                w_round = winners_round_names[winners_round_idx]
                for m in winners_bracket.get(w_round, []):
                    w_losers.append(m.get('loser'))  # May be None
            
            # Calculate expected matches based on structure
            num_matches = max(len(prev_losers), len(w_losers), 1)
            if num_matches == 0:
                # Fallback based on bracket structure
                num_matches = bracket_size // (2 ** (winners_round_idx + 1))
            
            for i in range(num_matches):
                team1 = w_losers[i] if i < len(w_losers) and w_losers[i] else None
                team2 = prev_losers[i] if i < len(prev_losers) and prev_losers[i] else None
                
                match_number = i + 1
                match_key = f"losers_{round_name}_{match_number}"
                result = bracket_results.get(match_key, {})
                
                if team1 and team2:
                    if result.get('completed'):
                        winner = result.get('winner')
                        is_playable = False
                    else:
                        winner = None
                        is_playable = True
                    is_placeholder = False
                else:
                    winner = None
                    is_playable = False
                    is_placeholder = True
                    w_round_num = winners_round_idx + 1
                    team1 = team1 or f'Loser W{w_round_num}-M{i+1}'
                    team2 = team2 or f'Winner L{round_idx}-M{i+1}'
                
                match_data = {
                    'teams': (team1, team2),
                    'round': round_name,
                    'match_number': match_number,
                    'is_placeholder': is_placeholder,
                    'is_playable': is_playable,
                    'winner': winner,
                    'result': result if result else None,
                    'note': f'Winners R{winners_round_idx+1} loser vs Losers R{round_idx} winner'
                }
                round_matches.append(match_data)
                
                if winner:
                    losers_match_winners[f"{round_name}_{match_number}"] = winner
        
        else:
            # Regular losers round
            prev_round = losers_round_names[round_idx - 1]
            prev_round_matches = losers_bracket.get(prev_round, [])
            
            # Get winners or prepare placeholders
            prev_winners = [m.get('winner') for m in prev_round_matches]
            
            # Calculate expected matches
            num_matches = len(prev_round_matches) // 2
            if num_matches == 0:
                num_matches = 1  # At least show structure
            
            for i in range(num_matches):
                team1 = prev_winners[i * 2] if i * 2 < len(prev_winners) and prev_winners[i * 2] else None
                team2 = prev_winners[i * 2 + 1] if i * 2 + 1 < len(prev_winners) and prev_winners[i * 2 + 1] else None
                
                match_number = i + 1
                match_key = f"losers_{round_name}_{match_number}"
                result = bracket_results.get(match_key, {})
                
                if team1 and team2:
                    if result.get('completed'):
                        winner = result.get('winner')
                        is_playable = False
                    else:
                        winner = None
                        is_playable = True
                    is_placeholder = False
                else:
                    winner = None
                    is_playable = False
                    is_placeholder = True
                    prev_round_num = round_idx
                    team1 = team1 or f'Winner L{prev_round_num}-M{i*2+1}'
                    team2 = team2 or f'Winner L{prev_round_num}-M{i*2+2}'
                
                match_data = {
                    'teams': (team1, team2),
                    'round': round_name,
                    'match_number': match_number,
                    'is_placeholder': is_placeholder,
                    'is_playable': is_playable,
                    'winner': winner,
                    'result': result if result else None,
                    'note': f'Losers Round {round_idx} winners'
                }
                round_matches.append(match_data)
                
                if winner:
                    losers_match_winners[f"{round_name}_{match_number}"] = winner
        
        losers_bracket[round_name] = round_matches
    
    # Determine Grand Final participants
    winners_champion = None
    if winners_round_names:
        final_round = winners_round_names[-1]
        if winners_bracket.get(final_round):
            winners_champion = winners_bracket[final_round][0].get('winner')
    
    losers_champion = None
    if losers_round_names:
        losers_final = losers_round_names[-1]
        if losers_bracket.get(losers_final):
            losers_champion = losers_bracket[losers_final][0].get('winner')
    
    # Grand Final
    gf_match_key = "grand_final_Grand Final_1"
    gf_result = bracket_results.get(gf_match_key, {})
    
    if winners_champion and losers_champion:
        if gf_result.get('completed'):
            gf_winner = gf_result.get('winner')
            gf_is_playable = False
        else:
            gf_winner = None
            gf_is_playable = True
        gf_is_placeholder = False
    else:
        gf_winner = None
        gf_is_playable = False
        gf_is_placeholder = True
    
    grand_final = {
        'teams': (winners_champion or 'Winners Bracket Champion', 
                  losers_champion or 'Losers Bracket Champion'),
        'round': 'Grand Final',
        'match_number': 1,
        'is_placeholder': gf_is_placeholder,
        'is_playable': gf_is_playable,
        'winner': gf_winner,
        'result': gf_result if gf_result else None,
        'note': 'If Losers Bracket Champion wins, bracket reset occurs'
    }
    
    # Bracket Reset (conditional)
    br_match_key = "bracket_reset_Bracket Reset_1"
    br_result = bracket_results.get(br_match_key, {})
    
    # Bracket reset only happens if losers champion won grand final
    needs_reset = gf_winner and gf_winner == losers_champion
    
    if needs_reset:
        if br_result.get('completed'):
            br_winner = br_result.get('winner')
            br_is_playable = False
        else:
            br_winner = None
            br_is_playable = True
        br_is_placeholder = False
        br_teams = (winners_champion, losers_champion)
    else:
        br_winner = None
        br_is_playable = False
        br_is_placeholder = True
        br_teams = ('Grand Final Winner', 'Grand Final Loser')
    
    bracket_reset = {
        'teams': br_teams,
        'round': 'Bracket Reset',
        'match_number': 1,
        'is_placeholder': br_is_placeholder,
        'is_conditional': True,
        'is_playable': br_is_playable,
        'winner': br_winner,
        'result': br_result if br_result else None,
        'note': 'Only played if Losers Bracket Champion wins Grand Final',
        'needs_reset': needs_reset
    }
    
    # Determine overall champion
    champion = None
    if br_result.get('completed'):
        champion = br_result.get('winner')
    elif gf_winner and gf_winner == winners_champion:
        champion = winners_champion
    
    total_teams = len(seeded_teams)
    byes = calculate_byes(total_teams)
    
    first_round_byes = 0
    first_round_name = get_winners_round_name(bracket_size, bracket_size)
    if first_round_name in winners_bracket:
        first_round_byes = sum(1 for m in winners_bracket[first_round_name] if m.get('is_bye', False))
    
    winners_matches = bracket_size - 1
    losers_matches = bracket_size - 1
    total_matches = winners_matches + losers_matches + 1
    
    return {
        'seeded_teams': seeded_teams,
        'winners_bracket': winners_bracket,
        'losers_bracket': losers_bracket,
        'grand_final': grand_final,
        'bracket_reset': bracket_reset,
        'bracket_size': bracket_size,
        'total_winners_rounds': total_winners_rounds,
        'total_losers_rounds': total_losers_rounds,
        'total_teams': total_teams,
        'byes': first_round_byes,
        'total_matches': total_matches,
        'champion': champion
    }


def generate_silver_double_bracket_with_results(pools: Dict[str, Dict], standings: Optional[Dict] = None,
                                                 bracket_results: Optional[Dict] = None) -> Optional[Dict]:
    """
    Generate silver double elimination bracket with results applied for non-advancing teams.
    
    Args:
        pools: Pool configuration
        standings: Pool standings with team placements
        bracket_results: Dict of match results keyed by "silver_winners/losers_round_match_number"
    
    Returns:
        Complete silver bracket data, or None if not enough teams
    """
    if bracket_results is None:
        bracket_results = {}
    
    seeded_teams = seed_silver_bracket_teams(pools, standings)
    
    # Need at least 2 teams for a bracket
    if len(seeded_teams) < 2:
        return None
    
    bracket_size = calculate_bracket_size(len(seeded_teams))
    total_winners_rounds = int(math.log2(bracket_size))
    total_losers_rounds = calculate_losers_bracket_rounds(bracket_size)
    
    # Create seed-to-team mapping
    seed_to_team = {seed: team for team, seed, _ in seeded_teams}
    
    # Generate bracket order for first round
    bracket_order = _generate_bracket_order(bracket_size)
    
    # Track winners and losers from each match
    winners_match_winners = {}
    winners_match_losers = {}
    losers_match_winners = {}
    
    # Generate winners bracket round names
    winners_round_names = []
    temp_count = bracket_size
    for _ in range(total_winners_rounds):
        winners_round_names.append(get_winners_round_name(temp_count, bracket_size))
        temp_count //= 2
    
    # Generate losers bracket round names
    losers_round_names = []
    for i in range(total_losers_rounds):
        losers_round_names.append(get_losers_round_name(i, total_losers_rounds))
    
    # Build winners bracket with results (using silver_winners_ prefix)
    winners_bracket = {}
    current_teams_count = bracket_size
    
    for round_idx, round_name in enumerate(winners_round_names):
        round_matches = []
        num_matches = current_teams_count // 2
        
        if round_idx == 0:
            match_number = 1
            for i in range(0, len(bracket_order), 2):
                seed1 = bracket_order[i]
                seed2 = bracket_order[i + 1]
                
                team1 = seed_to_team.get(seed1)
                team2 = seed_to_team.get(seed2)
                
                if team1 is None and team2 is None:
                    continue
                
                is_bye = (team2 is None) or (team1 is None)
                if team2 is None:
                    actual_team1, actual_team2 = team1, 'BYE'
                    bye_winner = team1
                elif team1 is None:
                    actual_team1, actual_team2 = 'BYE', team2
                    bye_winner = team2
                else:
                    actual_team1, actual_team2 = team1, team2
                    bye_winner = None
                
                # Use silver_winners_ prefix
                match_key = f"silver_winners_{round_name}_{match_number}"
                result = bracket_results.get(match_key, {})
                
                if is_bye:
                    winner = bye_winner
                    loser = None
                    is_playable = False
                elif result.get('completed'):
                    winner = result.get('winner')
                    loser = result.get('loser')
                    is_playable = False
                else:
                    winner = None
                    loser = None
                    is_playable = True
                
                match_data = {
                    'teams': (actual_team1, actual_team2),
                    'round': round_name,
                    'match_number': match_number,
                    'match_code': f"SW{round_idx + 1}-M{match_number}",
                    'seeds': (seed1, seed2),
                    'is_bye': is_bye,
                    'is_playable': is_playable,
                    'winner': winner,
                    'loser': loser,
                    'result': result if result else None
                }
                round_matches.append(match_data)
                
                if winner:
                    winners_match_winners[f"{round_name}_{match_number}"] = winner
                if loser:
                    winners_match_losers[f"{round_name}_{match_number}"] = loser
                
                match_number += 1
        else:
            prev_round_name = winners_round_names[round_idx - 1]
            
            for i in range(num_matches):
                prev_match1 = i * 2 + 1
                prev_match2 = i * 2 + 2
                
                team1 = winners_match_winners.get(f"{prev_round_name}_{prev_match1}")
                team2 = winners_match_winners.get(f"{prev_round_name}_{prev_match2}")
                
                match_number = i + 1
                match_key = f"silver_winners_{round_name}_{match_number}"
                result = bracket_results.get(match_key, {})
                
                if team1 and team2:
                    if result.get('completed'):
                        winner = result.get('winner')
                        loser = result.get('loser')
                        is_playable = False
                    else:
                        winner = None
                        loser = None
                        is_playable = True
                    is_placeholder = False
                else:
                    winner = None
                    loser = None
                    is_playable = False
                    is_placeholder = True
                    team1 = team1 or f'Winner M{prev_match1}'
                    team2 = team2 or f'Winner M{prev_match2}'
                
                match_data = {
                    'teams': (team1, team2),
                    'round': round_name,
                    'match_number': match_number,
                    'match_code': f"SW{round_idx + 1}-M{match_number}",
                    'seeds': None,
                    'is_bye': False,
                    'is_placeholder': is_placeholder,
                    'is_playable': is_playable,
                    'winner': winner,
                    'loser': loser,
                    'result': result if result else None
                }
                round_matches.append(match_data)
                
                if winner:
                    winners_match_winners[f"{round_name}_{match_number}"] = winner
                if loser:
                    winners_match_losers[f"{round_name}_{match_number}"] = loser
        
        winners_bracket[round_name] = round_matches
        current_teams_count //= 2
    
    # Build losers bracket with proper placeholders
    losers_bracket = {}
    for round_idx, round_name in enumerate(losers_round_names):
        round_matches = []
        has_dropdown = round_idx > 0 and round_idx % 2 == 1
        
        if round_idx == 0:
            # First losers round - losers from winners round 1
            winners_round1_name = winners_round_names[0] if winners_round_names else None
            winners_round1_matches = winners_bracket.get(winners_round1_name, []) if winners_round1_name else []
            
            num_matches = max(len(winners_round1_matches) // 2, bracket_size // 4)
            for i in range(num_matches):
                # Get losers or use placeholders
                m1 = winners_round1_matches[i * 2] if i * 2 < len(winners_round1_matches) else {}
                m2 = winners_round1_matches[i * 2 + 1] if i * 2 + 1 < len(winners_round1_matches) else {}
                team1 = m1.get('loser') if not m1.get('is_bye') else None
                team2 = m2.get('loser') if not m2.get('is_bye') else None
                
                match_number = i + 1
                match_key = f"silver_losers_{round_name}_{match_number}"
                result = bracket_results.get(match_key, {})
                
                if team1 and team2:
                    if result.get('completed'):
                        winner = result.get('winner')
                        is_playable = False
                    else:
                        winner = None
                        is_playable = True
                    is_placeholder = False
                else:
                    winner = None
                    is_playable = False
                    is_placeholder = True
                    team1 = team1 or f'Loser SW1-M{i*2+1}'
                    team2 = team2 or f'Loser SW1-M{i*2+2}'
                
                match_data = {
                    'teams': (team1, team2),
                    'round': round_name,
                    'match_number': match_number,
                    'match_code': f"SL{round_idx + 1}-M{match_number}",
                    'is_placeholder': is_placeholder,
                    'is_playable': is_playable,
                    'winner': winner,
                    'result': result if result else None
                }
                round_matches.append(match_data)
                
                if result.get('winner'):
                    losers_match_winners[f"{round_name}_{match_number}"] = result.get('winner')
        
        elif has_dropdown:
            # Major/dropdown round - losers from winners bracket join
            winners_round_idx = (round_idx // 2) + 1
            prev_losers_round = losers_round_names[round_idx - 1]
            
            # Get winners from previous losers round
            prev_losers_matches = losers_bracket.get(prev_losers_round, [])
            prev_losers = [m.get('winner') for m in prev_losers_matches]
            
            # Get losers from corresponding winners round
            w_losers = []
            if winners_round_idx < len(winners_round_names):
                w_round = winners_round_names[winners_round_idx]
                for m in winners_bracket.get(w_round, []):
                    w_losers.append(m.get('loser'))
            
            num_matches = max(len(prev_losers), len(w_losers), 1)
            
            for i in range(num_matches):
                team1 = w_losers[i] if i < len(w_losers) and w_losers[i] else None
                team2 = prev_losers[i] if i < len(prev_losers) and prev_losers[i] else None
                
                match_number = i + 1
                match_key = f"silver_losers_{round_name}_{match_number}"
                result = bracket_results.get(match_key, {})
                
                if team1 and team2:
                    if result.get('completed'):
                        winner = result.get('winner')
                        is_playable = False
                    else:
                        winner = None
                        is_playable = True
                    is_placeholder = False
                else:
                    winner = None
                    is_playable = False
                    is_placeholder = True
                    w_round_num = winners_round_idx + 1
                    team1 = team1 or f'Loser SW{w_round_num}-M{i+1}'
                    team2 = team2 or f'Winner SL{round_idx}-M{i+1}'
                
                match_data = {
                    'teams': (team1, team2),
                    'round': round_name,
                    'match_number': match_number,
                    'match_code': f"SL{round_idx + 1}-M{match_number}",
                    'is_placeholder': is_placeholder,
                    'is_playable': is_playable,
                    'winner': winner,
                    'result': result if result else None
                }
                round_matches.append(match_data)
                
                if winner:
                    losers_match_winners[f"{round_name}_{match_number}"] = winner
        
        else:
            # Minor round - only losers bracket teams compete
            prev_round = losers_round_names[round_idx - 1] if round_idx > 0 else None
            prev_matches = losers_bracket.get(prev_round, []) if prev_round else []
            
            # Get winners from previous round
            prev_winners = [m.get('winner') for m in prev_matches]
            
            num_matches = max(1, len(prev_matches) // 2)
            
            for i in range(num_matches):
                team1 = prev_winners[i * 2] if i * 2 < len(prev_winners) and prev_winners[i * 2] else None
                team2 = prev_winners[i * 2 + 1] if i * 2 + 1 < len(prev_winners) and prev_winners[i * 2 + 1] else None
                
                match_number = i + 1
                match_key = f"silver_losers_{round_name}_{match_number}"
                result = bracket_results.get(match_key, {})
                
                if team1 and team2:
                    if result.get('completed'):
                        winner = result.get('winner')
                        is_playable = False
                    else:
                        winner = None
                        is_playable = True
                    is_placeholder = False
                else:
                    winner = None
                    is_playable = False
                    is_placeholder = True
                    prev_round_num = round_idx
                    team1 = team1 or f'Winner SL{prev_round_num}-M{i*2+1}'
                    team2 = team2 or f'Winner SL{prev_round_num}-M{i*2+2}'
                
                match_data = {
                    'teams': (team1, team2),
                    'round': round_name,
                    'match_number': match_number,
                    'match_code': f"SL{round_idx + 1}-M{match_number}",
                    'is_placeholder': is_placeholder,
                    'is_playable': is_playable,
                    'winner': winner,
                    'result': result if result else None
                }
                round_matches.append(match_data)
                
                if winner:
                    losers_match_winners[f"{round_name}_{match_number}"] = winner
        
        losers_bracket[round_name] = round_matches
    
    # Grand Final
    winners_champion = None
    if winners_round_names:
        final_round = winners_round_names[-1]
        if final_round in winners_bracket and winners_bracket[final_round]:
            winners_champion = winners_bracket[final_round][0].get('winner')
    
    losers_champion = None
    if losers_round_names:
        final_losers_round = losers_round_names[-1]
        if final_losers_round in losers_bracket and losers_bracket[final_losers_round]:
            losers_champion = losers_bracket[final_losers_round][0].get('winner')
    
    gf_match_key = "silver_grand_final_Grand Final_1"
    gf_result = bracket_results.get(gf_match_key, {})
    
    if winners_champion and losers_champion:
        gf_teams = (winners_champion, losers_champion)
        gf_is_placeholder = False
        if gf_result.get('completed'):
            gf_winner = gf_result.get('winner')
            gf_is_playable = False
        else:
            gf_winner = None
            gf_is_playable = True
    else:
        gf_winner = None
        gf_is_playable = False
        gf_is_placeholder = True
        gf_teams = (winners_champion or 'Winners Champion', losers_champion or 'Losers Champion')
    
    grand_final = {
        'teams': gf_teams,
        'round': 'Grand Final',
        'match_number': 1,
        'match_code': 'SGF',
        'is_placeholder': gf_is_placeholder,
        'is_playable': gf_is_playable,
        'winner': gf_winner,
        'result': gf_result if gf_result else None
    }
    
    # Bracket Reset
    br_match_key = "silver_bracket_reset_Bracket Reset_1"
    br_result = bracket_results.get(br_match_key, {})
    needs_reset = gf_winner and gf_winner == losers_champion
    
    if needs_reset:
        br_teams = (winners_champion, losers_champion)
        br_is_placeholder = False
        if br_result.get('completed'):
            br_winner = br_result.get('winner')
            br_is_playable = False
        else:
            br_winner = None
            br_is_playable = True
    else:
        br_winner = None
        br_is_playable = False
        br_is_placeholder = True
        br_teams = ('Grand Final Winner', 'Grand Final Loser')
    
    bracket_reset = {
        'teams': br_teams,
        'round': 'Bracket Reset',
        'match_number': 1,
        'match_code': 'SBR',
        'is_placeholder': br_is_placeholder,
        'is_conditional': True,
        'is_playable': br_is_playable,
        'winner': br_winner,
        'result': br_result if br_result else None,
        'needs_reset': needs_reset
    }
    
    # Determine champion
    champion = None
    if br_result.get('completed'):
        champion = br_result.get('winner')
    elif gf_winner and gf_winner == winners_champion:
        champion = winners_champion
    
    total_teams = len(seeded_teams)
    byes = calculate_byes(total_teams)
    
    first_round_byes = 0
    first_round_name = get_winners_round_name(bracket_size, bracket_size)
    if first_round_name in winners_bracket:
        first_round_byes = sum(1 for m in winners_bracket[first_round_name] if m.get('is_bye', False))
    
    return {
        'seeded_teams': seeded_teams,
        'winners_bracket': winners_bracket,
        'losers_bracket': losers_bracket,
        'grand_final': grand_final,
        'bracket_reset': bracket_reset,
        'bracket_size': bracket_size,
        'total_winners_rounds': total_winners_rounds,
        'total_losers_rounds': total_losers_rounds,
        'total_teams': total_teams,
        'byes': first_round_byes,
        'champion': champion
    }


def generate_bracket_execution_order(pools: Dict[str, Dict], standings: Optional[Dict] = None, 
                                      prefix: str = "", phase_name: str = "Bracket") -> List[Dict]:
    """
    Generate bracket matches in the correct execution order.
    
    For a double elimination bracket, the execution order is:
    - All Winners R1 matches first (can be played in parallel)
    - Losers R1 (minor round - W1 losers pair up) - AFTER W1 completes
    - Winners R2 - can start after W1 finishes producing teams
    - Losers R2 (major round - W2 losers drop in) - AFTER W2 AND L1 complete
    - Winners R3
    - Losers R3 (minor round)
    - Losers R4 (major round - W3 loser drops in)
    - Grand Final
    - Bracket Reset (conditional)
    
    Args:
        pools: Pool configuration
        standings: Pool standings
        prefix: Match code prefix ("" for Gold, "S" for Silver)
        phase_name: Phase name for display ("Bracket" or "Silver Bracket")
    
    Returns:
        List of matches in execution order, each with:
        - match_code, teams, round, phase, time_slot (relative ordering)
    """
    bracket_data = generate_double_elimination_bracket(pools, standings, prefix)
    
    if not bracket_data['seeded_teams']:
        return []
    
    matches_in_order = []
    time_slot = 0
    
    total_winners_rounds = bracket_data['total_winners_rounds']
    total_losers_rounds = bracket_data['total_losers_rounds']
    
    # Build lookup for winners and losers brackets by round index
    winners_by_round = {}
    for round_name, round_matches in bracket_data['winners_bracket'].items():
        # Extract round number from round name
        for match in round_matches:
            code = match.get('match_code', '')
            if code.startswith(prefix + 'W'):
                # Extract round number from W1-M1 format
                round_idx = int(code[len(prefix)+1:code.index('-')]) - 1
                if round_idx not in winners_by_round:
                    winners_by_round[round_idx] = []
                winners_by_round[round_idx].append((match, round_name))
    
    losers_by_round = {}
    for round_name, round_matches in bracket_data['losers_bracket'].items():
        for match in round_matches:
            code = match.get('match_code', '')
            if code.startswith(prefix + 'L'):
                round_idx = int(code[len(prefix)+1:code.index('-')]) - 1
                if round_idx not in losers_by_round:
                    losers_by_round[round_idx] = []
                losers_by_round[round_idx].append((match, round_name))
    
    # Generate execution order:
    # The interleaving pattern for an 8-team bracket (3 winners rounds, 4 losers rounds):
    # W1 (all matches) -> L1 -> W2 -> L2 -> W3 -> L3 -> L4 -> GF -> BR
    #
    # General pattern:
    # W1 -> L1 -> W2 -> L2 -> W3 -> L3 -> L4 -> ... -> GF -> BR
    # 
    # Winners R(i) produces losers for Losers R(2*i-1) or R(2*i) depending on odd/even
    # L1 is minor (0), L2 is major (1), L3 is minor (2), L4 is major (3)
    
    w_round = 0
    l_round = 0
    
    # First: all W1 matches (time slot 0)
    if 0 in winners_by_round:
        for match, round_name in winners_by_round[0]:
            if not match.get('is_bye', False):
                matches_in_order.append({
                    'match_code': match.get('match_code', ''),
                    'teams': list(match['teams']),
                    'round': round_name,
                    'phase': phase_name,
                    'time_slot': time_slot,
                    'is_placeholder': match.get('is_placeholder', False),
                    'is_bye': match.get('is_bye', False)
                })
        time_slot += 1
        w_round = 1
    
    # Now alternate: L(odd), W(next), L(even), ...
    # L1 (minor) can start after W1 completes
    # W2 can start after W1 (some parallelism possible, but for simplicity sequential)
    # L2 (major) can start after both W2 and L1 complete
    # etc.
    
    while l_round < total_losers_rounds or w_round < total_winners_rounds:
        # Add L(l_round) if it exists
        if l_round < total_losers_rounds and l_round in losers_by_round:
            for match, round_name in losers_by_round[l_round]:
                matches_in_order.append({
                    'match_code': match.get('match_code', ''),
                    'teams': list(match['teams']),
                    'round': round_name,
                    'phase': phase_name,
                    'time_slot': time_slot,
                    'is_placeholder': match.get('is_placeholder', True),
                    'is_bye': False
                })
            time_slot += 1
            l_round += 1
        
        # Add W(w_round) if it exists (skip W1 which is already done)
        if w_round > 0 and w_round < total_winners_rounds and w_round in winners_by_round:
            for match, round_name in winners_by_round[w_round]:
                if not match.get('is_bye', False):
                    matches_in_order.append({
                        'match_code': match.get('match_code', ''),
                        'teams': list(match['teams']),
                        'round': round_name,
                        'phase': phase_name,
                        'time_slot': time_slot,
                        'is_placeholder': match.get('is_placeholder', True),
                        'is_bye': False
                    })
            time_slot += 1
            w_round += 1
        elif w_round == 0:
            w_round = 1  # Skip to 1 since W1 is already processed
    
    # Grand Final
    if bracket_data['grand_final']:
        gf = bracket_data['grand_final']
        matches_in_order.append({
            'match_code': gf.get('match_code', f'{prefix}GF'),
            'teams': list(gf['teams']),
            'round': 'Grand Final',
            'phase': phase_name,
            'time_slot': time_slot,
            'is_placeholder': True,
            'is_bye': False
        })
        time_slot += 1
    
    # Bracket Reset (conditional)
    if bracket_data['bracket_reset']:
        br = bracket_data['bracket_reset']
        matches_in_order.append({
            'match_code': br.get('match_code', f'{prefix}BR'),
            'teams': list(br['teams']),
            'round': 'Bracket Reset',
            'phase': phase_name,
            'time_slot': time_slot,
            'is_placeholder': True,
            'is_bye': False,
            'is_conditional': True
        })
    
    return matches_in_order


def generate_silver_bracket_execution_order(pools: Dict[str, Dict], standings: Optional[Dict] = None) -> List[Dict]:
    """
    Generate Silver bracket matches in the correct execution order.
    Similar to generate_bracket_execution_order but uses Silver teams (3rd/4th place finishers).
    
    Args:
        pools: Pool configuration
        standings: Pool standings
    
    Returns:
        List of matches in execution order for Silver bracket
    """
    seeded_teams = seed_silver_bracket_teams(pools, standings)
    
    if len(seeded_teams) < 2:
        return []
    
    bracket_size = calculate_bracket_size(len(seeded_teams))
    total_winners_rounds = int(math.log2(bracket_size))
    total_losers_rounds = calculate_losers_bracket_rounds(bracket_size)
    
    # Generate brackets with "S" prefix for Silver
    winners_bracket = _generate_winners_bracket(seeded_teams, bracket_size, total_winners_rounds, prefix="S")
    losers_bracket = _generate_losers_bracket(bracket_size, total_winners_rounds, total_losers_rounds, prefix="S")
    
    matches_in_order = []
    time_slot = 0
    phase_name = "Silver Bracket"
    prefix = "S"
    
    # Build lookup for winners and losers brackets by round index
    winners_by_round = {}
    for round_name, round_matches in winners_bracket.items():
        for match in round_matches:
            code = match.get('match_code', '')
            if code.startswith('SW'):
                round_idx = int(code[2:code.index('-')]) - 1
                if round_idx not in winners_by_round:
                    winners_by_round[round_idx] = []
                winners_by_round[round_idx].append((match, round_name))
    
    losers_by_round = {}
    for round_name, round_matches in losers_bracket.items():
        for match in round_matches:
            code = match.get('match_code', '')
            if code.startswith('SL'):
                round_idx = int(code[2:code.index('-')]) - 1
                if round_idx not in losers_by_round:
                    losers_by_round[round_idx] = []
                losers_by_round[round_idx].append((match, round_name))
    
    w_round = 0
    l_round = 0
    
    # First: all SW1 matches (time slot 0)
    if 0 in winners_by_round:
        for match, round_name in winners_by_round[0]:
            if not match.get('is_bye', False):
                matches_in_order.append({
                    'match_code': match.get('match_code', ''),
                    'teams': list(match['teams']),
                    'round': f"Silver {round_name}",
                    'phase': phase_name,
                    'time_slot': time_slot,
                    'is_placeholder': match.get('is_placeholder', False),
                    'is_bye': match.get('is_bye', False)
                })
        time_slot += 1
        w_round = 1
    
    # Interleave winners and losers rounds
    while l_round < total_losers_rounds or w_round < total_winners_rounds:
        if l_round < total_losers_rounds and l_round in losers_by_round:
            for match, round_name in losers_by_round[l_round]:
                matches_in_order.append({
                    'match_code': match.get('match_code', ''),
                    'teams': list(match['teams']),
                    'round': f"Silver {round_name}",
                    'phase': phase_name,
                    'time_slot': time_slot,
                    'is_placeholder': True,
                    'is_bye': False
                })
            time_slot += 1
            l_round += 1
        
        if w_round > 0 and w_round < total_winners_rounds and w_round in winners_by_round:
            for match, round_name in winners_by_round[w_round]:
                if not match.get('is_bye', False):
                    matches_in_order.append({
                        'match_code': match.get('match_code', ''),
                        'teams': list(match['teams']),
                        'round': f"Silver {round_name}",
                        'phase': phase_name,
                        'time_slot': time_slot,
                        'is_placeholder': match.get('is_placeholder', True),
                        'is_bye': False
                    })
            time_slot += 1
            w_round += 1
        elif w_round == 0:
            w_round = 1
    
    # Silver Grand Final
    matches_in_order.append({
        'match_code': 'SGF',
        'teams': ['Winner of SWinners Bracket', 'Winner of SLosers Bracket'],
        'round': 'Silver Grand Final',
        'phase': phase_name,
        'time_slot': time_slot,
        'is_placeholder': True,
        'is_bye': False
    })
    time_slot += 1
    
    # Silver Bracket Reset
    matches_in_order.append({
        'match_code': 'SBR',
        'teams': ['Winner SGF', 'Loser SGF'],
        'round': 'Silver Bracket Reset',
        'phase': phase_name,
        'time_slot': time_slot,
        'is_placeholder': True,
        'is_bye': False,
        'is_conditional': True
    })
    
    return matches_in_order
