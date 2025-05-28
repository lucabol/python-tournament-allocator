import yaml
import os
import json
from itertools import combinations
from core.models import Team

def load_teams(file_path):
    teams = []
    with open(file_path, mode='r', encoding='utf-8') as file:
        pools_data = yaml.safe_load(file)
        for pool_name, team_names in pools_data.items():
            for team_name in team_names:
                teams.append(Team(name=team_name, attributes={'pool': pool_name}))
    return teams

def generate_pool_play_matches(teams):
    matches = []
    teams_dict = {team.name: team for team in teams}
    pools = {}
    
    # Group teams by pool
    for team in teams:
        pool_name = team.attributes['pool']
        if pool_name not in pools:
            pools[pool_name] = []
        pools[pool_name].append(team.name)

    # Generate matches for each pool
    for pool_name, team_names_in_pool in pools.items():
        valid_teams_in_pool = [name for name in team_names_in_pool if name in teams_dict]
        if len(valid_teams_in_pool) < 2:
            print(f"Warning: Pool {pool_name} has fewer than 2 valid teams ({len(valid_teams_in_pool)} found: {valid_teams_in_pool}). Skipping match generation.")
            continue
        for team1_name, team2_name in combinations(valid_teams_in_pool, 2):
            matches.append({
                "teams": [team1_name, team2_name],
                "pool": pool_name
            })
    return matches

def main():
    import sys
    
    script_dir = os.path.dirname(__file__)
    base_dir = os.path.dirname(script_dir)
    
    # Use command line argument if provided, otherwise use default path
    teams_file = sys.argv[1] if len(sys.argv) > 1 else os.path.join(base_dir, 'data', 'teams.yaml')

    teams = load_teams(teams_file)

    if not teams:
        return

    matches = generate_pool_play_matches(teams)
    
    if matches:
        # Group matches by pool
        matches_by_pool = {}
        for match in matches:
            pool = match["pool"]
            if pool not in matches_by_pool:
                matches_by_pool[pool] = []
            matches_by_pool[pool].append(match)
          # Print matches in the specified format
        first_pool = True
        for pool, pool_matches in sorted(matches_by_pool.items()):
            if not first_pool:
                print()  # Add newline before each pool except the first one
            print(f"# Pool {pool}")
            for match in pool_matches:
                team1, team2 = match["teams"]
                print(f"{team1} vs {team2}")
            first_pool = False

if __name__ == '__main__':
    main()
