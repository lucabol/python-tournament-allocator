# Entry point of the application for tournament allocation

import csv
import yaml
from core.allocation import AllocationManager
from core.models import Team, Court
import os

def load_teams(file_path):
    teams = []
    with open(file_path, mode='r', encoding='utf-8') as file:
        pools_data = yaml.safe_load(file)
        for pool_name, team_names in pools_data.items():
            for team_name in team_names:
                teams.append(Team(name=team_name, attributes={'pool': pool_name}))
    return teams

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

def get_pools_from_teams(teams):
    pools = {}
    for team in teams:
        pool_name = team.attributes['pool']
        if pool_name not in pools:
            pools[pool_name] = []
        pools[pool_name].append(team.name)
    return pools

def main():
    script_dir = os.path.dirname(__file__)
    base_dir = os.path.dirname(script_dir)
    
    teams_file = os.path.join(base_dir, 'data', 'teams.yaml')
    courts_file = os.path.join(base_dir, 'data', 'courts.csv')
    constraints_file = os.path.join(base_dir, 'data', 'constraints.yaml')  # Changed extension to yaml

    teams = load_teams(teams_file)
    courts = load_courts(courts_file)
    constraints = load_constraints(constraints_file)

    if not teams:
        print("No teams loaded. Check data/teams.yaml")
        return
    if not courts:
        print("No courts loaded. Check data/courts.csv")
        return

    # Update tournament settings in constraints with pools from teams.yaml
    pools = get_pools_from_teams(teams)
    if 'tournament_settings' not in constraints:
        constraints['tournament_settings'] = {}
    constraints['tournament_settings']['type'] = 'pool_play'
    constraints['tournament_settings']['pools'] = pools

    allocation_manager = AllocationManager(teams, courts, constraints)
    allocation_manager.allocate_teams_to_courts()

    # Output results
    print("\n--- Final Schedule ---")
    schedule_output = allocation_manager.get_schedule_output()
    if schedule_output:
        for court_schedule in schedule_output:
            print(f"\nCourt: {court_schedule['court_name']}")
            if court_schedule['matches']:
                for match in court_schedule['matches']:
                    print(f"  {match['start_time']} - {match['end_time']}: {match['teams'][0]} vs {match['teams'][1]}")
            else:
                print("  No matches scheduled.")
    else:
        print("No schedule generated.")

if __name__ == '__main__':
    main()