"""
Flask web application for Tournament Allocator.
"""
import os
import csv
import yaml
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from core.models import Team, Court
from core.allocation import AllocationManager
from generate_matches import generate_pool_play_matches

app = Flask(__name__)
app.secret_key = 'tournament-allocator-secret-key'

# Paths to data files
BASE_DIR = os.path.dirname(os.path.dirname(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')
TEAMS_FILE = os.path.join(DATA_DIR, 'teams.yaml')
COURTS_FILE = os.path.join(DATA_DIR, 'courts.csv')
CONSTRAINTS_FILE = os.path.join(DATA_DIR, 'constraints.yaml')


def load_teams():
    """Load teams from YAML file."""
    if not os.path.exists(TEAMS_FILE):
        return {}
    with open(TEAMS_FILE, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
        return data if data else {}


def save_teams(pools_data):
    """Save teams to YAML file."""
    with open(TEAMS_FILE, 'w', encoding='utf-8') as f:
        yaml.dump(pools_data, f, default_flow_style=False)


def load_courts():
    """Load courts from CSV file."""
    courts = []
    if not os.path.exists(COURTS_FILE):
        return courts
    with open(COURTS_FILE, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            courts.append({
                'name': row['court_name'].strip(),
                'start_time': row['start_time'].strip(),
                'end_time': row.get('end_time', '22:00').strip()
            })
    return courts


def save_courts(courts):
    """Save courts to CSV file."""
    with open(COURTS_FILE, 'w', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f, fieldnames=['court_name', 'start_time', 'end_time'])
        writer.writeheader()
        for court in courts:
            writer.writerow({
                'court_name': court['name'],
                'start_time': court['start_time'],
                'end_time': court.get('end_time', '22:00')
            })


def load_constraints():
    """Load constraints from YAML file."""
    if not os.path.exists(CONSTRAINTS_FILE):
        return get_default_constraints()
    with open(CONSTRAINTS_FILE, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
        return data if data else get_default_constraints()


def save_constraints(constraints):
    """Save constraints to YAML file."""
    with open(CONSTRAINTS_FILE, 'w', encoding='utf-8') as f:
        yaml.dump(constraints, f, default_flow_style=False)


def get_default_constraints():
    """Return default constraints."""
    return {
        'match_duration_minutes': 60,
        'days_number': 1,
        'min_break_between_matches_minutes': 15,
        'time_slot_increment_minutes': 15,
        'day_end_time_limit': '22:00',
        'team_specific_constraints': [],
        'general_constraints': [],
        'tournament_settings': {
            'type': 'pool_play',
            'advancement_rules': {
                'top_teams_per_pool_to_advance': 2
            }
        }
    }


@app.route('/')
def index():
    """Main page showing tournament overview."""
    pools = load_teams()
    courts = load_courts()
    constraints = load_constraints()
    
    # Count teams
    total_teams = sum(len(teams) for teams in pools.values()) if pools else 0
    
    return render_template('index.html', 
                         pools=pools,
                         courts=courts,
                         constraints=constraints,
                         total_teams=total_teams)


@app.route('/teams', methods=['GET', 'POST'])
def teams():
    """Teams management page."""
    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'add_pool':
            pool_name = request.form.get('pool_name', '').strip()
            if pool_name:
                pools = load_teams()
                if pool_name in pools:
                    flash(f'Pool "{pool_name}" already exists.', 'error')
                else:
                    pools[pool_name] = []
                    save_teams(pools)
        
        elif action == 'delete_pool':
            pool_name = request.form.get('pool_name')
            pools = load_teams()
            if pool_name in pools:
                del pools[pool_name]
                save_teams(pools)
        
        elif action == 'add_team':
            pool_name = request.form.get('pool_name')
            team_name = request.form.get('team_name', '').strip()
            if pool_name and team_name:
                pools = load_teams()
                # Check if team exists in any pool
                all_teams = {}
                for p_name, teams_in_pool in pools.items():
                    for t in teams_in_pool:
                        all_teams[t] = p_name
                
                if team_name in all_teams:
                    flash(f'Team "{team_name}" already exists in {all_teams[team_name]}.', 'error')
                elif pool_name in pools:
                    pools[pool_name].append(team_name)
                    save_teams(pools)
        
        elif action == 'delete_team':
            pool_name = request.form.get('pool_name')
            team_name = request.form.get('team_name')
            pools = load_teams()
            if pool_name in pools and team_name in pools[pool_name]:
                pools[pool_name].remove(team_name)
                save_teams(pools)
        
        return redirect(url_for('teams'))
    
    pools = load_teams()
    return render_template('teams.html', pools=pools)


@app.route('/courts', methods=['GET', 'POST'])
def courts():
    """Courts management page."""
    if request.method == 'POST':
        action = request.form.get('action')
        courts_list = load_courts()
        
        if action == 'add_court':
            court_name = request.form.get('court_name', '').strip()
            start_time = request.form.get('start_time', '08:00').strip()
            end_time = request.form.get('end_time', '22:00').strip()
            if court_name:
                courts_list.append({
                    'name': court_name,
                    'start_time': start_time,
                    'end_time': end_time
                })
                save_courts(courts_list)
        
        elif action == 'delete_court':
            court_name = request.form.get('court_name')
            courts_list = [c for c in courts_list if c['name'] != court_name]
            save_courts(courts_list)
        
        return redirect(url_for('courts'))
    
    courts_list = load_courts()
    return render_template('courts.html', courts=courts_list)


@app.route('/constraints', methods=['GET', 'POST'])
def constraints():
    """Constraints management page."""
    if request.method == 'POST':
        action = request.form.get('action')
        constraints_data = load_constraints()
        
        if action == 'update_general':
            constraints_data['match_duration_minutes'] = int(request.form.get('match_duration', 60))
            constraints_data['days_number'] = int(request.form.get('days_number', 1))
            constraints_data['min_break_between_matches_minutes'] = int(request.form.get('min_break', 15))
            constraints_data['time_slot_increment_minutes'] = int(request.form.get('time_increment', 15))
            constraints_data['day_end_time_limit'] = request.form.get('day_end_time', '22:00')
            save_constraints(constraints_data)
        
        elif action == 'add_team_constraint':
            team_name = request.form.get('team_name', '').strip()
            play_after = request.form.get('play_after', '').strip()
            play_before = request.form.get('play_before', '').strip()
            note = request.form.get('note', '').strip()
            
            if team_name:
                constraint = {'team_name': team_name}
                if play_after:
                    constraint['play_after'] = play_after
                if play_before:
                    constraint['play_before'] = play_before
                if note:
                    constraint['note'] = note
                
                if 'team_specific_constraints' not in constraints_data:
                    constraints_data['team_specific_constraints'] = []
                
                # Remove existing constraint for this team
                constraints_data['team_specific_constraints'] = [
                    c for c in constraints_data['team_specific_constraints']
                    if c.get('team_name') != team_name
                ]
                constraints_data['team_specific_constraints'].append(constraint)
                save_constraints(constraints_data)
        
        elif action == 'delete_team_constraint':
            team_name = request.form.get('team_name')
            if 'team_specific_constraints' in constraints_data:
                constraints_data['team_specific_constraints'] = [
                    c for c in constraints_data['team_specific_constraints']
                    if c.get('team_name') != team_name
                ]
                save_constraints(constraints_data)
        
        return redirect(url_for('constraints'))
    
    constraints_data = load_constraints()
    pools = load_teams()
    all_teams = []
    for pool_teams in pools.values():
        all_teams.extend(pool_teams)
    
    return render_template('constraints.html', constraints=constraints_data, all_teams=sorted(all_teams))


@app.route('/schedule', methods=['GET', 'POST'])
def schedule():
    """Generate and display schedule."""
    schedule_data = None
    error = None
    stats = None
    
    if request.method == 'POST':
        try:
            # Load data
            pools = load_teams()
            courts_data = load_courts()
            constraints_data = load_constraints()
            
            if not pools:
                error = "No teams defined. Please add teams first."
            elif not courts_data:
                error = "No courts defined. Please add courts first."
            else:
                # Create Team objects
                teams = []
                for pool_name, team_names in pools.items():
                    for team_name in team_names:
                        teams.append(Team(name=team_name, attributes={'pool': pool_name}))
                
                # Create Court objects
                courts = [Court(name=c['name'], start_time=c['start_time']) for c in courts_data]
                
                # Generate matches
                matches = generate_pool_play_matches(teams)
                match_tuples = [(tuple(m["teams"]), m["pool"]) for m in matches]
                
                # Create allocation manager and schedule
                manager = AllocationManager(teams, courts, constraints_data)
                manager._generate_pool_play_matches = lambda: match_tuples
                manager.allocate_teams_to_courts()
                
                # Get schedule output
                schedule_output = manager.get_schedule_output()
                
                # Organize by day
                schedule_data = {}
                for court_info in schedule_output:
                    for match in court_info['matches']:
                        day = match['day']
                        if day not in schedule_data:
                            schedule_data[day] = {}
                        court_name = court_info['court_name']
                        if court_name not in schedule_data[day]:
                            schedule_data[day][court_name] = []
                        schedule_data[day][court_name].append(match)
                
                # Sort matches by time within each court
                for day in schedule_data:
                    for court in schedule_data[day]:
                        schedule_data[day][court].sort(key=lambda x: x['start_time'])
                
                # Calculate stats
                total_scheduled = sum(
                    len(court_matches) 
                    for day_data in schedule_data.values() 
                    for court_matches in day_data.values()
                )
                stats = {
                    'total_matches': len(matches),
                    'scheduled_matches': total_scheduled,
                    'unscheduled_matches': len(matches) - total_scheduled
                }
                
        except Exception as e:
            error = f"Error generating schedule: {str(e)}"
    
    return render_template('schedule.html', schedule=schedule_data, error=error, stats=stats)


if __name__ == '__main__':
    app.run(debug=True, port=5000)
