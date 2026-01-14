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
RESULTS_FILE = os.path.join(DATA_DIR, 'results.yaml')
SCHEDULE_FILE = os.path.join(DATA_DIR, 'schedule.yaml')


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


def load_results():
    """Load match results from YAML file."""
    if not os.path.exists(RESULTS_FILE):
        return {'pool_play': {}, 'bracket': {}, 'bracket_type': 'single'}
    with open(RESULTS_FILE, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
        if not data:
            return {'pool_play': {}, 'bracket': {}, 'bracket_type': 'single'}
        # Ensure all sections exist
        if 'pool_play' not in data:
            data['pool_play'] = {}
        if 'bracket' not in data:
            data['bracket'] = {}
        if 'bracket_type' not in data:
            data['bracket_type'] = 'single'
        return data


def save_results(results):
    """Save match results to YAML file."""
    with open(RESULTS_FILE, 'w', encoding='utf-8') as f:
        yaml.dump(results, f, default_flow_style=False)


def load_schedule():
    """Load saved schedule from YAML file."""
    if not os.path.exists(SCHEDULE_FILE):
        return None, None
    with open(SCHEDULE_FILE, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
        if not data:
            return None, None
        return data.get('schedule'), data.get('stats')


def _convert_to_serializable(obj):
    """Convert tuples to lists recursively for YAML serialization."""
    if isinstance(obj, dict):
        return {k: _convert_to_serializable(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [_convert_to_serializable(item) for item in obj]
    else:
        return obj


def save_schedule(schedule_data, stats):
    """Save schedule to YAML file."""
    # Convert tuples to lists for safe YAML serialization
    serializable_data = _convert_to_serializable(schedule_data)
    serializable_stats = _convert_to_serializable(stats)
    with open(SCHEDULE_FILE, 'w', encoding='utf-8') as f:
        yaml.dump({'schedule': serializable_data, 'stats': serializable_stats}, f, default_flow_style=False)


def get_match_key(team1, team2, pool=None):
    """Generate a unique key for a match (sorted alphabetically for consistency)."""
    teams_sorted = sorted([team1, team2])
    key = f"{teams_sorted[0]}_vs_{teams_sorted[1]}"
    if pool:
        key += f"_{pool}"
    return key


def determine_winner(sets):
    """Determine winner from set scores. Returns (winner_index, set_wins)."""
    if not sets:
        return None, (0, 0)
    
    wins = [0, 0]
    for set_score in sets:
        if len(set_score) >= 2 and set_score[0] is not None and set_score[1] is not None:
            if set_score[0] > set_score[1]:
                wins[0] += 1
            elif set_score[1] > set_score[0]:
                wins[1] += 1
    
    # Auto-detect winner (best of 3: need 2 wins, single set: need 1 win)
    if wins[0] >= 2 or (len(sets) == 1 and wins[0] > wins[1]):
        return 0, tuple(wins)
    elif wins[1] >= 2 or (len(sets) == 1 and wins[1] > wins[0]):
        return 1, tuple(wins)
    
    return None, tuple(wins)


def calculate_pool_standings(pools, results):
    """
    Calculate standings for each pool based on match results.
    
    Returns: {pool_name: [{'team': name, 'wins': n, 'losses': n, 'sets_won': n, 
                          'sets_lost': n, 'set_diff': n, 'points_for': n, 
                          'points_against': n, 'point_diff': n}, ...]}
    
    Ranking: wins -> set_differential -> point_differential -> head-to-head
    """
    standings = {}
    pool_results = results.get('pool_play', {})
    
    for pool_name, pool_data in pools.items():
        team_stats = {}
        teams = pool_data.get('teams', [])
        
        # Initialize stats for each team
        for team in teams:
            team_stats[team] = {
                'team': team,
                'wins': 0,
                'losses': 0,
                'sets_won': 0,
                'sets_lost': 0,
                'points_for': 0,
                'points_against': 0,
                'matches_played': 0
            }
        
        # Process results
        for match_key, result in pool_results.items():
            # Check if this match is in this pool
            if not match_key.endswith(f"_{pool_name}"):
                continue
            
            sets = result.get('sets', [])
            if not sets:
                continue
            
            # Use the team names stored in the result (these match the order of scores in sets)
            # The result stores team1/team2 in the order they were displayed in the UI,
            # which matches how sets[i][0] and sets[i][1] are stored
            input_team1 = result.get('team1')
            input_team2 = result.get('team2')
            
            if not input_team1 or not input_team2:
                # Fallback to extracting from key for old results without team1/team2
                key_parts = match_key.rsplit(f"_{pool_name}", 1)[0]
                teams_in_match = key_parts.split('_vs_')
                if len(teams_in_match) != 2:
                    continue
                input_team1, input_team2 = teams_in_match
            
            if input_team1 not in team_stats or input_team2 not in team_stats:
                continue
            
            # Calculate set and point totals
            # sets[i][0] is input_team1's score, sets[i][1] is input_team2's score
            team1_sets = 0
            team2_sets = 0
            team1_points = 0
            team2_points = 0
            
            for set_score in sets:
                if len(set_score) >= 2 and set_score[0] is not None and set_score[1] is not None:
                    team1_points += set_score[0]
                    team2_points += set_score[1]
                    if set_score[0] > set_score[1]:
                        team1_sets += 1
                    elif set_score[1] > set_score[0]:
                        team2_sets += 1
            
            # Update stats for input_team1 (the team whose scores are in sets[i][0])
            team_stats[input_team1]['sets_won'] += team1_sets
            team_stats[input_team1]['sets_lost'] += team2_sets
            team_stats[input_team1]['points_for'] += team1_points
            team_stats[input_team1]['points_against'] += team2_points
            team_stats[input_team1]['matches_played'] += 1
            
            # Update stats for input_team2 (the team whose scores are in sets[i][1])
            team_stats[input_team2]['sets_won'] += team2_sets
            team_stats[input_team2]['sets_lost'] += team1_sets
            team_stats[input_team2]['points_for'] += team2_points
            team_stats[input_team2]['points_against'] += team1_points
            team_stats[input_team2]['matches_played'] += 1
            
            # Use stored winner from result (more reliable than re-calculating)
            winner = result.get('winner')
            if winner == input_team1:
                team_stats[input_team1]['wins'] += 1
                team_stats[input_team2]['losses'] += 1
            elif winner == input_team2:
                team_stats[input_team2]['wins'] += 1
                team_stats[input_team1]['losses'] += 1
        
        # Calculate differentials
        for team in team_stats:
            team_stats[team]['set_diff'] = team_stats[team]['sets_won'] - team_stats[team]['sets_lost']
            team_stats[team]['point_diff'] = team_stats[team]['points_for'] - team_stats[team]['points_against']
        
        # Sort teams by: wins (desc), set_diff (desc), point_diff (desc), alphabetical
        sorted_teams = sorted(
            team_stats.values(),
            key=lambda x: (-x['wins'], -x['set_diff'], -x['point_diff'], x['team'])
        )
        
        # Include advance_count for each pool so JavaScript can highlight advancing teams
        advance_count = pool_data.get('advance', 2)
        for team in sorted_teams:
            team['advance_count'] = advance_count
        
        standings[pool_name] = sorted_teams
    
    return standings


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
            constraints_data['scoring_format'] = request.form.get('scoring_format', 'best_of_3')
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
                
                # Create lookup from team pairs to pool
                match_to_pool = {}
                for m in matches:
                    key = tuple(sorted(m["teams"]))
                    match_to_pool[key] = m["pool"]
                
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
                        # Add pool info to each match
                        teams_key = tuple(sorted(match['teams']))
                        match['pool'] = match_to_pool.get(teams_key, '')
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
                
                # Save the schedule for tracking
                save_schedule(schedule_data, stats)
                
                # Clear all previous results (pool play and bracket)
                save_results({'pool_play': {}, 'bracket': {}, 'bracket_type': 'single'})
                
                # Redirect to tracking page after successful generation
                return redirect(url_for('tracking'))
                
        except Exception as e:
            error = f"Error generating schedule: {str(e)}"
    
    # GET request - load saved schedule if exists
    schedule_data, stats = load_schedule()
    
    return render_template('schedule.html', schedule=schedule_data, error=error, stats=stats)


@app.route('/tracking')
def tracking():
    """Display schedule with result tracking."""
    # Load saved schedule
    schedule_data, stats = load_schedule()
    
    if not schedule_data:
        return render_template('tracking.html', schedule=None, stats=None, 
                             results={}, standings={}, scoring_format='best_of_3', pools={})
    
    # Load results and calculate standings
    pools = load_teams()
    results = load_results()
    standings = calculate_pool_standings(pools, results)
    constraints = load_constraints()
    scoring_format = constraints.get('scoring_format', 'best_of_3')
    
    # Calculate tracking stats - use scheduled_matches from the saved stats
    scheduled_matches = stats.get('scheduled_matches', 0) if stats else 0
    completed_matches = len([r for r in results.get('pool_play', {}).values() if r.get('completed')])
    tracking_stats = {
        'scheduled_matches': scheduled_matches,
        'completed_matches': completed_matches,
        'remaining_matches': scheduled_matches - completed_matches
    }
    
    return render_template('tracking.html', schedule=schedule_data, stats=tracking_stats,
                          results=results.get('pool_play', {}), standings=standings,
                          scoring_format=scoring_format, pools=pools)


@app.route('/api/results/pool', methods=['POST'])
def save_pool_result():
    """API endpoint to save a pool play match result."""
    data = request.get_json()
    
    team1 = data.get('team1')
    team2 = data.get('team2')
    pool = data.get('pool')
    sets = data.get('sets', [])
    
    if not team1 or not team2:
        return jsonify({'error': 'Missing team names'}), 400
    
    # Generate match key
    match_key = get_match_key(team1, team2, pool)
    
    # Load existing results
    results = load_results()
    
    # Determine winner based on input order (team1 = index 0, team2 = index 1)
    winner_idx, set_wins = determine_winner(sets)
    winner = None
    if winner_idx == 0:
        winner = team1
    elif winner_idx == 1:
        winner = team2
    
    # Save result
    results['pool_play'][match_key] = {
        'sets': sets,
        'winner': winner,
        'completed': winner is not None,
        'team1': team1,
        'team2': team2
    }
    
    save_results(results)
    
    # Recalculate standings
    pools = load_teams()
    standings = calculate_pool_standings(pools, results)
    
    return jsonify({
        'success': True,
        'match_key': match_key,
        'winner': winner,
        'set_wins': set_wins,
        'standings': standings
    })


@app.route('/api/results/bracket', methods=['POST'])
def save_bracket_result():
    """API endpoint to save a bracket match result."""
    data = request.get_json()
    
    team1 = data.get('team1')
    team2 = data.get('team2')
    round_name = data.get('round')
    match_number = data.get('match_number')
    bracket_type = data.get('bracket_type', 'winners')  # 'winners', 'losers', 'grand_final', 'bracket_reset'
    sets = data.get('sets', [])
    
    if not team1 or not team2:
        return jsonify({'error': 'Missing team names'}), 400
    
    # Generate match key
    match_key = f"{bracket_type}_{round_name}_{match_number}"
    
    # Load existing results
    results = load_results()
    
    # Determine winner
    winner_idx, set_wins = determine_winner(sets)
    winner = None
    loser = None
    if winner_idx == 0:
        winner = team1
        loser = team2
    elif winner_idx == 1:
        winner = team2
        loser = team1
    
    # Save result
    results['bracket'][match_key] = {
        'sets': sets,
        'winner': winner,
        'loser': loser,
        'completed': winner is not None,
        'team1': team1,
        'team2': team2,
        'round': round_name,
        'match_number': match_number,
        'bracket_type': bracket_type
    }
    
    save_results(results)
    
    return jsonify({
        'success': True,
        'match_key': match_key,
        'winner': winner,
        'loser': loser,
        'set_wins': set_wins
    })


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
    
    # Load results and calculate standings for actual team names
    results = load_results()
    standings = calculate_pool_standings(pools, results)
    bracket_results = results.get('bracket', {})
    constraints = load_constraints()
    scoring_format = constraints.get('scoring_format', 'best_of_3')
    
    # Generate bracket with results applied
    from core.elimination import generate_bracket_with_results
    bracket_data = generate_bracket_with_results(pools, standings, bracket_results)
    
    return render_template('sbracket.html', bracket_data=bracket_data, error=None, 
                          bracket_results=bracket_results, scoring_format=scoring_format)


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
    
    # Load results and calculate standings for actual team names
    results = load_results()
    standings = calculate_pool_standings(pools, results)
    bracket_results = results.get('bracket', {})
    constraints = load_constraints()
    scoring_format = constraints.get('scoring_format', 'best_of_3')
    
    # Generate bracket with results applied
    from core.double_elimination import generate_double_bracket_with_results
    bracket_data = generate_double_bracket_with_results(pools, standings, bracket_results)
    
    return render_template('dbracket.html', bracket_data=bracket_data, error=None,
                          bracket_results=bracket_results, scoring_format=scoring_format)


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
