"""
Flask web application for Tournament Allocator.
"""
import os
import csv
import yaml
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash
from core.models import Team, Court
from core.allocation import AllocationManager
from core.elimination import get_elimination_bracket_display, generate_elimination_matches_for_scheduling
from core.double_elimination import get_double_elimination_bracket_display, generate_double_elimination_matches_for_scheduling
from generate_matches import generate_pool_play_matches, generate_elimination_matches

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
        if not data:
            return {}
        # Normalize format: each pool has 'teams' list and 'advance' count
        normalized = {}
        for pool_name, pool_data in data.items():
            if isinstance(pool_data, list):
                # Old format: just a list of teams
                normalized[pool_name] = {'teams': pool_data, 'advance': 2}
            else:
                # New format: dict with teams and advance
                normalized[pool_name] = pool_data
        return normalized


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
    total_teams = sum(len(pool_data['teams']) for pool_data in pools.values()) if pools else 0
    
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
            advance_count = int(request.form.get('advance_count', 2))
            if pool_name:
                pools = load_teams()
                if pool_name in pools:
                    flash(f'Pool "{pool_name}" already exists.', 'error')
                else:
                    pools[pool_name] = {'teams': [], 'advance': advance_count}
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
                for p_name, pool_data in pools.items():
                    for t in pool_data['teams']:
                        all_teams[t] = p_name
                
                if team_name in all_teams:
                    flash(f'Team "{team_name}" already exists in {all_teams[team_name]}.', 'error')
                elif pool_name in pools:
                    pools[pool_name]['teams'].append(team_name)
                    save_teams(pools)
        
        elif action == 'delete_team':
            pool_name = request.form.get('pool_name')
            team_name = request.form.get('team_name')
            pools = load_teams()
            if pool_name in pools and team_name in pools[pool_name]['teams']:
                pools[pool_name]['teams'].remove(team_name)
                save_teams(pools)
        
        elif action == 'update_advance':
            pool_name = request.form.get('pool_name')
            advance_count = int(request.form.get('advance_count', 2))
            pools = load_teams()
            if pool_name in pools:
                pools[pool_name]['advance'] = advance_count
                save_teams(pools)
        
        elif action == 'edit_pool':
            old_pool_name = request.form.get('old_pool_name', '').strip()
            new_pool_name = request.form.get('new_pool_name', '').strip()
            if old_pool_name and new_pool_name and old_pool_name != new_pool_name:
                pools = load_teams()
                if new_pool_name in pools:
                    flash(f'Pool "{new_pool_name}" already exists.', 'error')
                elif old_pool_name in pools:
                    # Create new pool with same data, delete old
                    pools[new_pool_name] = pools[old_pool_name]
                    del pools[old_pool_name]
                    save_teams(pools)
                    flash(f'Pool renamed from "{old_pool_name}" to "{new_pool_name}".', 'success')
        
        elif action == 'edit_team':
            pool_name = request.form.get('pool_name')
            old_team_name = request.form.get('old_team_name', '').strip()
            new_team_name = request.form.get('new_team_name', '').strip()
            if pool_name and old_team_name and new_team_name:
                pools = load_teams()
                # Check if new name already exists in any pool
                all_teams = {}
                for p_name, pool_data in pools.items():
                    for t in pool_data['teams']:
                        if t != old_team_name:  # Exclude the team being renamed
                            all_teams[t] = p_name
                
                if new_team_name in all_teams:
                    flash(f'Team "{new_team_name}" already exists in {all_teams[new_team_name]}.', 'error')
                elif pool_name in pools and old_team_name in pools[pool_name]['teams']:
                    # Update team name in pool
                    idx = pools[pool_name]['teams'].index(old_team_name)
                    pools[pool_name]['teams'][idx] = new_team_name
                    save_teams(pools)
                    
                    # Also update in constraints if referenced
                    constraints = load_constraints()
                    updated_constraints = False
                    if 'team_specific_constraints' in constraints:
                        for constraint in constraints['team_specific_constraints']:
                            if constraint.get('team_name') == old_team_name:
                                constraint['team_name'] = new_team_name
                                updated_constraints = True
                    if updated_constraints:
                        save_constraints(constraints)
                    
                    flash(f'Team renamed from "{old_team_name}" to "{new_team_name}".', 'success')
        
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
        
        elif action == 'edit_court':
            old_court_name = request.form.get('old_court_name', '').strip()
            new_court_name = request.form.get('new_court_name', '').strip()
            if old_court_name and new_court_name:
                # Check if new name already exists
                existing_names = [c['name'] for c in courts_list if c['name'] != old_court_name]
                if new_court_name in existing_names:
                    flash(f'Court "{new_court_name}" already exists.', 'error')
                else:
                    # Update court name
                    for court in courts_list:
                        if court['name'] == old_court_name:
                            court['name'] = new_court_name
                            break
                    save_courts(courts_list)
                    flash(f'Court renamed from "{old_court_name}" to "{new_court_name}".', 'success')
        
        return redirect(url_for('courts'))
    
    courts_list = load_courts()
    return render_template('courts.html', courts=courts_list)


@app.route('/settings', methods=['GET', 'POST'])
@app.route('/constraints', methods=['GET', 'POST'])  # Keep old URL for compatibility
def settings():
    """Settings management page."""
    if request.method == 'POST':
        action = request.form.get('action')
        constraints_data = load_constraints()
        
        if action == 'update_general':
            constraints_data['match_duration_minutes'] = int(request.form.get('match_duration', 60))
            constraints_data['days_number'] = int(request.form.get('days_number', 1))
            constraints_data['min_break_between_matches_minutes'] = int(request.form.get('min_break', 15))
            constraints_data['time_slot_increment_minutes'] = int(request.form.get('time_increment', 15))
            constraints_data['day_end_time_limit'] = request.form.get('day_end_time', '22:00')
            constraints_data['bracket_type'] = request.form.get('bracket_type', 'single')
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
        
        return redirect(url_for('settings'))
    
    constraints_data = load_constraints()
    pools = load_teams()
    all_teams = []
    for pool_data in pools.values():
        all_teams.extend(pool_data['teams'])
    
    courts_list = load_courts()
    all_courts = [c['name'] for c in courts_list]
    
    return render_template('constraints.html', constraints=constraints_data, all_teams=sorted(all_teams), all_courts=sorted(all_courts))

# Alias for backward compatibility
constraints = settings


@app.route('/bracket')
def bracket():
    """Redirect to appropriate bracket based on settings."""
    constraints_data = load_constraints()
    bracket_type = constraints_data.get('bracket_type', 'single')
    if bracket_type == 'double':
        return redirect(url_for('dbracket'))
    return redirect(url_for('sbracket'))


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
                for pool_name, pool_data in pools.items():
                    for team_name in pool_data['teams']:
                        teams.append(Team(name=team_name, attributes={'pool': pool_name}))
                
                # Create Court objects
                courts = [Court(name=c['name'], start_time=c['start_time'], end_time=c.get('end_time')) for c in courts_data]
                
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
                
                # Build time-aligned grid for display
                # Collect all unique time slots across all courts for each day
                for day in schedule_data:
                    all_times = set()
                    for court in schedule_data[day]:
                        for match in schedule_data[day][court]:
                            all_times.add(match['start_time'])
                    
                    # Create time-indexed lookup for each court
                    for court in schedule_data[day]:
                        time_to_match = {m['start_time']: m for m in schedule_data[day][court]}
                        schedule_data[day][court] = {
                            'matches': schedule_data[day][court],
                            'time_to_match': time_to_match
                        }
                    
                    # Store sorted time slots for this day
                    schedule_data[day]['_time_slots'] = sorted(all_times)
                
                # Calculate stats
                total_scheduled = sum(
                    len(court_data['matches']) 
                    for day_data in schedule_data.values() 
                    for court_name, court_data in day_data.items()
                    if court_name != '_time_slots'
                )
                stats = {
                    'total_matches': len(matches),
                    'scheduled_matches': total_scheduled,
                    'unscheduled_matches': len(matches) - total_scheduled
                }
                
        except Exception as e:
            error = f"Error generating schedule: {str(e)}"
    
    return render_template('schedule.html', schedule=schedule_data, error=error, stats=stats)


@app.route('/sbracket')
def sbracket():
    """Display single elimination bracket."""
    pools = load_teams()
    
    if not pools:
        return render_template('sbracket.html', bracket_data=None, error="No pools defined. Please add teams first.")
    
    # Check if any teams will advance
    total_advancing = sum(pool_data.get('advance', 2) for pool_data in pools.values())
    if total_advancing < 2:
        return render_template('sbracket.html', bracket_data=None, error="Not enough teams advancing to create a bracket.")
    
    bracket_data = get_elimination_bracket_display(pools)
    
    return render_template('sbracket.html', bracket_data=bracket_data, error=None)


@app.route('/schedule/single_elimination', methods=['GET', 'POST'])
def schedule_single_elimination():
    """Generate and display single elimination round schedule."""
    schedule_data = None
    error = None
    stats = None
    bracket_data = None
    
    if request.method == 'POST':
        try:
            pools = load_teams()
            courts_data = load_courts()
            constraints_data = load_constraints()
            
            if not pools:
                error = "No teams defined. Please add teams first."
            elif not courts_data:
                error = "No courts defined. Please add courts first."
            else:
                # Get bracket data for display
                bracket_data = get_elimination_bracket_display(pools)
                
                if bracket_data['total_teams'] < 2:
                    error = "Not enough teams advancing to create elimination bracket."
                else:
                    # Create Team objects for advancing teams
                    teams = []
                    for team_name, seed, pool_name in bracket_data['seeded_teams']:
                        teams.append(Team(name=team_name, attributes={'pool': pool_name, 'seed': seed}))
                    
                    # Create Court objects
                    courts = [Court(name=c['name'], start_time=c['start_time'], end_time=c.get('end_time')) for c in courts_data]
                    
                    # Generate elimination matches
                    elimination_matches = generate_elimination_matches_for_scheduling(pools)
                    
                    # Filter out byes
                    match_tuples = [(teams_tuple, round_name) for teams_tuple, round_name in elimination_matches]
                    
                    if not match_tuples:
                        error = "No elimination matches to schedule (all teams may have byes)."
                    else:
                        # Create allocation manager and schedule
                        manager = AllocationManager(teams, courts, constraints_data)
                        manager._generate_pool_play_matches = lambda: match_tuples
                        manager.allocate_teams_to_courts()
                        
                        # Get schedule output
                        schedule_output = manager.get_schedule_output()
                        
                        # Organize by day and round
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
                        
                        # Sort matches by time
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
                            'total_matches': len(match_tuples),
                            'scheduled_matches': total_scheduled,
                            'unscheduled_matches': len(match_tuples) - total_scheduled
                        }
                        
        except Exception as e:
            import traceback
            error = f"Error generating elimination schedule: {str(e)}"
            traceback.print_exc()
    
    pools = load_teams()
    if not bracket_data and pools:
        bracket_data = get_elimination_bracket_display(pools)
    
    return render_template('schedule_single_elimination.html', 
                         schedule=schedule_data, 
                         error=error, 
                         stats=stats,
                         bracket_data=bracket_data)


@app.route('/dbracket')
def dbracket():
    """Display double elimination bracket."""
    pools = load_teams()
    
    if not pools:
        return render_template('dbracket.html', bracket_data=None, error="No pools defined. Please add teams first.")
    
    # Check if any teams will advance
    total_advancing = sum(pool_data.get('advance', 2) for pool_data in pools.values())
    if total_advancing < 2:
        return render_template('dbracket.html', bracket_data=None, error="Not enough teams advancing to create a bracket.")
    
    bracket_data = get_double_elimination_bracket_display(pools)
    
    return render_template('dbracket.html', bracket_data=bracket_data, error=None)


@app.route('/schedule/double_elimination', methods=['GET', 'POST'])
def schedule_double_elimination():
    """Generate and display double elimination round schedule."""
    schedule_data = None
    error = None
    stats = None
    bracket_data = None
    
    if request.method == 'POST':
        try:
            pools = load_teams()
            courts_data = load_courts()
            constraints_data = load_constraints()
            
            if not pools:
                error = "No teams defined. Please add teams first."
            elif not courts_data:
                error = "No courts defined. Please add courts first."
            else:
                # Get bracket data for display
                bracket_data = get_double_elimination_bracket_display(pools)
                
                if bracket_data['total_teams'] < 2:
                    error = "Not enough teams advancing to create double elimination bracket."
                else:
                    # Create Team objects for advancing teams
                    teams = []
                    for team_name, seed, pool_name in bracket_data['seeded_teams']:
                        teams.append(Team(name=team_name, attributes={'pool': pool_name, 'seed': seed}))
                    
                    # Create Court objects
                    courts = [Court(name=c['name'], start_time=c['start_time'], end_time=c.get('end_time')) for c in courts_data]
                    
                    # Generate double elimination matches (first round only)
                    elimination_matches = generate_double_elimination_matches_for_scheduling(pools)
                    
                    # Filter out byes
                    match_tuples = [(teams_tuple, round_name) for teams_tuple, round_name in elimination_matches]
                    
                    if not match_tuples:
                        error = "No double elimination matches to schedule (all teams may have byes)."
                    else:
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
                        
                        # Sort matches by time
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
                            'total_matches': len(match_tuples),
                            'scheduled_matches': total_scheduled,
                            'unscheduled_matches': len(match_tuples) - total_scheduled
                        }
                        
        except Exception as e:
            import traceback
            error = f"Error generating double elimination schedule: {str(e)}"
            traceback.print_exc()
    
    pools = load_teams()
    if not bracket_data and pools:
        bracket_data = get_double_elimination_bracket_display(pools)
    
    return render_template('schedule_double_elimination.html', 
                         schedule=schedule_data, 
                         error=error, 
                         stats=stats,
                         bracket_data=bracket_data)


if __name__ == '__main__':
    app.run(debug=True, port=5000)
