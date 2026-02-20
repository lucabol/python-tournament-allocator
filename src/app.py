"""
Flask web application for Tournament Allocator.
"""
import os
import csv
import glob
import hmac
import io
import re
import shutil
import logging
import yaml
import time
import zipfile
from datetime import datetime, timedelta
from functools import wraps
from filelock import FileLock
from flask import Flask, render_template, request, jsonify, redirect, url_for, flash, Response, stream_with_context, send_file, session, g, abort
from core.models import Team, Court
from core.allocation import AllocationManager
from core.elimination import get_elimination_bracket_display, generate_elimination_matches_for_scheduling, generate_all_single_bracket_matches_for_scheduling
from core.double_elimination import get_double_elimination_bracket_display, generate_double_elimination_matches_for_scheduling, generate_all_bracket_matches_for_scheduling, generate_bracket_execution_order, generate_silver_bracket_execution_order
from generate_matches import generate_pool_play_matches, generate_elimination_matches

app = Flask(__name__)


def _get_or_create_secret_key() -> bytes:
    """Get SECRET_KEY from env, or generate and persist to file."""
    env_key = os.environ.get('SECRET_KEY')
    if env_key:
        return env_key.encode() if isinstance(env_key, str) else env_key
    key_file = os.path.join(DATA_DIR, '.secret_key')
    if os.path.exists(key_file):
        with open(key_file, 'rb') as f:
            return f.read()
    key = os.urandom(24)
    os.makedirs(os.path.dirname(key_file), exist_ok=True)
    with open(key_file, 'wb') as f:
        f.write(key)
    return key


BASE_DIR = os.path.dirname(os.path.dirname(__file__))
DATA_DIR = os.environ.get('TOURNAMENT_DATA_DIR', os.path.join(BASE_DIR, 'data'))

app.secret_key = _get_or_create_secret_key()
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=3650)

# Paths to data files (legacy constants — kept for migration; use _file_path() in routes)
TEAMS_FILE = os.path.join(DATA_DIR, 'teams.yaml')
COURTS_FILE = os.path.join(DATA_DIR, 'courts.csv')
CONSTRAINTS_FILE = os.path.join(DATA_DIR, 'constraints.yaml')
RESULTS_FILE = os.path.join(DATA_DIR, 'results.yaml')
SCHEDULE_FILE = os.path.join(DATA_DIR, 'schedule.yaml')
PRINT_SETTINGS_FILE = os.path.join(DATA_DIR, 'print_settings.yaml')
LOGO_FILE_PREFIX = os.path.join(DATA_DIR, 'logo')
DEFAULT_LOGO_URL = 'https://montgobvc.com/wp-content/uploads/2024/02/LOGO-MBVC-001.png'
ALLOWED_LOGO_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.svg', '.webp'}
_data_lock = FileLock(os.path.join(DATA_DIR, '.lock'), timeout=10)
MAX_UPLOAD_SIZE = 10 * 1024 * 1024  # 10 MB
MAX_SITE_UPLOAD_SIZE = 50 * 1024 * 1024  # 50 MB for site-wide exports
MAX_UNCOMPRESSED_SIZE = 50 * 1024 * 1024  # 50 MB
MAX_ZIP_FILES = 20
# Directories to skip during export
SITE_EXPORT_SKIP_DIRS = {'__pycache__'}
# File extensions to skip during export
SITE_EXPORT_SKIP_EXTS = {'.pyc', '.lock'}

# Files eligible for tournament export/import (legacy — use _get_exportable_files() in routes)
EXPORTABLE_FILES = {
    'teams.yaml': TEAMS_FILE,
    'courts.csv': COURTS_FILE,
    'constraints.yaml': CONSTRAINTS_FILE,
    'results.yaml': RESULTS_FILE,
    'schedule.yaml': SCHEDULE_FILE,
    'print_settings.yaml': PRINT_SETTINGS_FILE,
}
ALLOWED_IMPORT_NAMES = set(EXPORTABLE_FILES.keys())

# Multi-tournament support
TOURNAMENTS_FILE = os.path.join(DATA_DIR, 'tournaments.yaml')
TOURNAMENTS_DIR = os.path.join(DATA_DIR, 'tournaments')
USERS_FILE = os.path.join(DATA_DIR, 'users.yaml')
USERS_DIR = os.path.join(DATA_DIR, 'users')

# Rate limiting for player score submissions
# Structure: {(ip, username, slug): [(timestamp, timestamp, ...)]}
_rate_limit_store = {}


def load_users() -> list:
    """Load user registry from YAML."""
    if not os.path.exists(USERS_FILE):
        return []
    try:
        with open(USERS_FILE, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
        return data.get('users', []) if data else []
    except Exception as e:
        app.logger.warning(f'Failed to parse {USERS_FILE}: {e}')
        return []


def save_users(users: list):
    """Save user registry to YAML."""
    os.makedirs(DATA_DIR, exist_ok=True)
    with open(USERS_FILE, 'w', encoding='utf-8') as f:
        yaml.dump({'users': users}, f, default_flow_style=False)


def create_user(username: str, password: str) -> tuple:
    """Create a new user. Returns (success, message)."""
    from werkzeug.security import generate_password_hash
    username = username.lower().strip()
    if not re.match(r'^[a-z0-9][a-z0-9-]*$', username) or len(username) < 2:
        return False, 'Username must be at least 2 characters: letters, numbers, hyphens.'
    if len(password) < 4:
        return False, 'Password must be at least 4 characters.'
    with _data_lock:
        users = load_users()
        if any(u['username'] == username for u in users):
            return False, 'Username already taken.'
        users.append({
            'username': username,
            'password_hash': generate_password_hash(password),
            'created': datetime.now().isoformat()
        })
        save_users(users)
    # Create user data directory with a default tournament
    user_dir = os.path.join(USERS_DIR, username)
    user_tournaments_dir = os.path.join(user_dir, 'tournaments')
    default_dir = os.path.join(user_tournaments_dir, 'default')
    os.makedirs(default_dir, exist_ok=True)
    # Seed default tournament files
    default_constraints = get_default_constraints()
    default_constraints['tournament_name'] = 'Default Tournament'
    with open(os.path.join(default_dir, 'constraints.yaml'), 'w', encoding='utf-8') as f:
        yaml.dump(default_constraints, f, default_flow_style=False)
    with open(os.path.join(default_dir, 'teams.yaml'), 'w', encoding='utf-8') as f:
        f.write('')
    with open(os.path.join(default_dir, 'courts.csv'), 'w', encoding='utf-8', newline='') as f:
        f.write('court_name,start_time,end_time\n')
    # Create user's tournament registry
    user_reg = os.path.join(user_dir, 'tournaments.yaml')
    with open(user_reg, 'w', encoding='utf-8') as f:
        yaml.dump({
            'active': 'default',
            'tournaments': [{'slug': 'default', 'name': 'Default Tournament',
                             'created': datetime.now().isoformat()}]
        }, f, default_flow_style=False)
    return True, 'Account created successfully.'


def authenticate_user(username: str, password: str) -> bool:
    """Check username/password. Returns True if valid."""
    from werkzeug.security import check_password_hash
    users = load_users()
    for u in users:
        if u['username'] == username.lower().strip():
            return check_password_hash(u['password_hash'], password)
    return False


def login_required(f):
    """Redirect to login page if user not authenticated."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user' not in session:
            return redirect(url_for('login_page'))
        return f(*args, **kwargs)
    return decorated_function


def require_backup_key(f):
    """Require valid BACKUP_API_KEY in Authorization header."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        expected_key = os.environ.get('BACKUP_API_KEY')
        if not expected_key:
            return jsonify({'error': 'Server not configured for backup operations'}), 500
        
        auth_header = request.headers.get('Authorization', '')
        if not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Missing or invalid Authorization header'}), 401
        
        provided_key = auth_header[7:]  # Strip "Bearer "
        if not hmac.compare_digest(expected_key, provided_key):
            return jsonify({'error': 'Invalid API key'}), 401
        
        return f(*args, **kwargs)
    return decorated_function





def _slugify(name: str) -> str:
    """Convert tournament name to filesystem-safe slug."""
    slug = name.lower().strip()
    slug = re.sub(r'[^a-z0-9\s-]', '', slug)
    slug = re.sub(r'[\s-]+', '-', slug)
    slug = slug.strip('-')
    return slug or 'tournament'


def _tournament_dir(slug: str = None) -> str:
    """Return data directory for a tournament. Uses active tournament if slug not given."""
    if slug:
        tournaments_dir = getattr(g, 'user_tournaments_dir', TOURNAMENTS_DIR)
        return os.path.join(tournaments_dir, slug)
    try:
        return g.data_dir
    except (AttributeError, RuntimeError):
        return DATA_DIR


def _file_path(filename: str) -> str:
    """Return full path to a data file in the active tournament."""
    return os.path.join(_tournament_dir(), filename)


def load_tournaments() -> dict:
    """Load tournaments registry for the current user."""
    tournaments_file = getattr(g, 'user_tournaments_file', TOURNAMENTS_FILE)
    if not os.path.exists(tournaments_file):
        return {'active': None, 'tournaments': []}
    try:
        with open(tournaments_file, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
            return data if data else {'active': None, 'tournaments': []}
    except Exception as e:
        app.logger.warning(f'Failed to parse {tournaments_file}: {e}')
        return {'active': None, 'tournaments': []}


def save_tournaments(data: dict):
    """Save tournaments registry for the current user."""
    tournaments_file = getattr(g, 'user_tournaments_file', TOURNAMENTS_FILE)
    os.makedirs(os.path.dirname(tournaments_file), exist_ok=True)
    with open(tournaments_file, 'w', encoding='utf-8') as f:
        yaml.dump(data, f, default_flow_style=False)


def _get_exportable_files() -> dict:
    """Return mapping of filenames to paths for the active tournament."""
    return {
        'teams.yaml': _file_path('teams.yaml'),
        'courts.csv': _file_path('courts.csv'),
        'constraints.yaml': _file_path('constraints.yaml'),
        'results.yaml': _file_path('results.yaml'),
        'schedule.yaml': _file_path('schedule.yaml'),
        'print_settings.yaml': _file_path('print_settings.yaml'),
        'awards.yaml': _file_path('awards.yaml'),
    }


def ensure_tournament_structure():
    """Ensure user tournament structure directories exist."""
    os.makedirs(TOURNAMENTS_DIR, exist_ok=True)


def _create_default_tournament_files(tournament_dir: str, tournament_name: str = 'Default Tournament'):
    """Create minimal tournament files. Called before get_default_constraints() is available."""
    os.makedirs(tournament_dir, exist_ok=True)
    
    # Minimal constraints file
    constraints = {
        'tournament_name': tournament_name,
        'match_duration_minutes': 30,
        'days_number': 1,
        'min_break_between_matches_minutes': 0,
        'day_end_time_limit': '22:00',
        'bracket_type': 'double',
        'scoring_format': 'single_set',
        'pool_in_same_court': True,
        'silver_bracket_enabled': True,
        'pool_to_bracket_delay_minutes': 0,
        'show_test_buttons': False
    }
    with open(os.path.join(tournament_dir, 'constraints.yaml'), 'w', encoding='utf-8') as f:
        yaml.dump(constraints, f, default_flow_style=False)
    
    # Empty files
    with open(os.path.join(tournament_dir, 'teams.yaml'), 'w', encoding='utf-8') as f:
        f.write('')
    with open(os.path.join(tournament_dir, 'courts.csv'), 'w', encoding='utf-8', newline='') as f:
        f.write('court_name,start_time,end_time\n')





ensure_tournament_structure()


def _find_logo_file():
    """Find uploaded logo file in data directory (any extension)."""
    prefix = os.path.join(_tournament_dir(), 'logo')
    matches = glob.glob(prefix + '.*')
    return matches[0] if matches else None


def _delete_logo_file():
    """Delete any uploaded logo file."""
    existing = _find_logo_file()
    if existing:
        os.remove(existing)


def load_print_settings():
    """Load print settings from YAML file."""
    defaults = {
        'title': 'Tournament Summary',
        'subtitle': 'January 2026'
    }
    path = _file_path('print_settings.yaml')
    if not os.path.exists(path):
        return defaults
    with open(path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
        if not data:
            return defaults
        return {**defaults, **data}


def load_teams():
    """Load teams from YAML file."""
    path = _file_path('teams.yaml')
    if not os.path.exists(path):
        return {}
    with open(path, 'r', encoding='utf-8') as f:
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
    with open(_file_path('teams.yaml'), 'w', encoding='utf-8') as f:
        yaml.dump(pools_data, f, default_flow_style=False)


def load_courts():
    """Load courts from CSV file."""
    courts = []
    path = _file_path('courts.csv')
    if not os.path.exists(path):
        return courts
    with open(path, 'r', encoding='utf-8') as f:
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
    with open(_file_path('courts.csv'), 'w', encoding='utf-8', newline='') as f:
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
    path = _file_path('constraints.yaml')
    if not os.path.exists(path):
        return defaults
    with open(path, 'r', encoding='utf-8') as f:
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
    with open(_file_path('constraints.yaml'), 'w', encoding='utf-8') as f:
        yaml.dump(constraints, f, default_flow_style=False)


def load_results():
    """Load match results from YAML file."""
    path = _file_path('results.yaml')
    if not os.path.exists(path):
        return {'pool_play': {}, 'bracket': {}, 'bracket_type': 'single'}
    with open(path, 'r', encoding='utf-8') as f:
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
    with open(_file_path('results.yaml'), 'w', encoding='utf-8') as f:
        yaml.dump(results, f, default_flow_style=False)


def load_awards() -> dict:
    """Load awards from YAML file."""
    path = _file_path('awards.yaml')
    if not os.path.exists(path):
        return {'awards': []}
    with open(path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
        if not data:
            return {'awards': []}
        if 'awards' not in data:
            data['awards'] = []
        return data


def save_awards(data: dict):
    """Save awards to YAML file."""
    with open(_file_path('awards.yaml'), 'w', encoding='utf-8') as f:
        yaml.dump(data, f, default_flow_style=False)


def load_messages():
    """Load messages from YAML file."""
    path = _file_path('messages.yaml')
    if not os.path.exists(path):
        return []
    with open(path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
        if not data or 'messages' not in data:
            return []
        return data['messages']


def save_messages(messages):
    """Save messages to YAML file."""
    with open(_file_path('messages.yaml'), 'w', encoding='utf-8') as f:
        yaml.dump({'messages': messages}, f, default_flow_style=False)


def load_registrations():
    """Load team registrations from YAML file."""
    path = _file_path('registrations.yaml')
    if not os.path.exists(path):
        return {'registration_open': False, 'teams': []}
    with open(path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
        if not data:
            return {'registration_open': False, 'teams': []}
        if 'registration_open' not in data:
            data['registration_open'] = False
        if 'teams' not in data:
            data['teams'] = []
        # Ensure all teams have paid field (default to False)
        for team in data['teams']:
            if 'paid' not in team:
                team['paid'] = False
        return data


def save_registrations(registrations):
    """Save team registrations to YAML file."""
    with open(_file_path('registrations.yaml'), 'w', encoding='utf-8') as f:
        yaml.dump(registrations, f, default_flow_style=False)


def load_pending_results(data_dir: str = None):
    """Load pending score reports from YAML file.
    
    Auto-prunes dismissed entries older than 24 hours.
    
    Args:
        data_dir: Optional directory path. If provided, uses that instead of _file_path().
    
    Returns:
        List of pending result dicts with keys: match_key, team1, team2, pool, sets, timestamp, status
    """
    if data_dir:
        path = os.path.join(data_dir, 'pending_results.yaml')
    else:
        path = _file_path('pending_results.yaml')
    
    if not os.path.exists(path):
        return []
    
    with open(path, 'r', encoding='utf-8') as f:
        data = yaml.safe_load(f)
        if not data or 'pending_results' not in data:
            return []
        
        results = data['pending_results']
        if not isinstance(results, list):
            return []
        
        # Prune dismissed entries older than 24h
        cutoff = datetime.now() - timedelta(hours=24)
        filtered = []
        for r in results:
            if r.get('status') == 'dismissed':
                timestamp_str = r.get('timestamp', '')
                try:
                    ts = datetime.fromisoformat(timestamp_str)
                    if ts >= cutoff:
                        filtered.append(r)
                except (ValueError, TypeError):
                    # Keep if timestamp is invalid (safer than dropping)
                    filtered.append(r)
            else:
                filtered.append(r)
        
        # Save back if we pruned anything
        if len(filtered) < len(results):
            save_pending_results(filtered, data_dir)
        
        return filtered


def save_pending_results(results: list, data_dir: str = None):
    """Save pending score reports to YAML file.
    
    Args:
        results: List of pending result dicts
        data_dir: Optional directory path. If provided, uses that instead of _file_path().
    """
    if data_dir:
        path = os.path.join(data_dir, 'pending_results.yaml')
    else:
        path = _file_path('pending_results.yaml')
    
    with open(path, 'w', encoding='utf-8') as f:
        yaml.dump({'pending_results': results}, f, default_flow_style=False)


def check_rate_limit(ip: str, username: str, slug: str, max_per_hour: int = 30) -> bool:
    """Check if IP has exceeded rate limit for a tournament.
    
    Args:
        ip: Client IP address
        username: Tournament owner username
        slug: Tournament slug
        max_per_hour: Maximum submissions allowed per hour
    
    Returns:
        True if rate limit NOT exceeded, False if exceeded
    """
    key = (ip, username, slug)
    now = time.time()
    cutoff = now - 3600  # 1 hour ago
    
    # Get existing timestamps for this key
    timestamps = _rate_limit_store.get(key, [])
    
    # Filter to only timestamps within the last hour
    recent = [ts for ts in timestamps if ts > cutoff]
    
    # Check if limit exceeded
    if len(recent) >= max_per_hour:
        return False
    
    # Add current timestamp
    recent.append(now)
    _rate_limit_store[key] = recent
    
    return True


def load_schedule():
    """Load saved schedule from YAML file."""
    path = _file_path('schedule.yaml')
    if not os.path.exists(path):
        return None, None
    with open(path, 'r', encoding='utf-8') as f:
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
    with open(_file_path('schedule.yaml'), 'w', encoding='utf-8') as f:
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


def enrich_schedule_with_results(schedule_data, results, pools, standings):
    """
    Enrich schedule data with match results for live display.
    
    For pool matches: adds result data (scores, winner/loser)
    For bracket matches: resolves placeholders to actual team names
    
    Returns: enriched schedule_data (modified in place)
    """
    if not schedule_data:
        return schedule_data
    
    pool_results = results.get('pool_play', {})
    bracket_results = results.get('bracket', {})
    
    # Build lookup for bracket match results
    # Since bracket results are now stored with match_code keys (e.g., "W1-M1", "GF"),
    # and schedule matches already have match_code, we can look them up directly.
    # We still support the old bracket_key format for backward compatibility.
    resolved_teams = {}  # match_code -> {'winner': team, 'loser': team, 'sets': [...]}
    
    # Direct pass-through: bracket_results keys are already match_codes or old format
    for key, result in bracket_results.items():
        if result.get('completed'):
            # If key is already a match_code (W1-M1, L2-M3, GF, BR), use it directly
            # If key is old format (winners_Winners Quarterfinal_1), we'll fall back to it
            resolved_teams[key] = {
                'winner': result.get('winner'),
                'loser': result.get('loser'),
                'sets': result.get('sets', [])
            }
    
    # Process each day in the schedule
    for day, day_data in schedule_data.items():
        if day == '_time_slots':
            continue
            
        for court_name, court_data in day_data.items():
            if court_name == '_time_slots':
                continue
            
            matches = court_data.get('matches', [])
            for match in matches:
                teams = match.get('teams', [])
                if len(teams) < 2:
                    continue
                
                is_bracket = match.get('is_bracket', False)
                
                if is_bracket:
                    # Resolve bracket placeholders
                    new_teams = list(teams)
                    for i, team in enumerate(teams):
                        if isinstance(team, str):
                            # Check if this is a pool ranking placeholder like "#1 Pool A"
                            if team.startswith('#') and ' Pool ' in team:
                                # Parse "#1 Pool A" -> rank=1, pool="Pool A"
                                import re
                                match_obj = re.match(r'#(\d+) (Pool .+)', team)
                                if match_obj:
                                    rank = int(match_obj.group(1))
                                    pool_name = match_obj.group(2)
                                    if pool_name in standings and len(standings[pool_name]) >= rank:
                                        actual_team = standings[pool_name][rank - 1]['team']
                                        new_teams[i] = actual_team
                                        match['is_placeholder'] = False
                            # Check for special Grand Final placeholders
                            elif team == 'Winner of Winners Bracket':
                                # Find the winner of the last winners bracket match (W3-M1 for 8 teams)
                                for code in ['W3-M1', 'W2-M1', 'W1-M1']:
                                    if code in resolved_teams and resolved_teams[code].get('winner'):
                                        new_teams[i] = resolved_teams[code]['winner']
                                        match['is_placeholder'] = False
                                        break
                            elif team == 'Winner of Losers Bracket':
                                # Find the winner of the last losers bracket match (L4-M1 for 8 teams)
                                for code in ['L4-M1', 'L3-M1', 'L2-M1']:
                                    if code in resolved_teams and resolved_teams[code].get('winner'):
                                        new_teams[i] = resolved_teams[code]['winner']
                                        match['is_placeholder'] = False
                                        break
                            elif team == 'Winner of SWinners Bracket':
                                for code in ['SW3-M1', 'SW2-M1', 'SW1-M1']:
                                    if code in resolved_teams and resolved_teams[code].get('winner'):
                                        new_teams[i] = resolved_teams[code]['winner']
                                        match['is_placeholder'] = False
                                        break
                            elif team == 'Winner of SLosers Bracket':
                                for code in ['SL4-M1', 'SL3-M1', 'SL2-M1']:
                                    if code in resolved_teams and resolved_teams[code].get('winner'):
                                        new_teams[i] = resolved_teams[code]['winner']
                                        match['is_placeholder'] = False
                                        break
                            # Check if this is a placeholder like "Winner W1-M1"
                            elif team.startswith('Winner '):
                                ref_code = team[7:]  # Remove "Winner " prefix
                                if ref_code in resolved_teams:
                                    new_teams[i] = resolved_teams[ref_code]['winner']
                                    match['is_placeholder'] = False
                            elif team.startswith('Loser '):
                                ref_code = team[6:]  # Remove "Loser " prefix
                                if ref_code in resolved_teams:
                                    new_teams[i] = resolved_teams[ref_code]['loser']
                                    match['is_placeholder'] = False
                    
                    match['teams'] = new_teams
                    
                    # Check if this bracket match has results by match_code
                    match_code = match.get('match_code', '')
                    if match_code in resolved_teams:
                        match['result'] = {
                            'winner': resolved_teams[match_code]['winner'],
                            'loser': resolved_teams[match_code]['loser'],
                            'sets': resolved_teams[match_code].get('sets', []),
                            'completed': True
                        }
                else:
                    # Pool match - look up result
                    pool = match.get('pool', '')
                    match_key = get_match_key(teams[0], teams[1], pool)
                    
                    if match_key in pool_results:
                        result = pool_results[match_key]
                        match['result'] = {
                            'winner': result.get('winner'),
                            'loser': result.get('loser'),
                            'sets': result.get('sets', []),
                            'completed': result.get('completed', False)
                        }
            
            # Rebuild time_to_match to reflect enriched matches
            court_data['time_to_match'] = {m['start_time']: m for m in matches}
    
    return schedule_data


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


def determine_tournament_phase(schedule_data, results, bracket_data):
    """Determine the current phase of the tournament.

    Args:
        schedule_data: The schedule dict or None.
        results: The results dict with 'pool_play' and 'bracket' keys.
        bracket_data: The bracket data dict or None.

    Returns:
        One of: 'setup', 'pool_play', 'bracket', 'complete'.
    """
    if not schedule_data:
        return 'setup'

    # Check if champion is determined
    if bracket_data and bracket_data.get('champion'):
        return 'complete'

    # Check if any bracket results exist
    bracket_results = results.get('bracket', {})
    if any(r.get('completed') for r in bracket_results.values()):
        return 'bracket'

    # Check pool play completion
    pool_results = results.get('pool_play', {})
    completed_pool = sum(1 for r in pool_results.values() if r.get('completed'))
    if completed_pool > 0:
        # Count total pool matches from schedule
        total_pool = 0
        for day, day_data in schedule_data.items():
            if day == '_time_slots' or day == 'Bracket Phase':
                continue
            for court_name, court_data in day_data.items():
                if court_name == '_time_slots':
                    continue
                for match in court_data.get('matches', []):
                    if not match.get('is_bracket', False):
                        total_pool += 1
        if total_pool > 0 and completed_pool >= total_pool:
            return 'bracket'
        return 'pool_play'

    return 'pool_play'


def calculate_match_stats(results):
    """Calculate aggregate statistics across all completed matches.

    Args:
        results: The results dict with 'pool_play' and 'bracket' keys.

    Returns:
        Dict with total_points, closest_match, biggest_blowout, matches_completed,
        average_margin, or None if no completed matches.
    """
    all_matches = []

    for section in ('pool_play', 'bracket'):
        for match_key, result in results.get(section, {}).items():
            if not result.get('completed'):
                continue
            # Skip bracket results duplicated in pool_play section
            if section == 'pool_play' and (
                match_key.endswith('_Bracket') or match_key.endswith('_Silver Bracket')
            ):
                continue
            sets = result.get('sets', [])
            if not sets:
                continue
            total_t1 = sum(s[0] for s in sets if len(s) >= 2 and s[0] is not None)
            total_t2 = sum(s[1] for s in sets if len(s) >= 2 and s[1] is not None)
            margin = abs(total_t1 - total_t2)
            winner = result.get('winner', '?')
            loser_name = result.get('loser', '')
            if not loser_name:
                t1 = result.get('team1', '?')
                t2 = result.get('team2', '?')
                loser_name = t2 if winner == t1 else t1
            score_line = ' / '.join(f'{s[0]}-{s[1]}' for s in sets if len(s) >= 2)
            all_matches.append({
                'winner': winner,
                'loser': loser_name,
                'margin': margin,
                'total_points': total_t1 + total_t2,
                'score_line': score_line,
            })

    if not all_matches:
        return None

    closest = min(all_matches, key=lambda m: m['margin'])
    biggest = max(all_matches, key=lambda m: m['margin'])
    total_pts = sum(m['total_points'] for m in all_matches)
    avg_margin = sum(m['margin'] for m in all_matches) / len(all_matches)

    return {
        'total_points': total_pts,
        'matches_completed': len(all_matches),
        'average_margin': round(avg_margin, 1),
        'closest_match': {
            'winner': closest['winner'],
            'loser': closest['loser'],
            'score': closest['score_line'],
            'margin': closest['margin'],
        },
        'biggest_blowout': {
            'winner': biggest['winner'],
            'loser': biggest['loser'],
            'score': biggest['score_line'],
            'margin': biggest['margin'],
        },
    }


def get_default_constraints():
    """Return default constraints."""
    return {
        'match_duration_minutes': 25,
        'days_number': 1,
        'min_break_between_matches_minutes': 5,
        'time_slot_increment_minutes': 15,
        'day_end_time_limit': '02:00',
        'bracket_type': 'double',
        'scoring_format': 'single_set',
        'pool_in_same_court': True,
        'silver_bracket_enabled': True,
        'show_test_buttons': False,
        'pool_to_bracket_delay_minutes': 120,
        'club_name': 'Montgó Beach Volley Club',
        'tournament_name': 'Summer Tournament 2026',
        'tournament_date': 'July 2026',
        'team_specific_constraints': [],

        'general_constraints': [],
        'tournament_settings': {
            'type': 'pool_play',
            'advancement_rules': {
                'top_teams_per_pool_to_advance': 2
            }
        }
    }


@app.before_request
def set_active_tournament():
    """Set g.data_dir to the active tournament's data directory."""
    # Skip auth for static files, login, register, and API key authenticated endpoints
    if request.endpoint in ('static', 'login_page', 'register_page', 'public_register',
                            'public_live', 'api_public_live_html', 'api_public_live_stream',
                            'api_admin_export', 'api_admin_import', None):
        return

    # Ensure tournament structure exists (idempotent)
    ensure_tournament_structure()

    # Require login for all other endpoints except logout
    if 'user' not in session:
        if request.endpoint != 'logout':
            return redirect(url_for('login_page'))
        return

    username = session['user']
    user_dir = os.path.join(USERS_DIR, username)
    g.user_dir = user_dir
    g.user_tournaments_file = os.path.join(user_dir, 'tournaments.yaml')
    g.user_tournaments_dir = os.path.join(user_dir, 'tournaments')

    # Ensure user directory exists
    os.makedirs(g.user_tournaments_dir, exist_ok=True)

    tournaments = load_tournaments()
    active_slug = session.get('active_tournament', tournaments.get('active'))

    # Auto-activate first tournament if none is active but tournaments exist
    if not active_slug and tournaments.get('tournaments'):
        first_slug = tournaments['tournaments'][0]['slug']
        tournament_path = os.path.join(g.user_tournaments_dir, first_slug)
        if os.path.isdir(tournament_path):
            active_slug = first_slug
            tournaments['active'] = first_slug
            save_tournaments(tournaments)
            session['active_tournament'] = first_slug

    if active_slug:
        tournament_path = os.path.join(g.user_tournaments_dir, active_slug)
        if os.path.isdir(tournament_path):
            g.data_dir = tournament_path
            g.active_tournament = active_slug
            for t in tournaments.get('tournaments', []):
                if t['slug'] == active_slug:
                    g.tournament_name = t.get('name', active_slug)
                    break
            else:
                g.tournament_name = active_slug
            return

    g.data_dir = user_dir
    g.active_tournament = None
    g.tournament_name = None

    # Guard: redirect to tournaments page if user has no tournaments
    tournament_endpoints = {'tournaments', 'api_create_tournament', 'api_delete_tournament',
                            'api_clone_tournament',
                            'api_switch_tournament', 'logout', 'api_export_tournament',
                            'api_import_tournament', 'api_export_user', 'api_import_user',
                            'api_delete_account', 'awards', 'insta'}
    if request.endpoint not in tournament_endpoints:
        flash('Please create a tournament first.', 'info')
        return redirect(url_for('tournaments'))


@app.context_processor
def inject_tournament_context():
    """Make tournament and user info available to all templates."""
    show_test_buttons = False
    unread_messages_count = 0
    try:
        constraints = load_constraints()
        show_test_buttons = constraints.get('show_test_buttons', False)
    except Exception:
        pass
    
    # Count unread messages for logged-in users
    if 'user' in session and hasattr(g, 'data_dir'):
        try:
            messages_list = load_messages()
            unread_messages_count = sum(1 for m in messages_list if m.get('status') == 'new')
        except Exception:
            pass
    
    return {
        'active_tournament': getattr(g, 'active_tournament', None),
        'tournament_name': getattr(g, 'tournament_name', None),
        'current_user': session.get('user'),
        'show_test_buttons': show_test_buttons,
        'unread_messages_count': unread_messages_count,
    }


@app.route('/login', methods=['GET', 'POST'])
def login_page():
    """Login form and authentication."""
    if 'user' in session:
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form.get('username', '')
        password = request.form.get('password', '')
        if authenticate_user(username, password):
            session['user'] = username.lower().strip()
            session.permanent = True
            return redirect(url_for('index'))
        flash('Invalid username or password.', 'error')
    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register_page():
    """Registration form and user creation."""
    if 'user' in session:
        return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form.get('username', '')
        password = request.form.get('password', '')
        confirm = request.form.get('confirm_password', '')
        if password != confirm:
            flash('Passwords do not match.', 'error')
        else:
            ok, msg = create_user(username, password)
            if ok:
                session['user'] = username.lower().strip()
                session.permanent = True
                flash(msg, 'success')
                return redirect(url_for('index'))
            flash(msg, 'error')
    return render_template('register.html')


@app.route('/logout')
def logout():
    """Clear session and redirect to login."""
    session.clear()
    flash('Logged out.', 'success')
    return redirect(url_for('login_page'))


@app.route('/api/delete-account', methods=['POST'])
@login_required
def api_delete_account():
    """Delete the currently logged-in user's account and all their data."""
    username = session.get('user')

    with _data_lock:
        users = load_users()
        users = [u for u in users if u['username'] != username]
        save_users(users)

    shutil.rmtree(os.path.join(USERS_DIR, username), ignore_errors=True)
    session.clear()
    flash('Your account and all data have been permanently deleted.', 'success')
    return jsonify({'success': True, 'redirect': url_for('login_page')})


@app.route('/')
def index():
    """Main page showing tournament overview."""
    pools = load_teams()
    courts = load_courts()
    constraints = load_constraints()
    results = load_results()
    schedule_data, schedule_stats = load_schedule()

    # Count teams
    total_teams = sum(len(pool_data['teams']) for pool_data in pools.values()) if pools else 0

    # Calculate standings
    standings = calculate_pool_standings(pools, results) if pools else {}

    # Load bracket data for champion / status
    bracket_data = None
    silver_bracket_data = None
    if pools:
        bracket_type = constraints.get('bracket_type', 'double')
        bracket_results = results.get('bracket', {})
        try:
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
        except Exception:
            pass  # Bracket data is optional for dashboard

    # Determine tournament phase
    phase = determine_tournament_phase(schedule_data, results, bracket_data)

    # Match progress — filter out bracket results that were also saved in pool_play
    pool_completed = sum(
        1 for key, r in results.get('pool_play', {}).items()
        if r.get('completed') and not key.endswith('_Bracket') and not key.endswith('_Silver Bracket')
    )
    bracket_completed = sum(1 for r in results.get('bracket', {}).values() if r.get('completed'))

    # Count pool-only vs bracket-only totals from the schedule
    pool_total = 0
    bracket_total = 0
    if schedule_data:
        for day_name, day_data in schedule_data.items():
            if day_name == '_time_slots':
                continue
            for court_name, court_data in day_data.items():
                if court_name == '_time_slots':
                    continue
                for match in court_data.get('matches', []):
                    if match.get('is_bracket'):
                        bracket_total += 1
                    else:
                        pool_total += 1

    # Aggregate match stats
    match_stats = calculate_match_stats(results)

    return render_template('index.html',
                         pools=pools,
                         courts=courts,
                         constraints=constraints,
                         total_teams=total_teams,
                         standings=standings,
                         schedule_stats=schedule_stats,
                         bracket_data=bracket_data,
                         silver_bracket_data=silver_bracket_data,
                         phase=phase,
                         pool_completed=pool_completed,
                         bracket_completed=bracket_completed,
                         pool_total=pool_total,
                         bracket_total=bracket_total,
                         match_stats=match_stats)


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
                        # Normalize format and extract registrations
                        normalized = {}
                        registrations = load_registrations()
                        
                        for pool_name, pool_data in data.items():
                            if isinstance(pool_data, list):
                                # Check if list contains dicts with team info or strings
                                teams_list = []
                                for item in pool_data:
                                    if isinstance(item, dict):
                                        # Team object with name, email, phone
                                        team_name = item.get('name', '').strip()
                                        if team_name:
                                            teams_list.append(team_name)
                                            # Store email/phone in registrations
                                            email = item.get('email', '').strip()
                                            phone = item.get('phone', '').strip()
                                            if email or phone:
                                                # Check if registration exists, update or create
                                                existing_reg = None
                                                for reg in registrations['teams']:
                                                    if reg['team_name'] == team_name:
                                                        existing_reg = reg
                                                        break
                                                
                                                if existing_reg:
                                                    if email:
                                                        existing_reg['email'] = email
                                                    if phone:
                                                        existing_reg['phone'] = phone
                                                    existing_reg['status'] = 'assigned'
                                                    existing_reg['assigned_pool'] = pool_name
                                                    # Preserve paid status if not already set
                                                    if 'paid' not in existing_reg:
                                                        existing_reg['paid'] = False
                                                else:
                                                    registrations['teams'].append({
                                                        'team_name': team_name,
                                                        'email': email,
                                                        'phone': phone,
                                                        'status': 'assigned',
                                                        'assigned_pool': pool_name,
                                                        'paid': False,
                                                        'registered_at': datetime.now().isoformat()
                                                    })
                                    elif isinstance(item, str):
                                        # Simple string format (backward compatible)
                                        teams_list.append(item.strip())
                                
                                normalized[pool_name] = {'teams': teams_list, 'advance': 2}
                            elif isinstance(pool_data, dict):
                                teams_list = []
                                teams_raw = pool_data.get('teams', [])
                                advance = pool_data.get('advance', 2)
                                
                                # Process teams list (might be strings or dicts)
                                for item in teams_raw:
                                    if isinstance(item, dict):
                                        team_name = item.get('name', '').strip()
                                        if team_name:
                                            teams_list.append(team_name)
                                            email = item.get('email', '').strip()
                                            phone = item.get('phone', '').strip()
                                            if email or phone:
                                                existing_reg = None
                                                for reg in registrations['teams']:
                                                    if reg['team_name'] == team_name:
                                                        existing_reg = reg
                                                        break
                                                
                                                if existing_reg:
                                                    if email:
                                                        existing_reg['email'] = email
                                                    if phone:
                                                        existing_reg['phone'] = phone
                                                    existing_reg['status'] = 'assigned'
                                                    existing_reg['assigned_pool'] = pool_name
                                                    # Preserve paid status if not already set
                                                    if 'paid' not in existing_reg:
                                                        existing_reg['paid'] = False
                                                else:
                                                    registrations['teams'].append({
                                                        'team_name': team_name,
                                                        'email': email,
                                                        'phone': phone,
                                                        'status': 'assigned',
                                                        'assigned_pool': pool_name,
                                                        'paid': False,
                                                        'registered_at': datetime.now().isoformat()
                                                    })
                                    elif isinstance(item, str):
                                        teams_list.append(item.strip())
                                
                                normalized[pool_name] = {'teams': teams_list, 'advance': advance}
                            else:
                                flash(f'Invalid format for pool "{pool_name}".', 'error')
                                return redirect(url_for('teams'))
                        
                        save_teams(normalized)
                        save_registrations(registrations)
                        
                        # Clear existing schedule when teams change
                        schedule_path = _file_path('schedule.yaml')
                        if os.path.exists(schedule_path):
                            os.remove(schedule_path)
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
                # Move teams back to unassigned registrations
                teams_in_pool = pools[pool_name].get('teams', [])
                if teams_in_pool:
                    registrations = load_registrations()
                    for team_name in teams_in_pool:
                        for reg_team in registrations['teams']:
                            if reg_team['team_name'] == team_name and reg_team.get('status') == 'assigned':
                                reg_team['status'] = 'unassigned'
                                reg_team['assigned_pool'] = None
                    save_registrations(registrations)
                
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
                # Check if team came from registrations and update status
                registrations = load_registrations()
                for reg_team in registrations['teams']:
                    if reg_team['team_name'] == team_name and reg_team.get('status') == 'assigned':
                        reg_team['status'] = 'unassigned'
                        reg_team['assigned_pool'] = None
                        save_registrations(registrations)
                        break
        
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
    registrations = load_registrations()
    return render_template('teams.html', pools=pools, registrations=registrations)


@app.route('/register/<username>/<slug>', methods=['GET', 'POST'])
def public_register(username, slug):
    """Public team registration page (no login required)."""
    # Verify tournament exists
    user_dir = os.path.join(USERS_DIR, username)
    tournaments_file = os.path.join(user_dir, 'tournaments.yaml')
    if not os.path.exists(tournaments_file):
        abort(404)
    
    try:
        with open(tournaments_file, 'r', encoding='utf-8') as f:
            tournaments_data = yaml.safe_load(f)
            if not tournaments_data or not tournaments_data.get('tournaments'):
                abort(404)
            tournament = next((t for t in tournaments_data['tournaments'] if t['slug'] == slug), None)
            if not tournament:
                abort(404)
    except Exception:
        abort(404)
    
    # Load tournament data
    tournament_dir = os.path.join(user_dir, 'tournaments', slug)
    registrations_file = os.path.join(tournament_dir, 'registrations.yaml')
    constraints_file = os.path.join(tournament_dir, 'constraints.yaml')
    teams_file = os.path.join(tournament_dir, 'teams.yaml')
    
    # Load constraints for tournament info
    tournament_name = tournament.get('name', 'Tournament')
    tournament_dates = ''
    organization_name = ''
    tournament_location = ''
    if os.path.exists(constraints_file):
        with open(constraints_file, 'r', encoding='utf-8') as f:
            constraints = yaml.safe_load(f)
            if constraints:
                tournament_name = constraints.get('tournament_name', tournament_name)
                tournament_dates = constraints.get('tournament_date', '')
                organization_name = constraints.get('club_name', '')
                tournament_location = constraints.get('tournament_location', '')
    
    # Load pools
    pools = {}
    if os.path.exists(teams_file):
        with open(teams_file, 'r', encoding='utf-8') as f:
            pools = yaml.safe_load(f) or {}
    
    # Load registrations
    if os.path.exists(registrations_file):
        with open(registrations_file, 'r', encoding='utf-8') as f:
            registrations = yaml.safe_load(f) or {}
    else:
        registrations = {'registration_open': False, 'teams': []}
    
    if request.method == 'POST':
        # Handle AJAX registration submission
        if not registrations.get('registration_open', False):
            return jsonify({'success': False, 'error': 'Registration is currently closed.'}), 400
        
        data = request.get_json()
        team_name = data.get('team_name', '').strip()
        email = data.get('email', '').strip()
        phone = data.get('phone', '').strip()
        
        if not team_name or not email:
            return jsonify({'success': False, 'error': 'Team name and email are required.'}), 400
        
        # Check for duplicates
        existing_teams = [t['team_name'] for t in registrations.get('teams', [])]
        if team_name in existing_teams:
            return jsonify({'success': False, 'error': 'This team name is already registered.'}), 400
        
        # Add registration
        new_registration = {
            'team_name': team_name,
            'email': email,
            'phone': phone if phone else None,
            'registered_at': datetime.now().isoformat(),
            'status': 'unassigned',
            'assigned_pool': None,
            'paid': False
        }
        
        if 'teams' not in registrations:
            registrations['teams'] = []
        registrations['teams'].append(new_registration)
        
        # Save with filelock
        lock_file = os.path.join(tournament_dir, '.lock')
        lock = FileLock(lock_file, timeout=10)
        with lock:
            with open(registrations_file, 'w', encoding='utf-8') as f:
                yaml.dump(registrations, f, default_flow_style=False)
        
        return jsonify({'success': True, 'message': 'Registration successful!'})
    
    # GET: render registration form
    registration_open = registrations.get('registration_open', False)
    
    # Check for logo in tournament directory
    logo_prefix = os.path.join(tournament_dir, 'logo')
    logo_matches = glob.glob(logo_prefix + '.*')
    if logo_matches:
        # Serve logo from tournament directory using a public endpoint
        # We'll use /api/logo with query params for public access
        logo_url = f'/api/logo?username={username}&slug={slug}'
    else:
        logo_url = DEFAULT_LOGO_URL
    
    return render_template('team_register.html', 
                          tournament_name=tournament_name,
                          organization_name=organization_name,
                          tournament_dates=tournament_dates,
                          tournament_location=tournament_location,
                          logo_url=logo_url,
                          pools=pools,
                          registration_open=registration_open,
                          username=username,
                          slug=slug)


@app.route('/api/registrations/toggle', methods=['POST'], endpoint='api_toggle_registration')
@login_required
def api_toggle_registration():
    """Toggle registration open/closed status."""
    registrations = load_registrations()
    registrations['registration_open'] = not registrations.get('registration_open', False)
    save_registrations(registrations)
    return jsonify({'success': True, 'registration_open': registrations['registration_open']})


@app.route('/api/registrations/edit', methods=['POST'])
@login_required
def api_edit_registration():
    """Edit a registration (organizer only)."""
    old_team_name = request.json.get('old_team_name', '').strip()
    new_team_name = request.json.get('team_name', '').strip()
    email = request.json.get('email', '').strip()
    phone = request.json.get('phone', '').strip()
    
    if not old_team_name or not new_team_name or not email:
        return jsonify({'success': False, 'error': 'Team name and email are required.'}), 400
    
    registrations = load_registrations()
    
    # Find the registration
    reg_to_edit = None
    for reg in registrations['teams']:
        if reg['team_name'] == old_team_name:
            reg_to_edit = reg
            break
    
    if not reg_to_edit:
        return jsonify({'success': False, 'error': 'Registration not found.'}), 404
    
    # Check for duplicate name (if changing name)
    if new_team_name != old_team_name:
        existing_names = [t['team_name'] for t in registrations['teams'] if t != reg_to_edit]
        if new_team_name in existing_names:
            return jsonify({'success': False, 'error': 'This team name is already registered.'}), 400
    
    # Update registration
    reg_to_edit['team_name'] = new_team_name
    reg_to_edit['email'] = email
    reg_to_edit['phone'] = phone if phone else None
    
    # If name changed and team is assigned, update pool too
    if new_team_name != old_team_name and reg_to_edit.get('status') == 'assigned':
        pools = load_teams()
        pool_name = reg_to_edit.get('assigned_pool')
        if pool_name and pool_name in pools:
            teams_list = pools[pool_name]['teams']
            if old_team_name in teams_list:
                idx = teams_list.index(old_team_name)
                teams_list[idx] = new_team_name
                save_teams(pools)
    
    save_registrations(registrations)
    return jsonify({'success': True})


@app.route('/api/registrations/delete', methods=['POST'])
@login_required
def api_delete_registration():
    """Delete a registration (organizer only)."""
    team_name = request.json.get('team_name', '').strip()
    
    if not team_name:
        return jsonify({'success': False, 'error': 'Team name is required.'}), 400
    
    registrations = load_registrations()
    
    # Find and remove the registration
    reg_to_delete = None
    for reg in registrations['teams']:
        if reg['team_name'] == team_name:
            reg_to_delete = reg
            break
    
    if not reg_to_delete:
        return jsonify({'success': False, 'error': 'Registration not found.'}), 404
    
    # If team is assigned to a pool, remove it from there too
    if reg_to_delete.get('status') == 'assigned' and reg_to_delete.get('assigned_pool'):
        pools = load_teams()
        pool_name = reg_to_delete['assigned_pool']
        if pool_name in pools and team_name in pools[pool_name]['teams']:
            pools[pool_name]['teams'].remove(team_name)
            save_teams(pools)
    
    registrations['teams'].remove(reg_to_delete)
    save_registrations(registrations)
    return jsonify({'success': True})


@app.route('/api/teams/assign_from_registration', methods=['POST'])
@login_required
def api_assign_from_registration():
    """Assign a registered team to a pool."""
    team_name = request.json.get('team_name', '').strip()
    pool_name = request.json.get('pool_name', '').strip()
    
    if not team_name or not pool_name:
        return jsonify({'success': False, 'error': 'Team name and pool name are required.'}), 400
    
    pools = load_teams()
    if pool_name not in pools:
        return jsonify({'success': False, 'error': 'Pool not found.'}), 404
    
    # Check if team already exists in any pool
    for p_name, pool_data in pools.items():
        if team_name in pool_data['teams']:
            return jsonify({'success': False, 'error': f'Team already exists in {p_name}.'}), 400
    
    registrations = load_registrations()
    
    # Find the registration
    reg_team = None
    for reg in registrations['teams']:
        if reg['team_name'] == team_name:
            reg_team = reg
            break
    
    if not reg_team:
        return jsonify({'success': False, 'error': 'Registration not found.'}), 404
    
    # Add team to pool
    pools[pool_name]['teams'].append(team_name)
    save_teams(pools)
    
    # Update registration status
    reg_team['status'] = 'assigned'
    reg_team['assigned_pool'] = pool_name
    save_registrations(registrations)
    
    return jsonify({'success': True})


@app.route('/api/toggle-paid', methods=['POST'])
@login_required
def api_toggle_paid():
    """Toggle paid status for a team."""
    team_name = request.json.get('team_name', '').strip()
    
    if not team_name:
        return jsonify({'success': False, 'error': 'Team name is required.'}), 400
    
    registrations = load_registrations()
    
    # Find the team
    team_found = False
    for reg in registrations['teams']:
        if reg['team_name'] == team_name:
            # Toggle paid status
            reg['paid'] = not reg.get('paid', False)
            team_found = True
            new_status = reg['paid']
            break
    
    if not team_found:
        return jsonify({'success': False, 'error': 'Team not found in registrations.'}), 404
    
    save_registrations(registrations)
    return jsonify({'success': True, 'paid': new_status})


@app.route('/api/unpaid-teams', methods=['GET'])
@login_required
def api_unpaid_teams():
    """Get list of unpaid teams with their emails."""
    registrations = load_registrations()
    
    unpaid_teams = []
    for reg in registrations['teams']:
        if not reg.get('paid', False):
            team_name = reg.get('team_name', 'Unknown Team')
            if team_name:  # Only include if team_name exists
                unpaid_teams.append({
                    'team_name': team_name,
                    'email': reg.get('email', ''),
                    'phone': reg.get('phone', ''),
                    'status': reg.get('status', 'unassigned'),
                    'assigned_pool': reg.get('assigned_pool')
                })
    
    return jsonify({'success': True, 'unpaid_teams': unpaid_teams})


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
                        schedule_path = _file_path('schedule.yaml')
                        if os.path.exists(schedule_path):
                            os.remove(schedule_path)
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


@app.route('/api/export-teams', methods=['GET'])
@login_required
def api_export_teams():
    """Export teams with email/phone information in importable YAML format."""
    pools = load_teams()
    registrations = load_registrations()
    
    # Create mapping of team_name -> registration info
    reg_map = {}
    for reg in registrations.get('teams', []):
        reg_map[reg['team_name']] = {
            'email': reg.get('email', ''),
            'phone': reg.get('phone', '')
        }
    
    # Build export structure with team objects
    export_data = {}
    for pool_name, pool_data in pools.items():
        teams_list = []
        for team_name in pool_data.get('teams', []):
            # Check if we have registration info for this team
            if team_name in reg_map and (reg_map[team_name]['email'] or reg_map[team_name]['phone']):
                # Export as object with name, email, phone
                team_obj = {'name': team_name}
                if reg_map[team_name]['email']:
                    team_obj['email'] = reg_map[team_name]['email']
                if reg_map[team_name]['phone']:
                    team_obj['phone'] = reg_map[team_name]['phone']
                teams_list.append(team_obj)
            else:
                # Export as simple string (backward compatible)
                teams_list.append(team_name)
        
        export_data[pool_name] = {
            'teams': teams_list,
            'advance': pool_data.get('advance', 2)
        }
    
    # Convert to YAML and return as downloadable file
    yaml_content = yaml.dump(export_data, default_flow_style=False, allow_unicode=True)
    
    return Response(
        yaml_content,
        mimetype='application/x-yaml',
        headers={'Content-Disposition': 'attachment; filename=teams_export.yaml'}
    )


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
    if 'show_test_buttons' in data:
        constraints_data['show_test_buttons'] = data['show_test_buttons']
    if 'pool_to_bracket_delay' in data:
        constraints_data['pool_to_bracket_delay_minutes'] = int(data['pool_to_bracket_delay'])
    if 'club_name' in data:
        constraints_data['club_name'] = data['club_name']
    if 'tournament_name' in data:
        constraints_data['tournament_name'] = data['tournament_name']
    if 'tournament_date' in data:
        constraints_data['tournament_date'] = data['tournament_date']
    
    save_constraints(constraints_data)
    return jsonify({'success': True})


@app.route('/api/reset', methods=['POST'])
def api_reset_all():
    """Reset all tournament data."""
    # Clear all data files
    for fname in ['teams.yaml', 'courts.csv', 'results.yaml', 'schedule.yaml', 'constraints.yaml', 'registrations.yaml']:
        fpath = _file_path(fname)
        if os.path.exists(fpath):
            os.remove(fpath)
    _delete_logo_file()
    
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
    for fname in ['results.yaml', 'schedule.yaml']:
        fpath = _file_path(fname)
        if os.path.exists(fpath):
            os.remove(fpath)
    
    return jsonify({'success': True})


@app.route('/api/test-teams', methods=['POST'])
def api_load_test_teams():
    """Load test teams for development/testing."""
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
    
    # Register all test teams in registrations.yaml so pool deletion works correctly
    registrations = load_registrations()
    existing_team_names = {team['team_name'] for team in registrations['teams']}
    
    for pool_name, pool_data in test_teams.items():
        for team_name in pool_data['teams']:
            if team_name not in existing_team_names:
                registrations['teams'].append({
                    'team_name': team_name,
                    'email': f'{team_name.replace(" - ", "-").replace(" ", "")}@test.example',
                    'phone': None,
                    'registered_at': datetime.now().isoformat(),
                    'status': 'assigned',
                    'assigned_pool': pool_name,
                    'paid': False
                })
    
    save_registrations(registrations)
    
    # Clear any existing results and schedule
    for fname in ['results.yaml', 'schedule.yaml']:
        fpath = _file_path(fname)
        if os.path.exists(fpath):
            os.remove(fpath)
    
    return jsonify({'success': True})


@app.route('/api/test-courts', methods=['POST'])
def api_load_test_courts():
    """Load test courts for development/testing."""
    test_courts = [
        {'name': 'Court 1', 'start_time': '09:00', 'end_time': '02:00'},
        {'name': 'Court 2', 'start_time': '09:00', 'end_time': '02:00'},
        {'name': 'Court 3', 'start_time': '09:00', 'end_time': '02:00'},
        {'name': 'Court 4', 'start_time': '09:00', 'end_time': '02:00'}
    ]
    save_courts(test_courts)
    
    # Clear any existing schedule
    schedule_path = _file_path('schedule.yaml')
    if os.path.exists(schedule_path):
        os.remove(schedule_path)
    
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
    
    pools = load_teams()
    results = load_results()
    # Clear previous bracket results to regenerate fresh
    bracket_results = {}
    constraints = load_constraints()
    bracket_type = constraints.get('bracket_type', 'double')
    
    # Get standings for seeding
    standings = calculate_pool_standings(pools, results)
    
    # Import the appropriate bracket generation function
    if bracket_type == 'double':
        from core.double_elimination import generate_double_bracket_with_results
        bracket_generator = generate_double_bracket_with_results
    else:
        from core.elimination import generate_bracket_with_results
        bracket_generator = generate_bracket_with_results
    
    # Generate bracket to find playable matches
    bracket_data = bracket_generator(pools, standings, bracket_results)
    
    if not bracket_data:
        return jsonify({'success': False, 'error': 'No bracket data'})
    
    updated = True
    # Keep generating results until no more playable matches
    while updated:
        updated = False
        bracket_data = bracket_generator(pools, standings, bracket_results)
        
        # For double elimination: Process winners bracket, losers bracket, grand final, bracket reset
        # For single elimination: Process rounds
        if bracket_type == 'double':
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
        else:
            # Single elimination: Process rounds
            for round_name, matches in bracket_data.get('rounds', {}).items():
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
    
    results['bracket'] = bracket_results
    save_results(results)
    
    # Now generate Silver bracket results if enabled (only for single elimination)
    if bracket_type == 'single' and constraints.get('silver_bracket_enabled', False):
        from core.elimination import generate_silver_bracket_with_results as generate_silver_single_bracket
        
        # Reload results with Gold bracket filled
        results = load_results()
        bracket_results = results.get('bracket', {})
        
        updated = True
        while updated:
            updated = False
            silver_bracket_data = generate_silver_single_bracket(pools, standings, bracket_results)
            
            if not silver_bracket_data:
                break
            
            # Process silver rounds (single elimination structure)
            for round_name, matches in silver_bracket_data.get('rounds', {}).items():
                for match in matches:
                    if match.get('is_playable') and not match.get('is_bye'):
                        team1, team2 = match['teams']
                        match_number = match['match_number']
                        match_key = f"silver_{round_name}_{match_number}"
                        
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
    
    # Generate Silver bracket for double elimination if enabled
    elif bracket_type == 'double' and constraints.get('silver_bracket_enabled', False):
        from core.double_elimination import generate_silver_double_bracket_with_results
        
        # Reload results with Gold bracket filled
        results = load_results()
        bracket_results = results.get('bracket', {})
        
        updated = True
        while updated:
            updated = False
            silver_bracket_data = generate_silver_double_bracket_with_results(pools, standings, bracket_results)
            
            if not silver_bracket_data:
                break
            
            # Process silver winners bracket
            for round_name, matches in silver_bracket_data.get('winners_bracket', {}).items():
                for match in matches:
                    if match.get('is_playable') and not match.get('is_bye'):
                        team1, team2 = match['teams']
                        match_number = match['match_number']
                        match_key = f"silver_winners_{round_name}_{match_number}"
                        
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
            
            # Process silver losers bracket
            for round_name, matches in silver_bracket_data.get('losers_bracket', {}).items():
                for match in matches:
                    if match.get('is_playable'):
                        team1, team2 = match['teams']
                        match_number = match['match_number']
                        match_key = f"silver_losers_{round_name}_{match_number}"
                        
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
            
            # Process silver grand final
            gf = silver_bracket_data.get('grand_final')
            if gf and gf.get('is_playable'):
                team1, team2 = gf['teams']
                match_key = "silver_grand_final_Grand Final_1"
                
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
            
            # Process silver bracket reset if needed
            br = silver_bracket_data.get('bracket_reset')
            if br and br.get('needs_reset') and br.get('is_playable'):
                team1, team2 = br['teams']
                match_key = "silver_bracket_reset_Bracket Reset_1"
                
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
            constraints_data['day_end_time_limit'] = request.form.get('day_end_time', '22:00')
            constraints_data['bracket_type'] = request.form.get('bracket_type', 'single')
            constraints_data['scoring_format'] = request.form.get('scoring_format', 'best_of_3')
            constraints_data['pool_in_same_court'] = request.form.get('pool_in_same_court') == 'on'
            constraints_data['silver_bracket_enabled'] = request.form.get('silver_bracket_enabled') == 'on'
            constraints_data['show_test_buttons'] = 'show_test_buttons' in request.form
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
                
                # Generate bracket matches and schedule them
                # Algorithm: Interleave Winners and Losers brackets with proper dependencies
                # - Losers bracket matches can only start after the Winners matches that feed them complete
                # - Each bracket type gets assigned to a court
                # - Schedule respects round dependencies
                
                bracket_type = constraints_data.get('bracket_type', 'double')
                include_silver = constraints_data.get('silver_bracket_enabled', False)
                
                if bracket_type == 'double':
                    # Use new execution order function for correct match ordering
                    gold_matches = generate_bracket_execution_order(pools, None, prefix="", phase_name="Bracket")
                    silver_matches = generate_silver_bracket_execution_order(pools, None) if include_silver else []
                else:
                    bracket_matches = generate_all_single_bracket_matches_for_scheduling(pools, None, include_silver)
                    # Add time_slot based on round order for single elimination
                    round_order = {}
                    slot = 0
                    for m in bracket_matches:
                        r = m['round']
                        if r not in round_order:
                            round_order[r] = slot
                            slot += 1
                        m['time_slot'] = round_order[r]
                    gold_matches = [m for m in bracket_matches if 'Silver' not in m.get('phase', '')]
                    silver_matches = [m for m in bracket_matches if 'Silver' in m.get('phase', '')]
                
                if gold_matches or silver_matches:
                    # Find the last scheduled time from pool play
                    last_end_time = None
                    for day in schedule_data:
                        for court in schedule_data[day]:
                            for match in schedule_data[day][court]:
                                if last_end_time is None or match['end_time'] > last_end_time:
                                    last_end_time = match['end_time']
                    
                    match_duration = constraints_data.get('match_duration_minutes', 30)
                    break_minutes = constraints_data.get('min_break_between_matches_minutes', 0)
                    slot_duration = match_duration + break_minutes
                    
                    def time_to_minutes(t):
                        if not t:
                            return 0
                        parts = t.split(':')
                        return int(parts[0]) * 60 + int(parts[1])
                    
                    def minutes_to_time(m):
                        return f"{m // 60:02d}:{m % 60:02d}"
                    
                    # Calculate bracket start time with delay
                    pool_to_bracket_delay = constraints_data.get('pool_to_bracket_delay_minutes', 0)
                    bracket_start = time_to_minutes(last_end_time) + break_minutes + pool_to_bracket_delay if last_end_time else time_to_minutes(courts_data[0]['start_time'])
                    
                    bracket_day = "Bracket Phase"
                    if bracket_day not in schedule_data:
                        schedule_data[bracket_day] = {}
                    
                    court_names = [c['name'] for c in courts_data]
                    num_courts = len(court_names)
                    
                    # Initialize all courts
                    for court_name in court_names:
                        if court_name not in schedule_data[bracket_day]:
                            schedule_data[bracket_day][court_name] = []
                    
                    # Assign courts: distribute across available courts by round
                    # Gold and Silver each get a share of courts
                    if include_silver and num_courts >= 2:
                        gold_courts = court_names[:num_courts // 2] or [court_names[0]]
                        silver_courts = court_names[num_courts // 2:] or [court_names[-1]]
                    else:
                        gold_courts = court_names
                        silver_courts = [court_names[-1]] if include_silver else []
                    
                    def schedule_match(court, start_min, bmatch):
                        schedule_data[bracket_day][court].append({
                            'teams': bmatch['teams'],
                            'start_time': minutes_to_time(start_min),
                            'end_time': minutes_to_time(start_min + match_duration),
                            'day': bracket_day,
                            'pool': bmatch['phase'],
                            'round': bmatch['round'],
                            'match_code': bmatch.get('match_code', ''),
                            'is_placeholder': bmatch.get('is_placeholder', True),
                            'is_bracket': True
                        })
                    
                    def schedule_bracket_matches(bracket_matches, assigned_courts):
                        """Schedule bracket matches across courts, parallelizing within rounds."""
                        # Group matches by time_slot (round dependency level)
                        rounds = {}
                        for m in bracket_matches:
                            if m.get('is_bye', False):
                                continue
                            slot = m.get('time_slot', 0)
                            if slot not in rounds:
                                rounds[slot] = []
                            rounds[slot].append(m)
                        
                        current_time = bracket_start
                        for slot in sorted(rounds.keys()):
                            round_matches = rounds[slot]
                            # Distribute this round's matches across courts round-robin
                            for i, bmatch in enumerate(round_matches):
                                court = assigned_courts[i % len(assigned_courts)]
                                schedule_match(court, current_time + (i // len(assigned_courts)) * slot_duration, bmatch)
                            # Next round starts after all matches in this round complete
                            rows_needed = (len(round_matches) + len(assigned_courts) - 1) // len(assigned_courts)
                            current_time += rows_needed * slot_duration
                    
                    # Schedule Gold bracket
                    schedule_bracket_matches(gold_matches, gold_courts)
                    
                    # Schedule Silver bracket
                    if include_silver and silver_matches:
                        schedule_bracket_matches(silver_matches, silver_courts)
                
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
                
                # Calculate stats - total_scheduled includes all matches (pool + bracket)
                total_scheduled = sum(
                    len(court_data['matches']) 
                    for day_data in schedule_data.values() 
                    for court_name, court_data in day_data.items()
                    if court_name != '_time_slots'
                )
                
                stats = {
                    'total_matches': total_scheduled,
                    'scheduled_matches': total_scheduled,
                    'unscheduled_matches': 0
                }
                
                # Save the schedule for tracking
                save_schedule(schedule_data, stats)
                
                # Clear all previous results (pool play and bracket)
                save_results({'pool_play': {}, 'bracket': {}, 'bracket_type': 'single'})
                
                # Clear pending score reports from previous schedule
                save_pending_results([])
                
                # Stay on schedule page after successful generation
                return render_template('schedule.html', schedule=schedule_data, error=None, stats=stats)
                
        except Exception as e:
            error = f"Error generating schedule: {str(e)}"
    
    # GET request - load saved schedule if exists
    schedule_data, stats = load_schedule()
    
    # Enrich schedule with live results
    if schedule_data:
        pools = load_teams()
        results = load_results()
        standings = calculate_pool_standings(pools, results)
        schedule_data = enrich_schedule_with_results(schedule_data, results, pools, standings)
    
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
    
    # Calculate tracking stats - count only pool (non-bracket) matches
    pool_scheduled = 0
    if schedule_data:
        for day_data in schedule_data.values():
            for court_name, court_data in (
                (c, d) for c, d in day_data.items() if c != '_time_slots'
            ):
                for match in court_data.get('matches', []):
                    if not match.get('is_bracket'):
                        pool_scheduled += 1
    completed_matches = sum(
        1 for key, r in results.get('pool_play', {}).items()
        if r.get('completed') and not key.endswith('_Bracket') and not key.endswith('_Silver Bracket')
    )
    tracking_stats = {
        'scheduled_matches': pool_scheduled,
        'completed_matches': completed_matches,
        'remaining_matches': pool_scheduled - completed_matches
    }
    
    # Load pending score reports
    pending_list = load_pending_results()
    pending_results = {item['match_key']: item for item in pending_list} if pending_list else {}
    
    share_url = url_for('public_live', username=session.get('user', ''), slug=getattr(g, 'active_tournament', ''), _external=True)
    return render_template('tracking.html', schedule=schedule_data, stats=tracking_stats,
                          results=results.get('pool_play', {}), standings=standings,
                          scoring_format=scoring_format, pools=pools, share_url=share_url,
                          pending_results=pending_results)


@app.route('/awards')
def awards():
    """Awards management page."""
    awards_data = load_awards()
    return render_template('awards.html', awards=awards_data.get('awards', []))


@app.route('/messages')
@login_required
def messages():
    """Messages management page for organizers."""
    messages_list = load_messages()
    
    # Calculate unread count
    unread_count = sum(1 for m in messages_list if m.get('status') == 'new')
    
    # Sort by timestamp (newest first)
    messages_list.sort(key=lambda m: m.get('timestamp', ''), reverse=True)
    
    return render_template('messages.html', messages=messages_list, unread_count=unread_count)


@app.route('/api/awards/add', methods=['POST'])
def api_awards_add():
    """Add a new award."""
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'No data provided'}), 400

    name = data.get('name', '').strip()
    player = data.get('player', '').strip()
    if not name or not player:
        return jsonify({'success': False, 'error': 'Name and player are required'}), 400

    new_award = {
        'id': f"award-{int(time.time())}",
        'name': name,
        'player': player,
        'image': data.get('image', 'trophy.svg'),
    }

    awards_data = load_awards()
    awards_data['awards'].append(new_award)
    save_awards(awards_data)
    return jsonify({'success': True, 'award': new_award})


@app.route('/api/awards/delete', methods=['POST'])
def api_awards_delete():
    """Delete an award by ID."""
    data = request.get_json()
    if not data or 'id' not in data:
        return jsonify({'success': False, 'error': 'No ID provided'}), 400

    award_id = data['id']
    awards_data = load_awards()
    award_to_delete = None
    for a in awards_data['awards']:
        if a.get('id') == award_id:
            award_to_delete = a
            break

    if not award_to_delete:
        return jsonify({'success': False, 'error': 'Award not found'}), 404

    # Delete custom image file if applicable
    image = award_to_delete.get('image', '')
    if image.startswith('custom-'):
        image_path = os.path.join(_tournament_dir(), image)
        if os.path.exists(image_path):
            os.remove(image_path)

    awards_data['awards'] = [a for a in awards_data['awards'] if a.get('id') != award_id]
    save_awards(awards_data)
    return jsonify({'success': True})


@app.route('/api/awards/upload-image', methods=['POST'])
def api_awards_upload_image():
    """Upload a custom award image."""
    file = request.files.get('image')
    if not file or not file.filename:
        return jsonify({'success': False, 'error': 'No file provided'}), 400

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_LOGO_EXTENSIONS:
        return jsonify({'success': False, 'error': f'Invalid file type. Allowed: {", ".join(ALLOWED_LOGO_EXTENSIONS)}'}), 400

    filename = f"custom-{int(time.time())}{ext}"
    file.save(os.path.join(_tournament_dir(), filename))
    return jsonify({'success': True, 'filename': filename})


@app.route('/api/awards/image/<filename>')
def api_awards_image(filename):
    """Serve a custom award image from the tournament directory."""
    image_path = os.path.join(_tournament_dir(), filename)
    if not os.path.exists(image_path):
        abort(404)
    return send_file(image_path)


@app.route('/api/test-awards', methods=['POST'])
def api_test_awards():
    """Load sample beach volleyball awards for testing."""
    test_awards = [
        {'id': 'award-test-1', 'name': 'MVP', 'player': 'Alex Silva', 'image': 'trophy.svg'},
        {'id': 'award-test-2', 'name': 'Best Blocker', 'player': 'Jordan Lee', 'image': 'medal-gold.svg'},
        {'id': 'award-test-3', 'name': 'Best Defender', 'player': 'Sam Costa', 'image': 'medal-silver.svg'},
        {'id': 'award-test-4', 'name': 'Best Server', 'player': 'Chris Tanaka', 'image': 'target.svg'},
        {'id': 'award-test-5', 'name': 'Spirit Award', 'player': 'Morgan Reyes', 'image': 'star.svg'},
    ]
    awards_data = load_awards()
    awards_data['awards'] = test_awards
    save_awards(awards_data)
    return jsonify({'success': True})


@app.route('/api/awards/samples')
def api_awards_samples():
    """List available sample award images."""
    awards_dir = os.path.join(os.path.dirname(__file__), 'static', 'awards')
    if not os.path.isdir(awards_dir):
        return jsonify({'success': True, 'samples': []})
    filenames = sorted(f for f in os.listdir(awards_dir) if os.path.isfile(os.path.join(awards_dir, f)))
    return jsonify({'success': True, 'samples': filenames})


@app.route('/api/report-result/<username>/<slug>', methods=['POST'])
def api_report_result(username, slug):
    """Public API endpoint for players to report match scores.
    
    Requires: match_key, team1, team2, pool, sets in JSON body.
    Rate limited to 30 submissions per IP per hour per tournament.
    """
    # Resolve tournament directory
    data_dir = _resolve_public_tournament_dir(username, slug)
    if not data_dir:
        return jsonify({'success': False, 'error': 'Tournament not found'}), 404
    
    # Get client IP
    client_ip = request.headers.get('X-Forwarded-For', request.remote_addr)
    if client_ip:
        client_ip = client_ip.split(',')[0].strip()
    
    # Check rate limit
    if not check_rate_limit(client_ip, username, slug):
        return jsonify({'success': False, 'error': 'Rate limit exceeded. Please try again later.'}), 429
    
    # Parse request data
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'No data provided'}), 400
    
    match_key = data.get('match_key', '').strip()
    team1 = data.get('team1', '').strip()
    team2 = data.get('team2', '').strip()
    pool = data.get('pool', '').strip()
    sets = data.get('sets', [])
    
    if not match_key or not team1 or not team2 or not sets:
        return jsonify({'success': False, 'error': 'Missing required fields'}), 400
    
    # Validate sets structure
    if not isinstance(sets, list):
        return jsonify({'success': False, 'error': 'Sets must be a list'}), 400
    
    for s in sets:
        if not isinstance(s, list) or len(s) != 2:
            return jsonify({'success': False, 'error': 'Each set must be [score1, score2]'}), 400
        if not isinstance(s[0], int) or not isinstance(s[1], int):
            return jsonify({'success': False, 'error': 'Scores must be integers'}), 400
        if s[0] < 0 or s[1] < 0 or s[0] > 99 or s[1] > 99:
            return jsonify({'success': False, 'error': 'Scores must be between 0 and 99'}), 400
    
    # Load existing pending results
    pending = load_pending_results(data_dir)
    
    # Check if this match already has a pending report - if so, update it (last-wins)
    existing_idx = next((i for i, r in enumerate(pending) if r.get('match_key') == match_key and r.get('status') == 'pending'), None)
    
    # Create result entry
    result_entry = {
        'match_key': match_key,
        'team1': team1,
        'team2': team2,
        'pool': pool,
        'sets': sets,
        'timestamp': datetime.now().isoformat(),
        'status': 'pending'
    }
    
    if existing_idx is not None:
        # Update existing pending result with new submission (last-wins logic)
        pending[existing_idx] = result_entry
    else:
        # Add new pending result
        pending.append(result_entry)
    
    save_pending_results(pending, data_dir)
    
    return jsonify({'success': True})


@app.route('/api/accept-result/<username>/<slug>', methods=['POST'])
@login_required
def api_accept_result(username, slug):
    """Organizer endpoint to accept a pending score report.
    
    Applies the result to results.yaml and marks as accepted.
    Requires: match_key in JSON body.
    """
    # Verify user owns this tournament
    if session.get('user') != username:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    data_dir = _resolve_public_tournament_dir(username, slug)
    if not data_dir:
        return jsonify({'success': False, 'error': 'Tournament not found'}), 404
    
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'No data provided'}), 400
    
    match_key = data.get('match_key', '').strip()
    if not match_key:
        return jsonify({'success': False, 'error': 'Missing match_key'}), 400
    
    # Load pending results
    pending = load_pending_results(data_dir)
    
    # Find the pending result
    result_to_accept = next((r for r in pending if r.get('match_key') == match_key and r.get('status') == 'pending'), None)
    if not result_to_accept:
        return jsonify({'success': False, 'error': 'Pending result not found'}), 404
    
    # Apply to results.yaml (use existing pattern from tracking route)
    # Temporarily set g.data_dir so load_results/save_results work
    original_data_dir = getattr(g, 'data_dir', None)
    g.data_dir = data_dir
    
    try:
        results = load_results()
        
        # Determine winner
        winner_idx, loser_idx = None, None
        if result_to_accept['sets']:
            winner_idx, _ = determine_winner(result_to_accept['sets'])
            loser_idx = 1 - winner_idx
        
        # Store result
        result_entry = {
            'sets': result_to_accept['sets'],
            'completed': True
        }
        
        if winner_idx is not None:
            result_entry['winner'] = result_to_accept['team1'] if winner_idx == 0 else result_to_accept['team2']
            result_entry['loser'] = result_to_accept['team2'] if winner_idx == 0 else result_to_accept['team1']
        
        # Check if this is a pool play or bracket match
        pool = result_to_accept.get('pool', '')
        if pool and not pool.endswith('Bracket') and not pool.endswith('Silver Bracket'):
            # Pool play match
            results['pool_play'][match_key] = result_entry
        else:
            # Bracket match
            results['bracket'][match_key] = result_entry
        
        save_results(results)
        
        # Mark as accepted
        result_to_accept['status'] = 'accepted'
        save_pending_results(pending, data_dir)
        
        return jsonify({'success': True})
    
    finally:
        # Restore original g.data_dir
        if original_data_dir is not None:
            g.data_dir = original_data_dir
        elif hasattr(g, 'data_dir'):
            delattr(g, 'data_dir')


@app.route('/api/dismiss-result/<username>/<slug>', methods=['POST'])
@login_required
def api_dismiss_result(username, slug):
    """Organizer endpoint to dismiss a pending score report.
    
    Marks the report as dismissed (will be pruned after 24h).
    Requires: match_key in JSON body.
    """
    # Verify user owns this tournament
    if session.get('user') != username:
        return jsonify({'success': False, 'error': 'Unauthorized'}), 403
    
    data_dir = _resolve_public_tournament_dir(username, slug)
    if not data_dir:
        return jsonify({'success': False, 'error': 'Tournament not found'}), 404
    
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'No data provided'}), 400
    
    match_key = data.get('match_key', '').strip()
    if not match_key:
        return jsonify({'success': False, 'error': 'Missing match_key'}), 400
    
    # Load pending results
    pending = load_pending_results(data_dir)
    
    # Find the pending result
    result_to_dismiss = next((r for r in pending if r.get('match_key') == match_key and r.get('status') == 'pending'), None)
    if not result_to_dismiss:
        return jsonify({'success': False, 'error': 'Pending result not found'}), 404
    
    # Mark as dismissed
    result_to_dismiss['status'] = 'dismissed'
    save_pending_results(pending, data_dir)
    
    return jsonify({'success': True})


@app.route('/api/message/<username>/<slug>', methods=['POST'])
def api_message(username, slug):
    """Public endpoint for players to send messages to organizers from Live page.
    
    Requires: team_name, message in JSON body.
    No login required - this is for players.
    """
    data_dir = _resolve_public_tournament_dir(username, slug)
    if not data_dir:
        return jsonify({'success': False, 'error': 'Tournament not found'}), 404
    
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'No data provided'}), 400
    
    team_name = data.get('team_name', '').strip()
    message = data.get('message', '').strip()
    
    if not team_name:
        return jsonify({'success': False, 'error': 'Team name is required'}), 400
    if not message:
        return jsonify({'success': False, 'error': 'Message is required'}), 400
    if len(message) > 500:
        return jsonify({'success': False, 'error': 'Message too long (max 500 characters)'}), 400
    
    # Load existing messages
    messages_file = os.path.join(data_dir, 'messages.yaml')
    if os.path.exists(messages_file):
        with open(messages_file, 'r', encoding='utf-8') as f:
            messages_data = yaml.safe_load(f)
            messages = messages_data.get('messages', []) if messages_data else []
    else:
        messages = []
    
    # Create new message
    timestamp = datetime.now().isoformat()
    message_id = f"{int(datetime.now().timestamp())}_{team_name.replace(' ', '_')}"
    
    new_message = {
        'id': message_id,
        'timestamp': timestamp,
        'team_name': team_name,
        'message': message,
        'status': 'new'
    }
    
    messages.append(new_message)
    
    # Save messages
    with open(messages_file, 'w', encoding='utf-8') as f:
        yaml.dump({'messages': messages}, f, default_flow_style=False)
    
    return jsonify({'success': True, 'message_id': message_id})


@app.route('/api/messages/update', methods=['POST'])
@login_required
def api_messages_update():
    """Organizer endpoint to update message status (read/archived/deleted).
    
    Requires: message_id, action ('read'/'archive'/'delete') in JSON body.
    """
    data = request.get_json()
    if not data:
        return jsonify({'success': False, 'error': 'No data provided'}), 400
    
    message_id = data.get('message_id', '').strip()
    action = data.get('action', '').strip()
    
    if not message_id:
        return jsonify({'success': False, 'error': 'Message ID is required'}), 400
    if action not in ['read', 'archive', 'delete']:
        return jsonify({'success': False, 'error': 'Invalid action'}), 400
    
    # Load messages
    messages = load_messages()
    
    # Find the message
    message = next((m for m in messages if m.get('id') == message_id), None)
    if not message:
        return jsonify({'success': False, 'error': 'Message not found'}), 404
    
    # Update message
    if action == 'delete':
        messages = [m for m in messages if m.get('id') != message_id]
    elif action == 'read':
        message['status'] = 'read'
    elif action == 'archive':
        message['status'] = 'archived'
    
    # Save messages
    save_messages(messages)
    
    return jsonify({'success': True})


def _get_live_data() -> dict:
    """Build the template context dict for the live tournament view.

    Returns:
        Dictionary with keys: pools, standings, schedule, results,
        bracket_data, silver_bracket_data, silver_bracket_enabled.
    """
    pools = load_teams()
    results = load_results()
    standings = calculate_pool_standings(pools, results)
    constraints = load_constraints()
    bracket_type = constraints.get('bracket_type', 'double')
    silver_bracket_enabled = constraints.get('silver_bracket_enabled', False)

    schedule_data, stats = load_schedule()
    if schedule_data:
        schedule_data = enrich_schedule_with_results(schedule_data, results, pools, standings)

    bracket_data = None
    silver_bracket_data = None
    bracket_results = results.get('bracket', {})

    if pools:
        if bracket_type == 'double':
            from core.double_elimination import generate_double_bracket_with_results, generate_silver_double_bracket_with_results
            bracket_data = generate_double_bracket_with_results(pools, standings, bracket_results)
            if silver_bracket_enabled:
                silver_bracket_data = generate_silver_double_bracket_with_results(pools, standings, bracket_results)
        else:
            from core.elimination import generate_bracket_with_results, generate_silver_bracket_with_results
            bracket_data = generate_bracket_with_results(pools, standings, bracket_results)
            if silver_bracket_enabled:
                silver_bracket_data = generate_silver_bracket_with_results(pools, standings, bracket_results)

    return dict(
        pools=pools,
        standings=standings,
        schedule=schedule_data,
        results=results.get('pool_play', {}),
        bracket_data=bracket_data,
        silver_bracket_data=silver_bracket_data,
        silver_bracket_enabled=silver_bracket_enabled,
        print_settings=load_print_settings(),
        constraints=constraints,
        awards=load_awards().get('awards', []),
    )


@app.route('/live')
def live():
    """Read-only live view of tournament standings and brackets for players."""
    return render_template('live.html', **_get_live_data(), public_mode=False)


@app.route('/insta')
def insta():
    """Instagram-friendly tournament summary page."""
    return render_template('insta.html', **_get_live_data())


@app.route('/api/live-html')
def api_live_html():
    """Return only the inner HTML of the live content area (partial template)."""
    return render_template('live_content.html', **_get_live_data())


def _get_data_file_mtimes() -> dict:
    """Return modification times for the data files the live page depends on.

    Returns:
        Dictionary mapping file path to its mtime (float), or 0.0 if missing.
    """
    names = ['results.yaml', 'schedule.yaml', 'teams.yaml', 'constraints.yaml']
    files = [_file_path(n) for n in names]
    return {f: os.path.getmtime(f) if os.path.exists(f) else 0.0 for f in files}


@app.route('/api/live-stream')
def api_live_stream():
    """Server-Sent Events stream that notifies clients when data changes."""

    def generate():
        """Yield SSE events, checking data file mtimes every 3 seconds."""
        # Send immediate connected event so client shows "Live" status right away
        yield "event: connected\ndata: ok\n\n"
        
        last_mtimes = _get_data_file_mtimes()
        heartbeat_counter = 0

        while True:
            time.sleep(3)
            heartbeat_counter += 3

            current_mtimes = _get_data_file_mtimes()
            if current_mtimes != last_mtimes:
                last_mtimes = current_mtimes
                yield f"event: update\ndata: {time.time()}\n\n"

            # Send heartbeat every ~15 seconds to keep connection alive
            if heartbeat_counter >= 15:
                heartbeat_counter = 0
                yield ": heartbeat\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
        },
    )


def _resolve_public_tournament_dir(username: str, slug: str):
    """Validate username/slug and return the tournament data directory path.

    Returns:
        The absolute path if valid and exists, or None otherwise.
    """
    if not username or not slug:
        return None
    for part in (username, slug):
        if '..' in part or '/' in part or '\\' in part:
            return None
    path = os.path.join(USERS_DIR, username, 'tournaments', slug)
    if os.path.isdir(path):
        return path
    return None


@app.route('/live/<username>/<slug>')
def public_live(username, slug):
    """Public read-only live view of a tournament."""
    data_dir = _resolve_public_tournament_dir(username, slug)
    if not data_dir:
        abort(404)
    g.data_dir = data_dir
    return render_template('live.html', **_get_live_data(),
                           public_mode=True, public_username=username, public_slug=slug)


@app.route('/api/live-html/<username>/<slug>')
def api_public_live_html(username, slug):
    """Public partial HTML for live content area."""
    data_dir = _resolve_public_tournament_dir(username, slug)
    if not data_dir:
        abort(404)
    g.data_dir = data_dir
    return render_template('live_content.html', **_get_live_data())


@app.route('/api/live-stream/<username>/<slug>')
def api_public_live_stream(username, slug):
    """Public SSE stream for real-time updates."""
    data_dir = _resolve_public_tournament_dir(username, slug)
    if not data_dir:
        abort(404)
    names = ['results.yaml', 'schedule.yaml', 'teams.yaml', 'constraints.yaml']
    watched_files = [os.path.join(data_dir, n) for n in names]

    def generate():
        yield "event: connected\ndata: ok\n\n"
        last_mtimes = {f: os.path.getmtime(f) if os.path.exists(f) else 0.0 for f in watched_files}
        heartbeat_counter = 0
        while True:
            time.sleep(3)
            heartbeat_counter += 3
            current_mtimes = {f: os.path.getmtime(f) if os.path.exists(f) else 0.0 for f in watched_files}
            if current_mtimes != last_mtimes:
                last_mtimes = current_mtimes
                yield f"event: update\ndata: {time.time()}\n\n"
            if heartbeat_counter >= 15:
                heartbeat_counter = 0
                yield ": heartbeat\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={'Cache-Control': 'no-cache', 'X-Accel-Buffering': 'no'},
    )


@app.route('/api/logo')
def api_logo():
    """Serve the uploaded logo, or redirect to default.
    
    Supports public access with ?username=X&slug=Y query params.
    """
    username = request.args.get('username')
    slug = request.args.get('slug')
    
    if username and slug:
        # Public access - serve logo from specific tournament
        user_dir = os.path.join(USERS_DIR, username)
        tournament_dir = os.path.join(user_dir, 'tournaments', slug)
        logo_prefix = os.path.join(tournament_dir, 'logo')
        matches = glob.glob(logo_prefix + '.*')
        if matches:
            return send_file(matches[0])
        return redirect(DEFAULT_LOGO_URL)
    
    # Authenticated access - use active tournament
    logo_path = _find_logo_file()
    if logo_path:
        return send_file(logo_path)
    return redirect(DEFAULT_LOGO_URL)


@app.route('/api/upload-logo', methods=['POST'])
def api_upload_logo():
    """Upload a custom logo image."""
    file = request.files.get('logo')
    if not file or not file.filename:
        return jsonify({'success': False, 'error': 'No file provided'}), 400

    ext = os.path.splitext(file.filename)[1].lower()
    if ext not in ALLOWED_LOGO_EXTENSIONS:
        return jsonify({'success': False, 'error': f'Invalid file type. Allowed: {", ".join(ALLOWED_LOGO_EXTENSIONS)}'}), 400

    _delete_logo_file()
    logo_path = os.path.join(_tournament_dir(), 'logo') + ext
    file.save(logo_path)
    return jsonify({'success': True})


@app.route('/api/export/schedule-csv')
def api_export_schedule_csv():
    """Export the current schedule as a downloadable CSV file."""
    import io

    schedule_data, stats = load_schedule()
    if not schedule_data:
        return jsonify({'success': False, 'error': 'No schedule found'}), 404

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Day', 'Time', 'Court', 'Team 1', 'Team 2', 'Pool / Phase', 'Match Code'])

    for day, day_data in schedule_data.items():
        if day == '_time_slots':
            continue
        for court_name, court_data in day_data.items():
            if court_name == '_time_slots':
                continue
            for match in court_data.get('matches', []):
                teams = match.get('teams', [])
                t1 = teams[0] if len(teams) > 0 else ''
                t2 = teams[1] if len(teams) > 1 else ''
                writer.writerow([
                    day,
                    match.get('start_time', ''),
                    court_name,
                    t1,
                    t2,
                    match.get('pool', ''),
                    match.get('match_code', ''),
                ])

    csv_content = output.getvalue()
    output.close()

    return Response(
        csv_content,
        mimetype='text/csv',
        headers={'Content-Disposition': 'attachment; filename=schedule.csv'},
    )


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
    
    # Check if user is clearing the result (all scores empty/None)
    all_empty = all(
        (score[0] is None or score[0] == '') and (score[1] is None or score[1] == '')
        for score in sets
        if isinstance(score, (list, tuple)) and len(score) >= 2
    )
    
    if all_empty or not sets:
        # Clear the result
        results['pool_play'].pop(match_key, None)
        save_results(results)
        
        # Recalculate standings
        pools = load_teams()
        standings = calculate_pool_standings(pools, results)
        
        return jsonify({
            'success': True,
            'match_key': match_key,
            'cleared': True,
            'standings': standings
        })
    
    # Validate partial input (one score filled, one empty is an error)
    for score in sets:
        if isinstance(score, (list, tuple)) and len(score) >= 2:
            score0_empty = score[0] is None or score[0] == ''
            score1_empty = score[1] is None or score[1] == ''
            if score0_empty != score1_empty:
                return jsonify({'error': 'Both scores must be filled or both must be empty'}), 400
    
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
    
    # Check if user is clearing the result (all scores empty/None)
    all_empty = all(
        (score[0] is None or score[0] == '') and (score[1] is None or score[1] == '')
        for score in sets
        if isinstance(score, (list, tuple)) and len(score) >= 2
    )
    
    if all_empty or not sets:
        # Clear the result
        results['bracket'].pop(match_key, None)
        save_results(results)
        
        return jsonify({
            'success': True,
            'match_key': match_key,
            'cleared': True
        })
    
    # Validate partial input (one score filled, one empty is an error)
    for score in sets:
        if isinstance(score, (list, tuple)) and len(score) >= 2:
            score0_empty = score[0] is None or score[0] == ''
            score1_empty = score[1] is None or score[1] == ''
            if score0_empty != score1_empty:
                return jsonify({'error': 'Both scores must be filled or both must be empty'}), 400
    
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


@app.route('/api/clear-result', methods=['POST'])
def api_clear_result():
    """API endpoint to clear/delete a match result."""
    data = request.get_json()
    if not data or not data.get('match_key'):
        return jsonify({'error': 'Missing match_key'}), 400

    match_key = data['match_key']
    results = load_results()

    # Remove from pool_play or bracket (idempotent — missing key is fine)
    results.get('pool_play', {}).pop(match_key, None)
    results.get('bracket', {}).pop(match_key, None)

    save_results(results)
    return jsonify({'success': True})


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
    
    # Load pending score reports
    pending_list = load_pending_results()
    pending_results = {item['match_key']: item for item in pending_list} if pending_list else {}
    
    return render_template('sbracket.html', bracket_data=bracket_data, error=None, 
                          bracket_results=bracket_results, scoring_format=scoring_format,
                          silver_bracket_data=silver_bracket_data, silver_bracket_enabled=silver_bracket_enabled,
                          pending_results=pending_results)


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
    
    # Load pending score reports
    pending_list = load_pending_results()
    pending_results = {item['match_key']: item for item in pending_list} if pending_list else {}
    
    return render_template('dbracket.html', bracket_data=bracket_data, error=None,
                          bracket_results=bracket_results, scoring_format=scoring_format,
                          silver_bracket_data=silver_bracket_data, silver_bracket_enabled=silver_bracket_enabled,
                          pending_results=pending_results,
)


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


@app.route('/api/export/tournament')
def api_export_tournament():
    """Export all tournament data as a downloadable ZIP file."""
    buffer = io.BytesIO()
    exportable = _get_exportable_files()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        # Add standard data files
        for archive_name, file_path in exportable.items():
            if os.path.exists(file_path):
                zf.write(file_path, archive_name)

        # Add logo file if it exists
        logo = _find_logo_file()
        if logo:
            logo_ext = os.path.splitext(logo)[1]
            zf.write(logo, f'logo{logo_ext}')

    buffer.seek(0)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    return send_file(
        buffer,
        mimetype='application/zip',
        as_attachment=True,
        download_name=f'tournament_export_{timestamp}.zip',
    )


@app.route('/api/import/tournament', methods=['POST'])
def api_import_tournament():
    """Import tournament data from an uploaded ZIP file, replacing current data."""
    file = request.files.get('file')
    if not file or file.filename == '':
        flash('No file selected.', 'error')
        return redirect(url_for('index'))

    # Read file into memory for validation
    file_bytes = file.read()
    if not zipfile.is_zipfile(io.BytesIO(file_bytes)):
        flash('Uploaded file is not a valid ZIP archive.', 'error')
        return redirect(url_for('index'))

    with zipfile.ZipFile(io.BytesIO(file_bytes), 'r') as zf:
        names = set(zf.namelist())

        # Sanity check: must contain at least one core data file
        if not names & ALLOWED_IMPORT_NAMES:
            flash('ZIP does not appear to contain tournament data.', 'error')
            return redirect(url_for('index'))

        # Security: reject entries with path traversal
        for name in names:
            if '..' in name or name.startswith('/') or name.startswith('\\'):
                flash('ZIP contains unsafe file paths. Import aborted.', 'error')
                return redirect(url_for('index'))

        # Extract allowed data files
        exportable = _get_exportable_files()
        for name in names:
            if name in ALLOWED_IMPORT_NAMES:
                dest = exportable[name]
                with zf.open(name) as src, open(dest, 'wb') as dst:
                    dst.write(src.read())

        # Handle logo: delete existing, then extract if present in archive
        logo_entries = [n for n in names if n.startswith('logo.') and os.path.splitext(n)[1] in ALLOWED_LOGO_EXTENSIONS]
        if logo_entries:
            _delete_logo_file()
            logo_name = logo_entries[0]
            logo_ext = os.path.splitext(logo_name)[1]
            logo_dest = os.path.join(_tournament_dir(), 'logo') + logo_ext
            with zf.open(logo_name) as src, open(logo_dest, 'wb') as dst:
                dst.write(src.read())

    flash('Tournament data imported successfully.', 'success')
    return redirect(url_for('index'))


@app.route('/api/export/user')
@login_required
def api_export_user():
    """Export all user tournaments as a downloadable ZIP file."""
    tournaments_file = g.user_tournaments_file
    if not os.path.exists(tournaments_file):
        flash('No tournaments to export.', 'error')
        return redirect(url_for('tournaments'))

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        # Include the tournaments registry
        zf.write(tournaments_file, 'tournaments.yaml')

        data = load_tournaments()
        for t in data.get('tournaments', []):
            slug = t['slug']
            tournament_path = os.path.join(g.user_tournaments_dir, slug)
            if not os.path.isdir(tournament_path):
                continue

            # Add standard data files
            for name in ALLOWED_IMPORT_NAMES:
                file_path = os.path.join(tournament_path, name)
                if os.path.exists(file_path):
                    zf.write(file_path, f'{slug}/{name}')

            # Add logo file if it exists
            logo_prefix = os.path.join(tournament_path, 'logo')
            logo_matches = glob.glob(logo_prefix + '.*')
            if logo_matches:
                logo = logo_matches[0]
                logo_ext = os.path.splitext(logo)[1]
                zf.write(logo, f'{slug}/logo{logo_ext}')

    buffer.seek(0)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    return send_file(
        buffer,
        mimetype='application/zip',
        as_attachment=True,
        download_name=f'user_export_{timestamp}.zip',
    )


@app.route('/api/import/user', methods=['POST'])
@login_required
def api_import_user():
    """Import user tournaments from an uploaded ZIP file (additive merge)."""
    file = request.files.get('file')
    if not file or file.filename == '':
        flash('No file selected.', 'error')
        return redirect(url_for('tournaments'))

    file_bytes = file.read()
    if len(file_bytes) > MAX_UPLOAD_SIZE:
        flash('File too large.', 'error')
        return redirect(url_for('tournaments'))

    if not zipfile.is_zipfile(io.BytesIO(file_bytes)):
        flash('Uploaded file is not a valid ZIP archive.', 'error')
        return redirect(url_for('tournaments'))

    with zipfile.ZipFile(io.BytesIO(file_bytes), 'r') as zf:
        names = set(zf.namelist())

        # Security: reject entries with path traversal
        for name in names:
            if '..' in name or name.startswith('/') or name.startswith('\\'):
                flash('ZIP contains unsafe file paths. Import aborted.', 'error')
                return redirect(url_for('tournaments'))

        # Must contain tournaments.yaml at the root
        if 'tournaments.yaml' not in names:
            flash('ZIP does not contain a tournaments.yaml registry file.', 'error')
            return redirect(url_for('tournaments'))

        # Parse the imported tournaments registry
        try:
            imported_data = yaml.safe_load(zf.read('tournaments.yaml'))
            if not imported_data or not isinstance(imported_data.get('tournaments'), list):
                flash('Invalid tournaments.yaml in ZIP.', 'error')
                return redirect(url_for('tournaments'))
        except Exception:
            flash('Failed to parse tournaments.yaml from ZIP.', 'error')
            return redirect(url_for('tournaments'))

        imported_tournaments = imported_data['tournaments']

        # Extract files for each tournament
        for t in imported_tournaments:
            slug = t.get('slug', '')
            if not slug or '..' in slug or '/' in slug or '\\' in slug:
                continue

            tournament_path = os.path.join(g.user_tournaments_dir, slug)
            os.makedirs(tournament_path, exist_ok=True)

            # Extract allowed data files
            for allowed_name in ALLOWED_IMPORT_NAMES:
                zip_entry = f'{slug}/{allowed_name}'
                if zip_entry in names:
                    dest = os.path.join(tournament_path, allowed_name)
                    with zf.open(zip_entry) as src, open(dest, 'wb') as dst:
                        dst.write(src.read())

            # Handle logo: delete existing, extract new if present
            logo_entries = [n for n in names
                           if n.startswith(f'{slug}/logo.')
                           and os.path.splitext(n)[1] in ALLOWED_LOGO_EXTENSIONS]
            if logo_entries:
                # Delete existing logo
                existing_logo_prefix = os.path.join(tournament_path, 'logo')
                for old_logo in glob.glob(existing_logo_prefix + '.*'):
                    os.remove(old_logo)
                # Extract new logo
                logo_name = logo_entries[0]
                logo_ext = os.path.splitext(logo_name)[1]
                logo_dest = os.path.join(tournament_path, 'logo') + logo_ext
                with zf.open(logo_name) as src, open(logo_dest, 'wb') as dst:
                    dst.write(src.read())

        # Merge tournaments registry (additive)
        existing_data = load_tournaments()
        existing_slugs = {t['slug']: i for i, t in enumerate(existing_data.get('tournaments', []))}

        for t in imported_tournaments:
            slug = t.get('slug', '')
            if not slug or '..' in slug or '/' in slug or '\\' in slug:
                continue
            if slug in existing_slugs:
                # Update name/created for existing tournament
                idx = existing_slugs[slug]
                existing_data['tournaments'][idx]['name'] = t.get('name', slug)
                existing_data['tournaments'][idx]['created'] = t.get('created', datetime.now().isoformat())
            else:
                # Add new tournament
                existing_data['tournaments'].append(t)

        save_tournaments(existing_data)

        # If no active tournament is set, activate the first available one
        if not existing_data.get('active') and existing_data.get('tournaments'):
            first_slug = existing_data['tournaments'][0]['slug']
            existing_data['active'] = first_slug
            save_tournaments(existing_data)
            session['active_tournament'] = first_slug

    flash('User tournaments imported successfully.', 'success')
    return redirect(url_for('tournaments'))


@app.route('/api/admin/export')
@require_backup_key
def api_admin_export():
    """Export entire DATA_DIR as a downloadable ZIP file (admin backup)."""
    if not os.path.exists(DATA_DIR):
        app.logger.error(f'Admin export failed: DATA_DIR does not exist: {DATA_DIR}')
        return jsonify({'error': 'Data directory does not exist'}), 404
    
    app.logger.info(f'Admin export starting: DATA_DIR={DATA_DIR}')
    
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        file_count = 0
        skipped_count = 0
        # Walk the entire DATA_DIR and add all files
        for root, dirs, files in os.walk(DATA_DIR):
            # Skip directories like __pycache__
            dirs[:] = [d for d in dirs if d not in SITE_EXPORT_SKIP_DIRS]
            
            for file in files:
                # Skip files with certain extensions
                if any(file.endswith(ext) for ext in SITE_EXPORT_SKIP_EXTS):
                    skipped_count += 1
                    app.logger.debug(f'Skipping file: {file}')
                    continue
                
                file_path = os.path.join(root, file)
                # Compute relative path from DATA_DIR
                arcname = os.path.relpath(file_path, DATA_DIR)
                zf.write(file_path, arcname)
                file_count += 1
                app.logger.debug(f'Added to ZIP: {arcname}')
        
        app.logger.info(f'Admin export: added {file_count} files to ZIP, skipped {skipped_count} files')
    
    buffer.seek(0)
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    return send_file(
        buffer,
        mimetype='application/zip',
        as_attachment=True,
        download_name=f'tournament-backup-{timestamp}.zip',
    )


@app.route('/api/admin/import', methods=['POST'])
@require_backup_key
def api_admin_import():
    """Import entire DATA_DIR from an uploaded ZIP file (admin restore)."""
    file = request.files.get('file')
    if not file or file.filename == '':
        return jsonify({'error': 'No file uploaded'}), 400
    
    file_bytes = file.read()
    if len(file_bytes) > MAX_SITE_UPLOAD_SIZE:
        return jsonify({'error': f'File too large (max {MAX_SITE_UPLOAD_SIZE} bytes)'}), 400
    
    if not zipfile.is_zipfile(io.BytesIO(file_bytes)):
        return jsonify({'error': 'Uploaded file is not a valid ZIP archive'}), 400
    
    with zipfile.ZipFile(io.BytesIO(file_bytes), 'r') as zf:
        names = set(zf.namelist())
        
        # Security: reject entries with path traversal
        for name in names:
            if '..' in name or name.startswith('/') or name.startswith('\\'):
                return jsonify({'error': 'ZIP contains unsafe file paths. Import aborted.'}), 400
        
        # Must contain tournaments.yaml at minimum (structural validation)
        if 'tournaments.yaml' not in names and 'users.yaml' not in names:
            return jsonify({'error': 'ZIP does not appear to be a valid backup (missing tournaments.yaml or users.yaml)'}), 400
        
        # Create backup of existing DATA_DIR
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_location = os.path.join(BASE_DIR, 'backups', f'pre-restore-{timestamp}')
        os.makedirs(backup_location, exist_ok=True)
        app.logger.info(f'Pre-restore backup will be saved to: {backup_location}')
        
        # Backup existing data
        if os.path.exists(DATA_DIR):
            for item in os.listdir(DATA_DIR):
                src = os.path.join(DATA_DIR, item)
                dst = os.path.join(backup_location, item)
                if os.path.isdir(src):
                    shutil.copytree(src, dst, ignore=shutil.ignore_patterns('.lock', '__pycache__'))
                else:
                    if not item.endswith(('.lock', '.pyc')):
                        shutil.copy2(src, dst)
        
        # Extract uploaded ZIP to DATA_DIR
        os.makedirs(DATA_DIR, exist_ok=True)
        for name in names:
            # Skip metadata files that might exist in the archive
            if name.endswith(('.lock', '.pyc')) or '__pycache__' in name:
                continue
            
            dest_path = os.path.join(DATA_DIR, name)
            os.makedirs(os.path.dirname(dest_path), exist_ok=True)
            
            with zf.open(name) as src, open(dest_path, 'wb') as dst:
                dst.write(src.read())
    
    return jsonify({
        'success': True,
        'backup_location': backup_location,
        'message': f'Data restored successfully. Previous data backed up to {backup_location}'
    }), 200


@app.route('/tournaments')
def tournaments():
    """List all tournaments with create/delete options."""
    data = load_tournaments()
    return render_template('tournaments.html',
                         tournaments=data.get('tournaments', []),
                         active=data.get('active'))


@app.route('/api/tournaments/create', methods=['POST'])
def api_create_tournament():
    """Create a new tournament."""
    name = request.form.get('name', '').strip()
    if not name:
        flash('Tournament name is required.', 'error')
        return redirect(url_for('tournaments'))

    slug = _slugify(name)
    data = load_tournaments()

    if any(t['slug'] == slug for t in data.get('tournaments', [])):
        flash(f'A tournament with a similar name already exists ("{slug}").', 'error')
        return redirect(url_for('tournaments'))

    tournament_path = os.path.join(g.user_tournaments_dir, slug)
    os.makedirs(tournament_path, exist_ok=True)

    # Seed initial data files
    initial_constraints = get_default_constraints()
    initial_constraints['tournament_name'] = name
    with open(os.path.join(tournament_path, 'constraints.yaml'), 'w', encoding='utf-8') as f:
        yaml.dump(initial_constraints, f, default_flow_style=False)
    # Create empty teams and courts files
    with open(os.path.join(tournament_path, 'teams.yaml'), 'w', encoding='utf-8') as f:
        f.write('')
    with open(os.path.join(tournament_path, 'courts.csv'), 'w', encoding='utf-8', newline='') as f:
        f.write('court_name,start_time,end_time\n')

    data['tournaments'].append({
        'slug': slug,
        'name': name,
        'created': datetime.now().isoformat()
    })
    data['active'] = slug
    save_tournaments(data)

    session['active_tournament'] = slug
    flash(f'Tournament "{name}" created.', 'success')
    return redirect(url_for('index'))


@app.route('/api/tournaments/delete', methods=['POST'])
def api_delete_tournament():
    """Delete a tournament."""
    slug = request.form.get('slug', '').strip()
    if not slug:
        flash('No tournament specified.', 'error')
        return redirect(url_for('tournaments'))

    data = load_tournaments()

    # Validate slug (prevent path traversal)
    if '..' in slug or '/' in slug or '\\' in slug:
        flash('Invalid tournament identifier.', 'error')
        return redirect(url_for('tournaments'))

    data['tournaments'] = [t for t in data.get('tournaments', []) if t['slug'] != slug]

    if data.get('active') == slug:
        new_active = data['tournaments'][0]['slug'] if data['tournaments'] else None
        data['active'] = new_active
        if new_active:
            session['active_tournament'] = new_active
        else:
            session.pop('active_tournament', None)

    save_tournaments(data)

    tournament_path = os.path.join(g.user_tournaments_dir, slug)
    if os.path.isdir(tournament_path):
        shutil.rmtree(tournament_path)

    flash('Tournament deleted.', 'success')
    return redirect(url_for('tournaments'))


@app.route('/api/tournaments/clone', methods=['POST'])
def api_clone_tournament():
    """Clone an existing tournament under a new name."""
    source_slug = request.form.get('slug', '').strip()
    new_name = request.form.get('name', '').strip()

    if not source_slug or not new_name:
        flash('Source tournament and new name are required.', 'error')
        return redirect(url_for('tournaments'))

    if '..' in source_slug or '/' in source_slug or '\\' in source_slug:
        flash('Invalid tournament identifier.', 'error')
        return redirect(url_for('tournaments'))

    new_slug = _slugify(new_name)
    data = load_tournaments()

    if not any(t['slug'] == source_slug for t in data.get('tournaments', [])):
        flash('Source tournament not found.', 'error')
        return redirect(url_for('tournaments'))

    if any(t['slug'] == new_slug for t in data.get('tournaments', [])):
        flash(f'A tournament with a similar name already exists ("{new_slug}").', 'error')
        return redirect(url_for('tournaments'))

    source_path = os.path.join(g.user_tournaments_dir, source_slug)
    dest_path = os.path.join(g.user_tournaments_dir, new_slug)

    if not os.path.isdir(source_path):
        flash('Source tournament data not found.', 'error')
        return redirect(url_for('tournaments'))

    shutil.copytree(source_path, dest_path)

    # Update tournament_name in the cloned constraints
    cloned_constraints_path = os.path.join(dest_path, 'constraints.yaml')
    if os.path.exists(cloned_constraints_path):
        try:
            with open(cloned_constraints_path, 'r', encoding='utf-8') as f:
                constraints = yaml.safe_load(f) or {}
            constraints['tournament_name'] = new_name
            with open(cloned_constraints_path, 'w', encoding='utf-8') as f:
                yaml.dump(constraints, f, default_flow_style=False)
        except Exception:
            pass  # Non-critical — name can be fixed manually

    data['tournaments'].append({
        'slug': new_slug,
        'name': new_name,
        'created': datetime.now().isoformat()
    })
    data['active'] = new_slug
    save_tournaments(data)

    session['active_tournament'] = new_slug
    flash(f'Tournament "{new_name}" cloned from "{source_slug}".', 'success')
    return redirect(url_for('tournaments'))


@app.route('/api/tournaments/switch', methods=['POST'])
def api_switch_tournament():
    """Switch active tournament."""
    slug = request.form.get('slug', '').strip()
    data = load_tournaments()

    if not any(t['slug'] == slug for t in data.get('tournaments', [])):
        flash('Tournament not found.', 'error')
        return redirect(url_for('tournaments'))

    data['active'] = slug
    save_tournaments(data)
    session['active_tournament'] = slug

    name = next((t['name'] for t in data['tournaments'] if t['slug'] == slug), slug)
    flash(f'Switched to "{name}".', 'success')
    return redirect(url_for('index'))


if __name__ == '__main__':
    app.run(debug=True, port=5000)
