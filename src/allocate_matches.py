import json
import csv
import yaml
import os
from core.allocation import AllocationManager
from core.models import Team, Court

def load_matches(file_path):
    with open(file_path, mode='r', encoding='utf-8') as file:
        data = json.load(file)
        matches = data.get('matches', [])
        
        # Convert matches back to the format expected by AllocationManager
        formatted_matches = []
        for match in matches:
            formatted_matches.append((tuple(match['teams']), match['pool']))
        return formatted_matches

def load_courts(file_path):
    courts = []
    with open(file_path, mode='r', encoding='utf-8') as file:
        reader = csv.DictReader(file)
        for row in reader:
            courts.append(Court(name=row['court_name'].strip(), start_time=row['start_time'].strip()))
    return courts

def load_constraints(file_path):
    with open(file_path, mode='r', encoding='utf-8') as file:
        return yaml.safe_load(file)

def create_teams_from_matches(matches):
    teams = set()
    pools = {}
    
    for match_teams, pool in matches:
        for team_name in match_teams:
            teams.add(team_name)
            if pool not in pools:
                pools[pool] = set()
            pools[pool].add(team_name)
    
    return [Team(name=team, attributes={'pool': next(pool for pool, teams in pools.items() if team in teams)}) 
            for team in teams]

def load_matches_from_stdin():
    import sys
    
    matches = []
    current_pool = None
    
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
            
        if line.startswith('#'):
            # Extract pool name from lines like "# Pool A"
            current_pool = line[7:] if line.startswith('# Pool ') else line[1:].strip()
        else:
            # Parse lines like "Team A vs Team B"
            if current_pool and ' vs ' in line:
                team1, team2 = [t.strip() for t in line.split(' vs ')]
                matches.append((tuple([team1, team2]), current_pool))
                
    return matches

def main():
    import sys
    script_dir = os.path.dirname(__file__)
    base_dir = os.path.dirname(script_dir)
    
    courts_file = os.path.join(base_dir, 'data', 'courts.csv')
    constraints_file = os.path.join(base_dir, 'data', 'constraints.yaml')

    matches = load_matches_from_stdin()
    courts = load_courts(courts_file)
    constraints = load_constraints(constraints_file)

    if not matches:
        print("No matches loaded from stdin. Make sure to pipe the output of generate_matches.py", file=sys.stderr)
        return
    if not courts:
        print("No courts loaded. Check data/courts.csv", file=sys.stderr)
        return

    # Create teams from matches data
    teams = create_teams_from_matches(matches)

    # Initialize the allocation manager
    allocation_manager = AllocationManager(teams, courts, constraints)
    
    # Override the pool play match generation with our pre-generated matches
    def custom_generate_matches(self):
        return matches
    allocation_manager._generate_pool_play_matches = lambda: matches

    # Allocate matches to courts
    allocation_manager.allocate_teams_to_courts()    # Get and print schedule
    schedule_output = allocation_manager.get_schedule_output()
    
    if schedule_output:
        for court_schedule in schedule_output:
            print(f"\nCourt: {court_schedule['court_name']}")
            if court_schedule['matches']:
                for match in court_schedule['matches']:
                    print(f"{match['start_time']} - {match['end_time']}: {match['teams'][0]} vs {match['teams'][1]}")
            else:
                print("No matches scheduled.")

if __name__ == '__main__':
    main()
