"""
Single elimination bracket generation and management.
"""
import math
from typing import List, Dict, Tuple, Optional


def get_round_name(teams_in_round: int, total_teams: int) -> str:
    """Get the name of a round based on number of teams."""
    if teams_in_round == 2:
        return "Final"
    elif teams_in_round == 4:
        return "Semifinal"
    elif teams_in_round == 8:
        return "Quarterfinal"
    elif teams_in_round == 16:
        return "Round of 16"
    elif teams_in_round == 32:
        return "Round of 32"
    elif teams_in_round == 64:
        return "Round of 64"
    else:
        return f"Round of {teams_in_round}"


def calculate_bracket_size(num_teams: int) -> int:
    """Calculate the bracket size (next power of 2)."""
    if num_teams <= 0:
        return 0
    return 2 ** math.ceil(math.log2(num_teams))


def calculate_byes(num_teams: int) -> int:
    """Calculate number of byes needed."""
    bracket_size = calculate_bracket_size(num_teams)
    return bracket_size - num_teams


def seed_teams_from_pools(pools: Dict[str, Dict], standings: Optional[Dict] = None) -> List[Tuple[str, int, str]]:
    """
    Create seeded list of teams advancing from pools.
    Returns list of (team_name, seed, pool_name) tuples.
    
    Seeding is done by pool finish position:
    - All 1st place finishers get top seeds
    - All 2nd place finishers get next seeds
    - etc.
    
    If standings are provided, uses actual team names from standings.
    Otherwise, uses placeholder teams.
    """
    seeded_teams = []
    
    # Get max advance count to determine how many positions we need
    if not pools:
        return seeded_teams
    
    max_advance = max(pool_data.get('advance', 2) for pool_data in pools.values())
    pool_names = sorted(pools.keys())
    
    seed = 1
    # For each finishing position (1st, 2nd, etc.)
    for position in range(1, max_advance + 1):
        # Gather all teams at this position across pools
        teams_at_position = []
        for pool_name in pool_names:
            pool_data = pools[pool_name]
            advance_count = pool_data.get('advance', 2)
            if position <= advance_count:
                team_name = f"#{position} {pool_name}"
                team_stats = None
                # Use actual team name from standings only if the team has played games
                if standings and pool_name in standings:
                    pool_standings = standings[pool_name]
                    if len(pool_standings) >= position:
                        team_data = pool_standings[position - 1]
                        # Only use actual name if team has played at least one match
                        if team_data.get('matches_played', 0) > 0:
                            team_name = team_data['team']
                            team_stats = team_data
                
                teams_at_position.append((team_name, pool_name, team_stats))
        
        # Sort by pool name only — cross-pool ordering must be deterministic
        # and match the schedule (generated before standings exist).
        # Within-pool ordering is handled by calculate_pool_standings.
        teams_at_position.sort(key=lambda t: t[1])
        
        for team_name, pool_name, _ in teams_at_position:
            seeded_teams.append((team_name, seed, pool_name))
            seed += 1
    
    return seeded_teams


def seed_silver_bracket_teams(pools: Dict[str, Dict], standings: Optional[Dict] = None) -> List[Tuple[str, int, str]]:
    """
    Create seeded list of teams NOT advancing from pools (for Silver Bracket).
    Returns list of (team_name, seed, pool_name) tuples.
    
    Seeding is done by pool finish position (starting after advance count):
    - All teams in position (advance+1) get top seeds
    - All teams in position (advance+2) get next seeds
    - etc.
    """
    seeded_teams = []
    
    if not pools:
        return seeded_teams
    
    pool_names = sorted(pools.keys())
    
    # Find max team count in any pool to determine how many positions we need
    max_teams_in_pool = 0
    for pool_name in pool_names:
        pool_data = pools[pool_name]
        num_teams = len(pool_data.get('teams', []))
        max_teams_in_pool = max(max_teams_in_pool, num_teams)
    
    seed = 1
    # For each finishing position starting after advance count
    for position in range(1, max_teams_in_pool + 1):
        # Gather all teams at this position across pools
        teams_at_position = []
        for pool_name in pool_names:
            pool_data = pools[pool_name]
            advance_count = pool_data.get('advance', 2)
            num_teams = len(pool_data.get('teams', []))
            
            # Only include teams that don't advance (position > advance_count)
            if position > advance_count and position <= num_teams:
                team_name = f"#{position} {pool_name}"
                team_stats = None
                # Use actual team name from standings only if the team has played games
                if standings and pool_name in standings:
                    pool_standings = standings[pool_name]
                    if len(pool_standings) >= position:
                        team_data = pool_standings[position - 1]
                        if team_data.get('matches_played', 0) > 0:
                            team_name = team_data['team']
                            team_stats = team_data
                
                teams_at_position.append((team_name, pool_name, team_stats))
        
        # Sort by pool name only — cross-pool ordering must be deterministic
        # and match the schedule (generated before standings exist).
        teams_at_position.sort(key=lambda t: t[1])
        
        for team_name, pool_name, _ in teams_at_position:
            seeded_teams.append((team_name, seed, pool_name))
            seed += 1
    
    return seeded_teams


def create_bracket_matchups(seeded_teams: List[Tuple[str, int, str]]) -> List[Dict]:
    """
    Create first round matchups for single elimination bracket.
    Uses standard bracket seeding (1 vs 16, 8 vs 9, etc.)
    
    Returns list of match dicts with:
    - teams: tuple of (team1, team2) or (team1, 'BYE')
    - round: round name
    - match_number: position in bracket
    - seeds: tuple of seed numbers
    """
    num_teams = len(seeded_teams)
    if num_teams < 2:
        return []
    
    bracket_size = calculate_bracket_size(num_teams)
    num_byes = calculate_byes(num_teams)
    
    # Create seed-to-team mapping
    seed_to_team = {seed: team for team, seed, _ in seeded_teams}
    
    # Standard bracket positions for first round
    # For a bracket of N teams, seed 1 plays seed N, seed 2 plays seed N-1, etc.
    # But they're arranged so winners meet in proper order
    matchups = []
    
    # Generate bracket order (standard tournament seeding)
    bracket_order = _generate_bracket_order(bracket_size)
    
    round_name = get_round_name(bracket_size, bracket_size)
    match_number = 1
    
    for i in range(0, len(bracket_order), 2):
        seed1 = bracket_order[i]
        seed2 = bracket_order[i + 1]
        
        team1 = seed_to_team.get(seed1)
        team2 = seed_to_team.get(seed2)
        
        # Handle byes - higher seed gets bye
        if team1 is None and team2 is None:
            continue  # Skip empty matchup
        elif team2 is None:
            # team1 gets a bye
            matchups.append({
                'teams': (team1, 'BYE'),
                'round': round_name,
                'match_number': match_number,
                'seeds': (seed1, seed2),
                'is_bye': True
            })
        elif team1 is None:
            # team2 gets a bye (shouldn't happen with proper seeding)
            matchups.append({
                'teams': ('BYE', team2),
                'round': round_name,
                'match_number': match_number,
                'seeds': (seed1, seed2),
                'is_bye': True
            })
        else:
            matchups.append({
                'teams': (team1, team2),
                'round': round_name,
                'match_number': match_number,
                'seeds': (seed1, seed2),
                'is_bye': False
            })
        
        match_number += 1
    
    return matchups


def _generate_bracket_order(bracket_size: int) -> List[int]:
    """
    Generate the standard tournament bracket order.
    This ensures that if all higher seeds win, they meet in the proper rounds.
    
    For 8 teams: [1, 8, 4, 5, 2, 7, 3, 6]
    This gives matchups: 1v8, 4v5, 2v7, 3v6
    Winners: 1v4 side, 2v3 side
    Final: 1v2 (if chalk)
    """
    if bracket_size == 2:
        return [1, 2]
    
    # Recursive generation
    half_size = bracket_size // 2
    upper_half = _generate_bracket_order(half_size)
    
    # Create lower half as complement
    lower_half = [bracket_size + 1 - seed for seed in upper_half]
    
    # Interleave: pair each upper seed with its complement
    result = []
    for u, l in zip(upper_half, lower_half):
        result.extend([u, l])
    
    return result


def generate_elimination_rounds(pools: Dict[str, Dict], standings: Optional[Dict] = None) -> Dict[str, List[Dict]]:
    """
    Generate all elimination round matches based on pools configuration.
    
    Returns dict with:
    - 'seeded_teams': list of (team, seed, pool) tuples
    - 'rounds': dict of round_name -> list of matches
    - 'bracket_size': total bracket size
    - 'total_rounds': number of rounds
    """
    seeded_teams = seed_teams_from_pools(pools, standings)
    
    if len(seeded_teams) < 2:
        return {
            'seeded_teams': seeded_teams,
            'rounds': {},
            'bracket_size': 0,
            'total_rounds': 0
        }
    
    bracket_size = calculate_bracket_size(len(seeded_teams))
    total_rounds = int(math.log2(bracket_size))
    
    # Generate first round matchups
    first_round_matches = create_bracket_matchups(seeded_teams)
    
    # Organize matches by round
    rounds = {}
    current_round_matches = first_round_matches
    current_teams_count = bracket_size
    
    for round_num in range(total_rounds):
        round_name = get_round_name(current_teams_count, bracket_size)
        
        if round_num == 0:
            rounds[round_name] = current_round_matches
        else:
            # Generate placeholder matches for subsequent rounds
            num_matches = current_teams_count // 2
            round_matches = []
            for i in range(num_matches):
                round_matches.append({
                    'teams': (f'Winner M{i*2+1}', f'Winner M{i*2+2}'),
                    'round': round_name,
                    'match_number': i + 1,
                    'seeds': None,
                    'is_bye': False,
                    'is_placeholder': True
                })
            rounds[round_name] = round_matches
        
        current_teams_count //= 2
    
    return {
        'seeded_teams': seeded_teams,
        'rounds': rounds,
        'bracket_size': bracket_size,
        'total_rounds': total_rounds
    }


def generate_silver_elimination_rounds(pools: Dict[str, Dict], standings: Optional[Dict] = None) -> Dict[str, List[Dict]]:
    """
    Generate all silver bracket elimination rounds for non-advancing teams.
    
    Returns dict with same structure as generate_elimination_rounds.
    """
    seeded_teams = seed_silver_bracket_teams(pools, standings)
    
    if len(seeded_teams) < 2:
        return {
            'seeded_teams': seeded_teams,
            'rounds': {},
            'bracket_size': 0,
            'total_rounds': 0
        }
    
    bracket_size = calculate_bracket_size(len(seeded_teams))
    total_rounds = int(math.log2(bracket_size))
    
    # Generate first round matchups
    first_round_matches = create_bracket_matchups(seeded_teams)
    
    # Organize matches by round
    rounds = {}
    current_round_matches = first_round_matches
    current_teams_count = bracket_size
    
    for round_num in range(total_rounds):
        round_name = get_round_name(current_teams_count, bracket_size)
        
        if round_num == 0:
            rounds[round_name] = current_round_matches
        else:
            num_matches = current_teams_count // 2
            round_matches = []
            for i in range(num_matches):
                round_matches.append({
                    'teams': (f'Winner M{i*2+1}', f'Winner M{i*2+2}'),
                    'round': round_name,
                    'match_number': i + 1,
                    'seeds': None,
                    'is_bye': False,
                    'is_placeholder': True
                })
            rounds[round_name] = round_matches
        
        current_teams_count //= 2
    
    return {
        'seeded_teams': seeded_teams,
        'rounds': rounds,
        'bracket_size': bracket_size,
        'total_rounds': total_rounds
    }


def generate_silver_matches_for_scheduling(pools: Dict[str, Dict], standings: Optional[Dict] = None) -> List[Tuple[Tuple[str, str], str]]:
    """
    Generate silver bracket matches in format suitable for AllocationManager.
    Only returns first-round matches that need scheduling (non-byes).
    
    Returns list of ((team1, team2), "Silver " + round_name) tuples.
    """
    bracket_data = generate_silver_elimination_rounds(pools, standings)
    matches = []
    
    for round_name, round_matches in bracket_data['rounds'].items():
        for match in round_matches:
            if match.get('is_bye', False):
                continue
            if match.get('is_placeholder', False):
                continue
            
            team1, team2 = match['teams']
            # Prefix with "Silver " to distinguish from Gold bracket
            matches.append(((team1, team2), f"Silver {round_name}"))
    
    return matches


def generate_elimination_matches_for_scheduling(pools: Dict[str, Dict], standings: Optional[Dict] = None) -> List[Tuple[Tuple[str, str], str]]:
    """
    Generate elimination matches in format suitable for AllocationManager.
    Only returns first-round matches that need scheduling (non-byes).
    
    Returns list of ((team1, team2), round_name) tuples.
    """
    bracket_data = generate_elimination_rounds(pools, standings)
    matches = []
    
    for round_name, round_matches in bracket_data['rounds'].items():
        for match in round_matches:
            # Skip byes and placeholder matches
            if match.get('is_bye', False):
                continue
            if match.get('is_placeholder', False):
                continue
            
            team1, team2 = match['teams']
            matches.append(((team1, team2), round_name))
    
    return matches


def generate_all_single_bracket_matches_for_scheduling(pools: Dict[str, Dict], standings: Optional[Dict] = None, include_silver: bool = False) -> List[Dict]:
    """
    Generate ALL single elimination matches for scheduling, including placeholders.
    
    Returns list of match dicts with:
    - teams: [team1, team2] (may be placeholders)
    - round: round name
    - match_number: match number within round
    - phase: "Bracket" or "Silver Bracket"
    - is_placeholder: True if teams are not yet determined
    """
    bracket_data = generate_elimination_rounds(pools, standings)
    matches = []
    
    if not bracket_data['seeded_teams']:
        return matches
    
    # All rounds
    for round_name, round_matches in bracket_data['rounds'].items():
        for match in round_matches:
            if match.get('is_bye', False):
                continue
            matches.append({
                'teams': list(match['teams']),
                'round': round_name,
                'match_number': match.get('match_number', 0),
                'phase': 'Bracket',
                'is_placeholder': match.get('is_placeholder', False),
                'is_bye': False
            })
    
    # Silver bracket if enabled
    if include_silver:
        silver_bracket_data = generate_silver_elimination_rounds(pools, standings)
        if silver_bracket_data and silver_bracket_data.get('seeded_teams'):
            for round_name, round_matches in silver_bracket_data['rounds'].items():
                for match in round_matches:
                    if match.get('is_bye', False):
                        continue
                    matches.append({
                        'teams': list(match['teams']),
                        'round': f"Silver {round_name}",
                        'match_number': match.get('match_number', 0),
                        'phase': 'Silver Bracket',
                        'is_placeholder': match.get('is_placeholder', False),
                        'is_bye': False
                    })
    
    return matches


def get_elimination_bracket_display(pools: Dict[str, Dict], standings: Optional[Dict] = None) -> Dict:
    """
    Get bracket data formatted for UI display.
    """
    bracket_data = generate_elimination_rounds(pools, standings)
    
    # Calculate statistics
    total_teams = len(bracket_data['seeded_teams'])
    first_round_byes = sum(
        1 for m in bracket_data['rounds'].get(
            get_round_name(bracket_data['bracket_size'], bracket_data['bracket_size']), []
        ) if m.get('is_bye', False)
    )
    
    # Count actual matches (non-byes) per round
    matches_per_round = {}
    for round_name, matches in bracket_data['rounds'].items():
        actual_matches = [m for m in matches if not m.get('is_bye', False)]
        matches_per_round[round_name] = len(actual_matches)
    
    return {
        'seeded_teams': bracket_data['seeded_teams'],
        'rounds': bracket_data['rounds'],
        'bracket_size': bracket_data['bracket_size'],
        'total_rounds': bracket_data['total_rounds'],
        'total_teams': total_teams,
        'byes': first_round_byes,
        'matches_per_round': matches_per_round
    }


def generate_bracket_with_results(pools: Dict[str, Dict], standings: Optional[Dict] = None, 
                                   bracket_results: Optional[Dict] = None) -> Dict:
    """
    Generate bracket with results applied, advancing winners to subsequent rounds.
    
    Args:
        pools: Pool configuration
        standings: Pool standings with team placements
        bracket_results: Dict of match results keyed by "winners_round_match_number"
    
    Returns:
        Complete bracket data with results applied and winners advanced
    """
    if bracket_results is None:
        bracket_results = {}
    
    seeded_teams = seed_teams_from_pools(pools, standings)
    
    if len(seeded_teams) < 2:
        return {
            'seeded_teams': seeded_teams,
            'rounds': {},
            'bracket_size': 0,
            'total_rounds': 0,
            'total_teams': 0,
            'byes': 0,
            'matches_per_round': {}
        }
    
    bracket_size = calculate_bracket_size(len(seeded_teams))
    total_rounds = int(math.log2(bracket_size))
    
    # Create seed-to-team mapping
    seed_to_team = {seed: team for team, seed, _ in seeded_teams}
    
    # Generate bracket order for first round
    bracket_order = _generate_bracket_order(bracket_size)
    
    # Build rounds progressively, applying results
    rounds = {}
    round_names = []
    current_teams_count = bracket_size
    
    # Generate all round names first
    temp_count = bracket_size
    for _ in range(total_rounds):
        round_names.append(get_round_name(temp_count, bracket_size))
        temp_count //= 2
    
    # Track winners from each match to feed into next round
    # Key: "round_name_match_number" -> winner team name
    match_winners = {}
    
    for round_idx, round_name in enumerate(round_names):
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
                
                # Check for BYE
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
                
                # Check for result
                match_key = f"winners_{round_name}_{match_number}"
                match_code = f"W{round_idx + 1}-M{match_number}"
                # Dual-format lookup
                result = bracket_results.get(match_code) or bracket_results.get(match_key, {})
                
                # Determine winner
                if is_bye:
                    winner = bye_winner
                    is_playable = False
                elif result.get('completed'):
                    winner = result.get('winner')
                    is_playable = False
                else:
                    winner = None
                    is_playable = True  # Can be played if both teams are real and no result yet
                
                match_data = {
                    'teams': (actual_team1, actual_team2),
                    'round': round_name,
                    'match_number': match_number,
                    'match_code': match_code,
                    'seeds': (seed1, seed2),
                    'is_bye': is_bye,
                    'is_playable': is_playable,
                    'winner': winner,
                    'result': result if result else None
                }
                round_matches.append(match_data)
                
                # Store winner for next round
                if winner:
                    match_winners[f"{round_name}_{match_number}"] = winner
                
                match_number += 1
        else:
            # Subsequent rounds - get teams from previous round winners
            prev_round_name = round_names[round_idx - 1]
            
            for i in range(num_matches):
                prev_match1 = i * 2 + 1
                prev_match2 = i * 2 + 2
                
                # Get teams from previous round winners
                team1_key = f"{prev_round_name}_{prev_match1}"
                team2_key = f"{prev_round_name}_{prev_match2}"
                
                team1 = match_winners.get(team1_key)
                team2 = match_winners.get(team2_key)
                
                match_number = i + 1
                match_key = f"winners_{round_name}_{match_number}"
                match_code = f"W{round_idx + 1}-M{match_number}"
                # Dual-format lookup
                result = bracket_results.get(match_code) or bracket_results.get(match_key, {})
                
                # Determine if match is playable (both teams known and no result yet)
                if team1 and team2:
                    if result.get('completed'):
                        winner = result.get('winner')
                        is_playable = False
                    else:
                        winner = None
                        is_playable = True
                    is_placeholder = False
                else:
                    # Waiting for teams
                    winner = None
                    is_playable = False
                    is_placeholder = True
                    team1 = team1 or f'Winner M{prev_match1}'
                    team2 = team2 or f'Winner M{prev_match2}'
                
                match_data = {
                    'teams': (team1, team2),
                    'round': round_name,
                    'match_number': match_number,
                    'match_code': match_code,
                    'seeds': None,
                    'is_bye': False,
                    'is_placeholder': is_placeholder,
                    'is_playable': is_playable,
                    'winner': winner,
                    'result': result if result else None
                }
                round_matches.append(match_data)
                
                if winner:
                    match_winners[f"{round_name}_{match_number}"] = winner
        
        rounds[round_name] = round_matches
        current_teams_count //= 2
    
    # Calculate statistics
    total_teams = len(seeded_teams)
    first_round_name = get_round_name(bracket_size, bracket_size)
    first_round_byes = sum(1 for m in rounds.get(first_round_name, []) if m.get('is_bye', False))
    
    matches_per_round = {}
    for rn, matches in rounds.items():
        actual_matches = [m for m in matches if not m.get('is_bye', False)]
        matches_per_round[rn] = len(actual_matches)
    
    # Find champion
    final_round = round_names[-1] if round_names else None
    champion = None
    if final_round and rounds.get(final_round):
        final_match = rounds[final_round][0]
        champion = final_match.get('winner')
    
    return {
        'seeded_teams': seeded_teams,
        'rounds': rounds,
        'bracket_size': bracket_size,
        'total_rounds': total_rounds,
        'total_teams': total_teams,
        'byes': first_round_byes,
        'matches_per_round': matches_per_round,
        'champion': champion
    }


def generate_silver_bracket_with_results(pools: Dict[str, Dict], standings: Optional[Dict] = None, 
                                          bracket_results: Optional[Dict] = None) -> Optional[Dict]:
    """
    Generate silver bracket with results applied for teams that don't advance from pools.
    
    Args:
        pools: Pool configuration
        standings: Pool standings with team placements
        bracket_results: Dict of match results keyed by "silver_round_match_number"
    
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
    total_rounds = int(math.log2(bracket_size))
    
    # Create seed-to-team mapping
    seed_to_team = {seed: team for team, seed, _ in seeded_teams}
    
    # Generate bracket order for first round
    bracket_order = _generate_bracket_order(bracket_size)
    
    # Build rounds progressively, applying results
    rounds = {}
    round_names = []
    current_teams_count = bracket_size
    
    # Generate all round names first
    temp_count = bracket_size
    for _ in range(total_rounds):
        round_names.append(get_round_name(temp_count, bracket_size))
        temp_count //= 2
    
    # Track winners from each match
    match_winners = {}
    
    for round_idx, round_name in enumerate(round_names):
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
                
                # Check for BYE
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
                
                # Check for result - silver bracket uses "silver_" prefix
                match_key = f"silver_{round_name}_{match_number}"
                result = bracket_results.get(match_key, {})
                
                # Determine winner
                if is_bye:
                    winner = bye_winner
                    is_playable = False
                elif result.get('completed'):
                    winner = result.get('winner')
                    is_playable = False
                else:
                    winner = None
                    is_playable = True
                
                match_data = {
                    'teams': (actual_team1, actual_team2),
                    'round': round_name,
                    'match_number': match_number,
                    'seeds': (seed1, seed2),
                    'is_bye': is_bye,
                    'is_playable': is_playable,
                    'winner': winner,
                    'result': result if result else None
                }
                round_matches.append(match_data)
                
                if winner:
                    match_winners[f"{round_name}_{match_number}"] = winner
                
                match_number += 1
        else:
            # Subsequent rounds
            prev_round_name = round_names[round_idx - 1]
            
            for i in range(num_matches):
                prev_match1 = i * 2 + 1
                prev_match2 = i * 2 + 2
                
                team1_key = f"{prev_round_name}_{prev_match1}"
                team2_key = f"{prev_round_name}_{prev_match2}"
                
                team1 = match_winners.get(team1_key)
                team2 = match_winners.get(team2_key)
                
                match_number = i + 1
                match_key = f"silver_{round_name}_{match_number}"
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
                    team1 = team1 or f'Winner M{prev_match1}'
                    team2 = team2 or f'Winner M{prev_match2}'
                
                match_data = {
                    'teams': (team1, team2),
                    'round': round_name,
                    'match_number': match_number,
                    'seeds': None,
                    'is_bye': False,
                    'is_placeholder': is_placeholder,
                    'is_playable': is_playable,
                    'winner': winner,
                    'result': result if result else None
                }
                round_matches.append(match_data)
                
                if winner:
                    match_winners[f"{round_name}_{match_number}"] = winner
        
        rounds[round_name] = round_matches
        current_teams_count //= 2
    
    # Calculate statistics
    total_teams = len(seeded_teams)
    first_round_name = get_round_name(bracket_size, bracket_size)
    first_round_byes = sum(1 for m in rounds.get(first_round_name, []) if m.get('is_bye', False))
    
    matches_per_round = {}
    for rn, matches in rounds.items():
        actual_matches = [m for m in matches if not m.get('is_bye', False)]
        matches_per_round[rn] = len(actual_matches)
    
    # Find champion
    final_round = round_names[-1] if round_names else None
    champion = None
    if final_round and rounds.get(final_round):
        final_match = rounds[final_round][0]
        champion = final_match.get('winner')
    
    return {
        'seeded_teams': seeded_teams,
        'rounds': rounds,
        'bracket_size': bracket_size,
        'total_rounds': total_rounds,
        'total_teams': total_teams,
        'byes': first_round_byes,
        'matches_per_round': matches_per_round,
        'champion': champion
    }
