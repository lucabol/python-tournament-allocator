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


def generate_double_elimination_bracket(pools: Dict[str, Dict], standings: Optional[Dict] = None) -> Dict:
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
        
        # Determine teams for this round based on losers bracket structure
        has_dropdown = (round_idx % 2 == 0) and (round_idx > 0)
        
        if round_idx == 0:
            # First losers round - losers from winners round 1
            winners_round1_name = winners_round_names[0]
            winners_round1_matches = winners_bracket.get(winners_round1_name, [])
            
            # Pair up losers from adjacent winners matches
            losers_from_w1 = []
            for m in winners_round1_matches:
                if m.get('loser') and not m.get('is_bye'):
                    losers_from_w1.append(m['loser'])
            
            num_matches = len(losers_from_w1) // 2
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
                    team1 = team1 or f'L-W1M{i*2+1}'
                    team2 = team2 or f'L-W1M{i*2+2}'
                
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
        
        elif has_dropdown:
            # Dropdown round - losers from winners bracket join
            winners_round_idx = (round_idx // 2) + 1
            prev_losers_round = losers_round_names[round_idx - 1]
            
            # Get winners from previous losers round
            prev_losers = []
            for m in losers_bracket.get(prev_losers_round, []):
                if m.get('winner'):
                    prev_losers.append(m['winner'])
            
            # Get losers from corresponding winners round
            if winners_round_idx < len(winners_round_names):
                w_round = winners_round_names[winners_round_idx]
                w_losers = []
                for m in winners_bracket.get(w_round, []):
                    if m.get('loser'):
                        w_losers.append(m['loser'])
            else:
                w_losers = []
            
            num_matches = max(len(prev_losers), len(w_losers))
            for i in range(num_matches):
                team1 = w_losers[i] if i < len(w_losers) else None
                team2 = prev_losers[i] if i < len(prev_losers) else None
                
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
                    team1 = team1 or f'L-W{winners_round_idx+1}M{i+1}'
                    team2 = team2 or f'L{round_idx}M{i+1}'
                
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
            prev_winners = []
            for m in losers_bracket.get(prev_round, []):
                if m.get('winner'):
                    prev_winners.append(m['winner'])
            
            num_matches = len(prev_winners) // 2
            for i in range(num_matches):
                team1 = prev_winners[i * 2] if i * 2 < len(prev_winners) else None
                team2 = prev_winners[i * 2 + 1] if i * 2 + 1 < len(prev_winners) else None
                
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
                    team1 = team1 or f'L{round_idx}M{i*2+1}'
                    team2 = team2 or f'L{round_idx}M{i*2+2}'
                
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
