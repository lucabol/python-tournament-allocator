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
PRINT_SETTINGS_FILE = os.path.join(DATA_DIR, 'print_settings.yaml')


def load_print_settings():
    """Load print settings from YAML file."""
    defaults = {
        'title': 'Tournament Summary',
        'subtitle': 'January 2026'
    }
    if not os.path.exists(PRINT_SETTINGS_FILE):
        return defaults
    with open(PRINT_SETTINGS_FILE, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
        if not data:
            return defaults
        return {**defaults, **data}


def save_print_settings(settings):
    """Save print settings to YAML file."""
    with open(PRINT_SETTINGS_FILE, 'w', encoding='utf-8') as f:
        yaml.dump(settings, f, default_flow_style=False)


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
    """Load constraints from YAML file, merging with defaults."""
    defaults = get_default_constraints()
    if not os.path.exists(CONSTRAINTS_FILE):
        return defaults
    with open(CONSTRAINTS_FILE, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
        if not data:
            return defaults
        # Merge with defaults to ensure all keys exist
        for key, value in defaults.items():
            if key not in data:
                data[key] = value
        return data


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
        'match_duration_minutes': 30,
        'days_number': 1,
        'min_break_between_matches_minutes': 0,
        'time_slot_increment_minutes': 15,
        'day_end_time_limit': '02:00',
        'bracket_type': 'double',
        'scoring_format': 'single_set',
        'pool_in_same_court': True,
        'silver_bracket_enabled': True,
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
        
        if action == 'load_yaml':
            file = request.files.get('yaml_file')
            if file and file.filename:
                try:
                    content = file.read().decode('utf-8')
                    data = yaml.safe_load(content)
                    if not isinstance(data, dict):
                        flash('Invalid YAML format. Expected pool definitions.', 'error')
                    else:
                        # Normalize format
                        normalized = {}
                        for pool_name, pool_data in data.items():
                            if isinstance(pool_data, list):
                                normalized[pool_name] = {'teams': pool_data, 'advance': 2}
                            elif isinstance(pool_data, dict):
                                teams_list = pool_data.get('teams', [])
                                advance = pool_data.get('advance', 2)
                                normalized[pool_name] = {'teams': teams_list, 'advance': advance}
                            else:
                                flash(f'Invalid format for pool "{pool_name}".', 'error')
                                return redirect(url_for('teams'))
                        save_teams(normalized)
                        # Clear existing schedule when teams change
                        if os.path.exists(SCHEDULE_FILE):
                            os.remove(SCHEDULE_FILE)
                        flash(f'Loaded {len(normalized)} pool(s) from YAML file.', 'success')
                except yaml.YAMLError as e:
                    flash(f'Error parsing YAML: {e}', 'error')
                except Exception as e:
                    flash(f'Error loading file: {e}', 'error')
            else:
                flash('Please select a YAML file to load.', 'error')
            return redirect(url_for('teams'))
        
        elif action == 'add_pool':
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
        
        return redirect(url_for('teams'))
    
    pools = load_teams()
    return render_template('teams.html', pools=pools)


@app.route('/courts', methods=['GET', 'POST'])
def courts():
    """Courts management page."""
    if request.method == 'POST':
        action = request.form.get('action')
        courts_list = load_courts()
        
        if action == 'load_yaml':
            file = request.files.get('yaml_file')
            if file and file.filename:
                try:
                    content = file.read().decode('utf-8')
                    data = yaml.safe_load(content)
                    if not isinstance(data, list):
                        flash('Invalid YAML format. Expected a list of courts.', 'error')
                    else:
                        new_courts = []
                        for court in data:
                            if isinstance(court, dict) and 'name' in court:
                                new_courts.append({
                                    'name': court['name'],
                                    'start_time': court.get('start_time', '08:00'),
                                    'end_time': court.get('end_time', '22:00')
                                })
                            else:
                                flash('Invalid court format. Each court must have a "name" field.', 'error')
                                return redirect(url_for('courts'))
                        save_courts(new_courts)
                        # Clear existing schedule when courts change
                        if os.path.exists(SCHEDULE_FILE):
                            os.remove(SCHEDULE_FILE)
                        flash(f'Loaded {len(new_courts)} court(s) from YAML file.', 'success')
                except yaml.YAMLError as e:
                    flash(f'Error parsing YAML: {e}', 'error')
                except Exception as e:
                    flash(f'Error loading file: {e}', 'error')
            else:
                flash('Please select a YAML file to load.', 'error')
            return redirect(url_for('courts'))
        
        elif action == 'add_court':
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
        
        return redirect(url_for('courts'))
    
    courts_list = load_courts()
    return render_template('courts.html', courts=courts_list)


# AJAX API endpoints for auto-save
@app.route('/api/teams/edit_pool', methods=['POST'])
def api_edit_pool():
    """AJAX endpoint for editing pool name."""
    data = request.get_json()
    old_name = data.get('old_name', '').strip()
    new_name = data.get('new_name', '').strip()
    
    if not old_name or not new_name or old_name == new_name:
        return jsonify({'success': True})
    
    pools = load_teams()
    if new_name in pools:
        return jsonify({'success': False, 'error': f'Pool "{new_name}" already exists.'})
    if old_name in pools:
        pools[new_name] = pools[old_name]
        del pools[old_name]
        save_teams(pools)
    return jsonify({'success': True})


@app.route('/api/teams/edit_team', methods=['POST'])
def api_edit_team():
    """AJAX endpoint for editing team name."""
    data = request.get_json()
    pool_name = data.get('pool_name', '').strip()
    old_name = data.get('old_name', '').strip()
    new_name = data.get('new_name', '').strip()
    
    if not pool_name or not old_name or not new_name or old_name == new_name:
        return jsonify({'success': True})
    
    pools = load_teams()
    
    # Check if new name already exists
    for p_name, pool_data in pools.items():
        for t in pool_data['teams']:
            if t == new_name and t != old_name:
                return jsonify({'success': False, 'error': f'Team "{new_name}" already exists.'})
    
    if pool_name in pools and old_name in pools[pool_name]['teams']:
        idx = pools[pool_name]['teams'].index(old_name)
        pools[pool_name]['teams'][idx] = new_name
        save_teams(pools)
        
        # Update constraints
        constraints = load_constraints()
        if 'team_specific_constraints' in constraints:
            for constraint in constraints['team_specific_constraints']:
                if constraint.get('team_name') == old_name:
                    constraint['team_name'] = new_name
            save_constraints(constraints)
    
    return jsonify({'success': True})


@app.route('/api/teams/update_advance', methods=['POST'])
def api_update_advance():
    """AJAX endpoint for updating advance count."""
    data = request.get_json()
    pool_name = data.get('pool_name', '').strip()
    advance_count = data.get('advance_count', 2)
    
    if not pool_name:
        return jsonify({'success': False, 'error': 'Pool name required'})
    
    pools = load_teams()
    if pool_name in pools:
        pools[pool_name]['advance'] = int(advance_count)
        save_teams(pools)
    
    return jsonify({'success': True})


@app.route('/api/courts/edit', methods=['POST'])
def api_edit_court():
    """AJAX endpoint for editing court name."""
    data = request.get_json()
    old_name = data.get('old_name', '').strip()
    new_name = data.get('new_name', '').strip()
    
    if not old_name or not new_name or old_name == new_name:
        return jsonify({'success': True})
    
    courts_list = load_courts()
    
    # Check if new name exists
    if any(c['name'] == new_name for c in courts_list if c['name'] != old_name):
        return jsonify({'success': False, 'error': f'Court "{new_name}" already exists.'})
    
    for court in courts_list:
        if court['name'] == old_name:
            court['name'] = new_name
            break
    save_courts(courts_list)
    
    return jsonify({'success': True})


@app.route('/api/settings/update', methods=['POST'])
def api_update_settings():
    """AJAX endpoint for updating settings."""
    data = request.get_json()
    constraints_data = load_constraints()
    
    # Update all provided fields
    if 'match_duration' in data:
        constraints_data['match_duration_minutes'] = int(data['match_duration'])
    if 'days_number' in data:
        constraints_data['days_number'] = int(data['days_number'])
    if 'min_break' in data:
        constraints_data['min_break_between_matches_minutes'] = int(data['min_break'])
    if 'time_increment' in data:
        constraints_data['time_slot_increment_minutes'] = int(data['time_increment'])
    if 'day_end_time' in data:
        constraints_data['day_end_time_limit'] = data['day_end_time']
    if 'bracket_type' in data:
        constraints_data['bracket_type'] = data['bracket_type']
    if 'scoring_format' in data:
        constraints_data['scoring_format'] = data['scoring_format']
    if 'pool_in_same_court' in data:
        constraints_data['pool_in_same_court'] = data['pool_in_same_court']
    if 'silver_bracket_enabled' in data:
        constraints_data['silver_bracket_enabled'] = data['silver_bracket_enabled']
    
    save_constraints(constraints_data)
    return jsonify({'success': True})


@app.route('/api/reset', methods=['POST'])
def api_reset_all():
    """Reset all tournament data."""
    # Clear all data files
    if os.path.exists(TEAMS_FILE):
        os.remove(TEAMS_FILE)
    if os.path.exists(COURTS_FILE):
        os.remove(COURTS_FILE)
    if os.path.exists(RESULTS_FILE):
        os.remove(RESULTS_FILE)
    if os.path.exists(SCHEDULE_FILE):
        os.remove(SCHEDULE_FILE)
    if os.path.exists(CONSTRAINTS_FILE):
        os.remove(CONSTRAINTS_FILE)
    
    return jsonify({'success': True})


@app.route('/api/test-data', methods=['POST'])
def api_load_test_data():
    """Load test data for development/testing."""
    # Test teams - 4 pools with 4 teams each
    test_teams = {
        'Pool A': {
            'teams': ['Adam - Rob', 'Alex - Sara', 'Anna - Lisa', 'Amy - Emma'],
            'advance': 2
        },
        'Pool B': {
            'teams': ['Ben - Kim', 'Brian - Pat', 'Beth - Jordan', 'Blake - Morgan'],
            'advance': 2
        },
        'Pool C': {
            'teams': ['Chris - Taylor', 'Carl - Drew', 'Claire - Avery', 'Cody - Sage'],
            'advance': 2
        },
        'Pool D': {
            'teams': ['David - Zoe', 'Dan - Mia', 'Diana - Jake', 'Derek - Lily'],
            'advance': 2
        }
    }
    save_teams(test_teams)
    
    # Test courts - 4 courts
    test_courts = [
        {'name': 'Court 1', 'start_time': '09:00', 'end_time': '02:00'},
        {'name': 'Court 2', 'start_time': '09:00', 'end_time': '02:00'},
        {'name': 'Court 3', 'start_time': '09:00', 'end_time': '02:00'},
        {'name': 'Court 4', 'start_time': '09:00', 'end_time': '02:00'}
    ]
    save_courts(test_courts)
    
    # Clear any existing results and schedule
    if os.path.exists(RESULTS_FILE):
        os.remove(RESULTS_FILE)
    if os.path.exists(SCHEDULE_FILE):
        os.remove(SCHEDULE_FILE)
    
    return jsonify({'success': True})


@app.route('/api/generate-random-results', methods=['POST'])
def api_generate_random_results():
    """Generate random results for all scheduled pool matches."""
    import random
    
    schedule_data, stats = load_schedule()
    
    if not schedule_data:
        return jsonify({'success': False, 'error': 'No schedule found'})
    
    results = load_results()
    pool_results = results.get('pool_play', {})
    
    # Iterate through schedule structure: day -> court -> matches list
    for day_name, day_data in schedule_data.items():
        for court_name, court_data in day_data.items():
            if court_name == '_time_slots':
                continue
            
            matches_list = court_data.get('matches', [])
            for match in matches_list:
                if not match or not isinstance(match, dict):
                    continue
                
                teams = match.get('teams', [])
                pool_name = match.get('pool')
                
                if len(teams) < 2 or not pool_name:
                    continue
                
                team1, team2 = teams[0], teams[1]
                match_key = get_match_key(team1, team2, pool_name)
                
                # Random score (single set, winner gets 21, loser gets 10-19)
                winner_score = 21
                loser_score = random.randint(10, 19)
                
                # Randomly decide winner
                if random.random() < 0.5:
                    sets = [[winner_score, loser_score]]
                    winner = team1
                    loser = team2
                else:
                    sets = [[loser_score, winner_score]]
                    winner = team2
                    loser = team1
                
                pool_results[match_key] = {
                    'sets': sets,
                    'winner': winner,
                    'loser': loser,
                    'completed': True,
                    'team1': team1,
                    'team2': team2
                }
    
    results['pool_play'] = pool_results
    save_results(results)
    
    return jsonify({'success': True})


@app.route('/api/generate-random-bracket-results', methods=['POST'])
def api_generate_random_bracket_results():
    """Generate random results for all playable bracket matches."""
    import random
    from core.double_elimination import generate_double_bracket_with_results
    from core.elimination import seed_silver_bracket_teams
    
    pools = load_teams()
    results = load_results()
    # Clear previous bracket results to regenerate fresh
    bracket_results = {}
    constraints = load_constraints()
    
    # Get standings for seeding
    standings = calculate_pool_standings(pools, results)
    
    # Generate bracket to find playable matches
    bracket_data = generate_double_bracket_with_results(pools, standings, bracket_results)
    
    if not bracket_data:
        return jsonify({'success': False, 'error': 'No bracket data'})
    
    updated = True
    # Keep generating results until no more playable matches
    while updated:
        updated = False
        bracket_data = generate_double_bracket_with_results(pools, standings, bracket_results)
        
        # Process winners bracket
        for round_name, matches in bracket_data.get('winners_bracket', {}).items():
            for match in matches:
                if match.get('is_playable') and not match.get('is_bye'):
                    team1, team2 = match['teams']
                    match_number = match['match_number']
                    match_key = f"winners_{round_name}_{match_number}"
                    
                    if match_key not in bracket_results or not bracket_results[match_key].get('completed'):
                        winner_score = 21
                        loser_score = random.randint(10, 19)
                        
                        if random.random() < 0.5:
                            sets = [[winner_score, loser_score]]
                            winner, loser = team1, team2
                        else:
                            sets = [[loser_score, winner_score]]
                            winner, loser = team2, team1
                        
                        bracket_results[match_key] = {
                            'sets': sets,
                            'winner': winner,
                            'loser': loser,
                            'completed': True
                        }
                        updated = True
        
        # Process losers bracket
        for round_name, matches in bracket_data.get('losers_bracket', {}).items():
            for match in matches:
                if match.get('is_playable'):
                    team1, team2 = match['teams']
                    match_number = match['match_number']
                    match_key = f"losers_{round_name}_{match_number}"
                    
                    if match_key not in bracket_results or not bracket_results[match_key].get('completed'):
                        winner_score = 21
                        loser_score = random.randint(10, 19)
                        
                        if random.random() < 0.5:
                            sets = [[winner_score, loser_score]]
                            winner, loser = team1, team2
                        else:
                            sets = [[loser_score, winner_score]]
                            winner, loser = team2, team1
                        
                        bracket_results[match_key] = {
                            'sets': sets,
                            'winner': winner,
                            'loser': loser,
                            'completed': True
                        }
                        updated = True
        
        # Process grand final
        gf = bracket_data.get('grand_final')
        if gf and gf.get('is_playable'):
            team1, team2 = gf['teams']
            match_key = "grand_final_Grand Final_1"
            
            if match_key not in bracket_results or not bracket_results[match_key].get('completed'):
                winner_score = 21
                loser_score = random.randint(10, 19)
                
                if random.random() < 0.5:
                    sets = [[winner_score, loser_score]]
                    winner, loser = team1, team2
                else:
                    sets = [[loser_score, winner_score]]
                    winner, loser = team2, team1
                
                bracket_results[match_key] = {
                    'sets': sets,
                    'winner': winner,
                    'loser': loser,
                    'completed': True
                }
                updated = True
        
        # Process bracket reset if needed
        br = bracket_data.get('bracket_reset')
        if br and br.get('needs_reset') and br.get('is_playable'):
            team1, team2 = br['teams']
            match_key = "bracket_reset_Bracket Reset_1"
            
            if match_key not in bracket_results or not bracket_results[match_key].get('completed'):
                winner_score = 21
                loser_score = random.randint(10, 19)
                
                if random.random() < 0.5:
                    sets = [[winner_score, loser_score]]
                    winner, loser = team1, team2
                else:
                    sets = [[loser_score, winner_score]]
                    winner, loser = team2, team1
                
                bracket_results[match_key] = {
                    'sets': sets,
                    'winner': winner,
                    'loser': loser,
                    'completed': True
                }
                updated = True
    
    results['bracket'] = bracket_results
    save_results(results)
    
    return jsonify({'success': True})


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
            constraints_data['pool_in_same_court'] = request.form.get('pool_in_same_court') == 'on'
            constraints_data['silver_bracket_enabled'] = request.form.get('silver_bracket_enabled') == 'on'
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
                
                # Stay on schedule page after successful generation
                return render_template('schedule.html', schedule=schedule_data, error=None, stats=stats)
                
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


@app.route('/print')
def print_view():
    """Display printable tournament summary."""
    pools = load_teams()
    courts = load_courts()
    constraints = load_constraints()
    schedule_data, stats = load_schedule()
    results = load_results()
    standings = calculate_pool_standings(pools, results)
    
    # Get bracket data
    bracket_data = None
    silver_bracket_data = None
    bracket_results = results.get('bracket', {})
    
    if pools:
        bracket_type = constraints.get('bracket_type', 'single')
        if bracket_type == 'double':
            from core.double_elimination import generate_double_bracket_with_results, generate_silver_double_bracket_with_results
            bracket_data = generate_double_bracket_with_results(pools, standings, bracket_results)
            if constraints.get('silver_bracket_enabled'):
                silver_bracket_data = generate_silver_double_bracket_with_results(pools, standings, bracket_results)
        else:
            from core.elimination import generate_bracket_with_results, generate_silver_bracket_with_results
            bracket_data = generate_bracket_with_results(pools, standings, bracket_results)
            if constraints.get('silver_bracket_enabled'):
                silver_bracket_data = generate_silver_bracket_with_results(pools, standings, bracket_results)
    
    print_settings = load_print_settings()
    
    return render_template('print.html',
                          pools=pools,
                          courts=courts,
                          constraints=constraints,
                          schedule=schedule_data,
                          standings=standings,
                          bracket_data=bracket_data,
                          silver_bracket_data=silver_bracket_data,
                          print_settings=print_settings)


@app.route('/api/print-settings', methods=['POST'])
def update_print_settings():
    """API endpoint to update print settings."""
    data = request.get_json()
    settings = load_print_settings()
    
    if 'title' in data:
        settings['title'] = data['title']
    if 'subtitle' in data:
        settings['subtitle'] = data['subtitle']
    
    save_print_settings(settings)
    return jsonify({'success': True})


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
    silver_bracket_enabled = constraints.get('silver_bracket_enabled', False)
    
    # Generate gold bracket with results applied
    from core.elimination import generate_bracket_with_results, generate_silver_bracket_with_results
    bracket_data = generate_bracket_with_results(pools, standings, bracket_results)
    
    # Generate silver bracket if enabled
    silver_bracket_data = None
    if silver_bracket_enabled:
        silver_bracket_data = generate_silver_bracket_with_results(pools, standings, bracket_results)
    
    return render_template('sbracket.html', bracket_data=bracket_data, error=None, 
                          bracket_results=bracket_results, scoring_format=scoring_format,
                          silver_bracket_data=silver_bracket_data, silver_bracket_enabled=silver_bracket_enabled)


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
                    
                    # Generate gold bracket elimination matches
                    elimination_matches = generate_elimination_matches_for_scheduling(pools)
                    
                    # Add silver bracket matches if enabled
                    silver_bracket_enabled = constraints_data.get('silver_bracket_enabled', False)
                    if silver_bracket_enabled:
                        from core.elimination import generate_silver_matches_for_scheduling
                        silver_matches = generate_silver_matches_for_scheduling(pools)
                        elimination_matches.extend(silver_matches)
                        
                        # Add silver bracket teams to the teams list
                        from core.elimination import seed_silver_bracket_teams
                        silver_teams = seed_silver_bracket_teams(pools)
                        for team_name, seed, pool_name in silver_teams:
                            teams.append(Team(name=team_name, attributes={'pool': pool_name, 'seed': seed, 'bracket': 'silver'}))
                    
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
    silver_bracket_enabled = constraints.get('silver_bracket_enabled', False)
    
    # Generate gold bracket with results applied
    from core.double_elimination import generate_double_bracket_with_results, generate_silver_double_bracket_with_results
    bracket_data = generate_double_bracket_with_results(pools, standings, bracket_results)
    
    # Generate silver bracket if enabled
    silver_bracket_data = None
    if silver_bracket_enabled:
        silver_bracket_data = generate_silver_double_bracket_with_results(pools, standings, bracket_results)
    
    return render_template('dbracket.html', bracket_data=bracket_data, error=None,
                          bracket_results=bracket_results, scoring_format=scoring_format,
                          silver_bracket_data=silver_bracket_data, silver_bracket_enabled=silver_bracket_enabled)


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
                    
                    # Add silver bracket matches if enabled
                    silver_bracket_enabled = constraints_data.get('silver_bracket_enabled', False)
                    if silver_bracket_enabled:
                        from core.double_elimination import generate_silver_double_matches_for_scheduling
                        silver_matches = generate_silver_double_matches_for_scheduling(pools)
                        elimination_matches.extend(silver_matches)
                        
                        # Add silver bracket teams to the teams list
                        from core.elimination import seed_silver_bracket_teams
                        silver_teams = seed_silver_bracket_teams(pools)
                        for team_name, seed, pool_name in silver_teams:
                            teams.append(Team(name=team_name, attributes={'pool': pool_name, 'seed': seed, 'bracket': 'silver'}))
                    
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
