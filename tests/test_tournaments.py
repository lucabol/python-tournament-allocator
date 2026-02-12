"""
Tests for multi-tournament support.

Written proactively from design spec:
- Tournaments stored as subdirectories under data/tournaments/<slug>/
- data/tournaments.yaml tracks list + active tournament
- Session-based active tournament via @app.before_request + g.data_dir
- Legacy flat files auto-migrate to data/tournaments/default/
- New routes: GET /tournaments, POST /api/tournaments/create,
  /api/tournaments/delete, /api/tournaments/switch
"""
import pytest
import sys
import os
import yaml

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from app import app


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

TOURNAMENT_DATA_FILES = ['teams.yaml', 'courts.csv', 'constraints.yaml']


@pytest.fixture
def client():
    """Create an authenticated test client."""
    app.config['TESTING'] = True
    with app.test_client() as client:
        with client.session_transaction() as sess:
            sess['user'] = 'testuser'
        yield client


@pytest.fixture
def tournament_dir(tmp_path, monkeypatch):
    """Set up a temporary data directory wired for multi-tournament support with auth.

    Creates user-scoped structure:
        tmp_path/
            users.yaml
            users/
                testuser/
                    tournaments.yaml          (registry)
                    tournaments/
                        default/
                            teams.yaml
                            courts.csv
                            constraints.yaml
    Returns the testuser directory so test assertions like
    ``tournament_dir / 'tournaments' / slug`` resolve correctly.
    """
    import app as app_module

    # Build user-scoped directory structure
    users_dir = tmp_path / 'users'
    testuser_dir = users_dir / 'testuser'
    tournaments_dir = testuser_dir / 'tournaments'

    # Seed a "default" tournament
    default_dir = tournaments_dir / 'default'
    default_dir.mkdir(parents=True)
    (default_dir / 'teams.yaml').write_text('')
    (default_dir / 'courts.csv').write_text('court_name,start_time,end_time\n')
    (default_dir / 'constraints.yaml').write_text('')

    # User's tournament registry
    registry = {
        'tournaments': [{'name': 'Default', 'slug': 'default'}],
        'active': 'default',
    }
    (testuser_dir / 'tournaments.yaml').write_text(
        yaml.dump(registry, default_flow_style=False))

    # Auth: create users.yaml so ensure_tournament_structure() skips migration
    users_file = tmp_path / 'users.yaml'
    users_file.write_text(yaml.dump({'users': [
        {'username': 'testuser', 'password_hash': 'unused', 'created': '2026-01-01'}
    ]}, default_flow_style=False))

    # Global registry stub
    global_reg = tmp_path / 'tournaments.yaml'
    global_reg.write_text(yaml.dump({'active': None, 'tournaments': []}, default_flow_style=False))

    # Patch module-level paths
    monkeypatch.setattr(app_module, 'DATA_DIR', str(default_dir))
    monkeypatch.setattr(app_module, 'TOURNAMENTS_DIR', str(tournaments_dir))
    monkeypatch.setattr(app_module, 'TOURNAMENTS_FILE', str(global_reg))
    monkeypatch.setattr(app_module, 'USERS_FILE', str(users_file))
    monkeypatch.setattr(app_module, 'USERS_DIR', str(users_dir))

    # Point per-request file paths into the default tournament dir
    monkeypatch.setattr(app_module, 'TEAMS_FILE', str(default_dir / 'teams.yaml'))
    monkeypatch.setattr(app_module, 'COURTS_FILE', str(default_dir / 'courts.csv'))
    monkeypatch.setattr(app_module, 'CONSTRAINTS_FILE', str(default_dir / 'constraints.yaml'))
    monkeypatch.setattr(app_module, 'RESULTS_FILE', str(default_dir / 'results.yaml'))
    monkeypatch.setattr(app_module, 'SCHEDULE_FILE', str(default_dir / 'schedule.yaml'))
    monkeypatch.setattr(app_module, 'PRINT_SETTINGS_FILE', str(default_dir / 'print_settings.yaml'))
    monkeypatch.setattr(app_module, 'LOGO_FILE_PREFIX', str(default_dir / 'logo'))

    exportable = {
        'teams.yaml': str(default_dir / 'teams.yaml'),
        'courts.csv': str(default_dir / 'courts.csv'),
        'constraints.yaml': str(default_dir / 'constraints.yaml'),
        'results.yaml': str(default_dir / 'results.yaml'),
        'schedule.yaml': str(default_dir / 'schedule.yaml'),
        'print_settings.yaml': str(default_dir / 'print_settings.yaml'),
    }
    monkeypatch.setattr(app_module, 'EXPORTABLE_FILES', exportable)
    monkeypatch.setattr(app_module, 'ALLOWED_IMPORT_NAMES', set(exportable.keys()))

    return testuser_dir


def _read_registry(data_dir):
    """Helper: load the tournaments.yaml registry from *data_dir*."""
    registry_path = data_dir / 'tournaments.yaml'
    if not registry_path.exists():
        return {'tournaments': [], 'active': None}
    with open(registry_path, 'r', encoding='utf-8') as f:
        return yaml.safe_load(f) or {'tournaments': [], 'active': None}


def _tournament_slugs(data_dir):
    """Return the list of slugs in the registry."""
    reg = _read_registry(data_dir)
    return [t['slug'] for t in reg.get('tournaments', [])]


# ---------------------------------------------------------------------------
# TestTournamentCreation
# ---------------------------------------------------------------------------

class TestTournamentCreation:
    """Tests for creating new tournaments."""

    def test_create_tournament(self, client, tournament_dir):
        """POST name → directory created and registry updated."""
        response = client.post(
            '/api/tournaments/create',
            data={'name': 'Spring Cup'},
            follow_redirects=True,
        )
        assert response.status_code == 200

        # Directory must exist under tournaments/
        slug = 'spring-cup'
        tourney_path = tournament_dir / 'tournaments' / slug
        assert tourney_path.is_dir()

        # Core data files should be seeded
        for fname in TOURNAMENT_DATA_FILES:
            assert (tourney_path / fname).exists()

        # Registry must list it
        assert slug in _tournament_slugs(tournament_dir)

    def test_create_tournament_empty_name(self, client, tournament_dir):
        """Empty name should flash an error and create nothing."""
        before = _tournament_slugs(tournament_dir)
        response = client.post(
            '/api/tournaments/create',
            data={'name': ''},
            follow_redirects=True,
        )
        assert response.status_code == 200
        # Should see an error flash
        assert b'error' in response.data.lower() or b'name' in response.data.lower()

        # No new directories created
        assert _tournament_slugs(tournament_dir) == before

    def test_create_duplicate_tournament(self, client, tournament_dir):
        """Creating a tournament whose slug already exists should flash error."""
        client.post('/api/tournaments/create', data={'name': 'Spring Cup'})

        response = client.post(
            '/api/tournaments/create',
            data={'name': 'Spring Cup'},
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert b'already exists' in response.data.lower() or b'duplicate' in response.data.lower()

        # Only one copy in the registry
        slugs = _tournament_slugs(tournament_dir)
        assert slugs.count('spring-cup') == 1

    def test_create_tournament_special_chars(self, client, tournament_dir):
        """Name with spaces and special characters should produce a valid slug."""
        response = client.post(
            '/api/tournaments/create',
            data={'name': '  Summer Tournament 2026!  '},
            follow_redirects=True,
        )
        assert response.status_code == 200

        # A tournament directory should have been created with a sanitised slug
        tournaments_path = tournament_dir / 'tournaments'
        new_dirs = [
            d.name for d in tournaments_path.iterdir()
            if d.is_dir() and d.name != 'default'
        ]
        assert len(new_dirs) == 1
        slug = new_dirs[0]

        # Slug should only contain lowercase, digits, and hyphens
        assert slug == slug.lower()
        assert all(c.isalnum() or c == '-' for c in slug)

    def test_create_tournament_switches_to_new(self, client, tournament_dir):
        """After creation the newly created tournament should become active."""
        client.post('/api/tournaments/create', data={'name': 'Fall Open'})

        reg = _read_registry(tournament_dir)
        assert reg['active'] == 'fall-open'


# ---------------------------------------------------------------------------
# TestTournamentDeletion
# ---------------------------------------------------------------------------

class TestTournamentDeletion:
    """Tests for deleting tournaments."""

    def _create(self, client, name):
        client.post('/api/tournaments/create', data={'name': name})

    def test_delete_tournament(self, client, tournament_dir):
        """Deleting a tournament removes its directory and registry entry."""
        self._create(client, 'Throwaway')

        response = client.post(
            '/api/tournaments/delete',
            data={'slug': 'throwaway'},
            follow_redirects=True,
        )
        assert response.status_code == 200

        assert not (tournament_dir / 'tournaments' / 'throwaway').exists()
        assert 'throwaway' not in _tournament_slugs(tournament_dir)

    def test_delete_active_tournament(self, client, tournament_dir):
        """Deleting the active tournament should switch active to another one."""
        self._create(client, 'A')
        self._create(client, 'B')

        # B is active after creation
        reg = _read_registry(tournament_dir)
        assert reg['active'] == 'b'

        # Delete B
        client.post('/api/tournaments/delete', data={'slug': 'b'}, follow_redirects=True)

        reg = _read_registry(tournament_dir)
        assert reg['active'] is not None
        assert reg['active'] != 'b'
        # Should have fallen back to one of the remaining tournaments
        assert reg['active'] in _tournament_slugs(tournament_dir)

    def test_delete_last_tournament(self, client, tournament_dir):
        """Deleting the only remaining tournament sets active to None."""
        # Remove the seeded 'default' tournament
        client.post('/api/tournaments/delete', data={'slug': 'default'}, follow_redirects=True)

        reg = _read_registry(tournament_dir)
        assert reg['active'] is None
        assert len(reg.get('tournaments', [])) == 0

    def test_delete_path_traversal(self, client, tournament_dir):
        """Slug containing '..' must be rejected to prevent path traversal."""
        # Place a canary file above the tournaments directory
        canary = tournament_dir / 'canary.txt'
        canary.write_text('do not delete')

        response = client.post(
            '/api/tournaments/delete',
            data={'slug': '../canary'},
            follow_redirects=True,
        )
        assert response.status_code in (200, 400)

        # Canary must survive
        assert canary.exists()
        assert canary.read_text() == 'do not delete'


# ---------------------------------------------------------------------------
# TestTournamentSwitch
# ---------------------------------------------------------------------------

class TestTournamentSwitch:
    """Tests for switching the active tournament."""

    def test_switch_tournament(self, client, tournament_dir):
        """Switching active tournament updates registry and session."""
        # Create a second tournament
        client.post('/api/tournaments/create', data={'name': 'Second'})

        # Switch back to default
        response = client.post(
            '/api/tournaments/switch',
            data={'slug': 'default'},
            follow_redirects=True,
        )
        assert response.status_code == 200

        reg = _read_registry(tournament_dir)
        assert reg['active'] == 'default'

    def test_switch_nonexistent(self, client, tournament_dir):
        """Switching to a slug that doesn't exist should flash an error."""
        response = client.post(
            '/api/tournaments/switch',
            data={'slug': 'does-not-exist'},
            follow_redirects=True,
        )
        assert response.status_code == 200
        assert (
            b'not found' in response.data.lower()
            or b'does not exist' in response.data.lower()
            or b'error' in response.data.lower()
        )

        # Active should remain unchanged
        reg = _read_registry(tournament_dir)
        assert reg['active'] == 'default'


# ---------------------------------------------------------------------------
# TestTournamentMigration
# ---------------------------------------------------------------------------

class TestTournamentMigration:
    """Tests for automatic migration to user-scoped tournament structure."""

    def test_legacy_migration(self, tmp_path, monkeypatch, client):
        """Flat files in data/ get migrated through to admin user's tournaments."""
        import app as app_module

        data_dir = tmp_path
        tournaments_dir = data_dir / 'tournaments'
        registry_file = data_dir / 'tournaments.yaml'
        users_file = data_dir / 'users.yaml'
        users_dir = data_dir / 'users'

        # Simulate legacy layout: data files sitting directly in data/
        (data_dir / 'teams.yaml').write_text('Pool A:\n  teams: [Alpha]\n  advance: 2\n')
        (data_dir / 'courts.csv').write_text('court_name,start_time,end_time\nCourt 1,08:00,22:00\n')
        (data_dir / 'constraints.yaml').write_text('match_duration_minutes: 30\n')

        # No tournaments directory, no registry, no users
        assert not tournaments_dir.exists()
        assert not registry_file.exists()
        assert not users_file.exists()

        monkeypatch.setattr(app_module, 'DATA_DIR', str(data_dir))
        monkeypatch.setattr(app_module, 'TOURNAMENTS_DIR', str(tournaments_dir))
        monkeypatch.setattr(app_module, 'TOURNAMENTS_FILE', str(registry_file))
        monkeypatch.setattr(app_module, 'USERS_FILE', str(users_file))
        monkeypatch.setattr(app_module, 'USERS_DIR', str(users_dir))

        # Trigger migration via before_request
        app_module.app.config['TESTING'] = True
        with app_module.app.test_client() as c:
            c.get('/tournaments')

        # Files should be migrated to admin user's tournament dir
        admin_default = users_dir / 'admin' / 'tournaments' / 'default'
        assert admin_default.is_dir()
        assert (admin_default / 'teams.yaml').exists()
        assert 'Alpha' in (admin_default / 'teams.yaml').read_text()

        # users.yaml should exist with admin user
        assert users_file.exists()
        import yaml as _yaml
        users_data = _yaml.safe_load(users_file.read_text())
        assert any(u['username'] == 'admin' for u in users_data.get('users', []))

    def test_migration_idempotent(self, tmp_path, monkeypatch, client):
        """Running migration again when already migrated does nothing."""
        import app as app_module

        data_dir = tmp_path
        tournaments_dir = data_dir / 'tournaments'
        tournaments_dir.mkdir()
        registry_file = data_dir / 'tournaments.yaml'
        users_file = data_dir / 'users.yaml'
        users_dir = data_dir / 'users'

        # Already-migrated state: users.yaml exists
        users_file.write_text(yaml.dump({'users': [
            {'username': 'admin', 'password_hash': 'hashed', 'created': '2026-01-01'}
        ]}, default_flow_style=False))

        # Admin user's tournament dir
        admin_dir = users_dir / 'admin' / 'tournaments' / 'default'
        admin_dir.mkdir(parents=True)
        teams_content = 'Pool X:\n  teams: [Beta]\n  advance: 1\n'
        (admin_dir / 'teams.yaml').write_text(teams_content)
        (admin_dir / 'courts.csv').write_text('court_name,start_time,end_time\n')
        (admin_dir / 'constraints.yaml').write_text('')

        (users_dir / 'admin' / 'tournaments.yaml').write_text(yaml.dump({
            'tournaments': [{'name': 'Default', 'slug': 'default'}],
            'active': 'default',
        }, default_flow_style=False))

        registry_file.write_text(yaml.dump({
            'tournaments': [{'name': 'Default', 'slug': 'default'}],
            'active': 'default',
        }, default_flow_style=False))

        monkeypatch.setattr(app_module, 'DATA_DIR', str(data_dir))
        monkeypatch.setattr(app_module, 'TOURNAMENTS_DIR', str(tournaments_dir))
        monkeypatch.setattr(app_module, 'TOURNAMENTS_FILE', str(registry_file))
        monkeypatch.setattr(app_module, 'USERS_FILE', str(users_file))
        monkeypatch.setattr(app_module, 'USERS_DIR', str(users_dir))

        monkeypatch.setattr(app_module, 'TEAMS_FILE', str(admin_dir / 'teams.yaml'))
        monkeypatch.setattr(app_module, 'COURTS_FILE', str(admin_dir / 'courts.csv'))
        monkeypatch.setattr(app_module, 'CONSTRAINTS_FILE', str(admin_dir / 'constraints.yaml'))
        monkeypatch.setattr(app_module, 'RESULTS_FILE', str(admin_dir / 'results.yaml'))
        monkeypatch.setattr(app_module, 'SCHEDULE_FILE', str(admin_dir / 'schedule.yaml'))
        monkeypatch.setattr(app_module, 'PRINT_SETTINGS_FILE', str(admin_dir / 'print_settings.yaml'))
        monkeypatch.setattr(app_module, 'LOGO_FILE_PREFIX', str(admin_dir / 'logo'))

        app_module.app.config['TESTING'] = True
        with app_module.app.test_client() as c:
            with c.session_transaction() as sess:
                sess['user'] = 'admin'
            c.get('/tournaments')

        # Data should be untouched
        assert (admin_dir / 'teams.yaml').read_text() == teams_content

    def test_fresh_install(self, tmp_path, monkeypatch, client):
        """Empty data directory creates users.yaml for fresh install."""
        import app as app_module

        data_dir = tmp_path
        tournaments_dir = data_dir / 'tournaments'
        registry_file = data_dir / 'tournaments.yaml'
        users_file = data_dir / 'users.yaml'
        users_dir = data_dir / 'users'

        # Completely empty — no legacy files, no tournaments, no users
        monkeypatch.setattr(app_module, 'DATA_DIR', str(data_dir))
        monkeypatch.setattr(app_module, 'TOURNAMENTS_DIR', str(tournaments_dir))
        monkeypatch.setattr(app_module, 'TOURNAMENTS_FILE', str(registry_file))
        monkeypatch.setattr(app_module, 'USERS_FILE', str(users_file))
        monkeypatch.setattr(app_module, 'USERS_DIR', str(users_dir))

        app_module.app.config['TESTING'] = True
        with app_module.app.test_client() as c:
            c.get('/tournaments')

        # users.yaml should be created (fresh install — no admin, just empty)
        assert users_file.exists()
        import yaml as _yaml
        users_data = _yaml.safe_load(users_file.read_text())
        assert users_data == {'users': []}


# ---------------------------------------------------------------------------
# TestTournamentIsolation
# ---------------------------------------------------------------------------

class TestTournamentIsolation:
    """Tests that tournament data is properly isolated."""

    def test_data_isolation(self, client, tournament_dir):
        """Changes in one tournament must not affect another."""
        # Create two tournaments
        client.post('/api/tournaments/create', data={'name': 'Alpha Cup'})
        client.post('/api/tournaments/create', data={'name': 'Beta Cup'})

        # Write team data directly into Alpha Cup's directory
        alpha_teams = tournament_dir / 'tournaments' / 'alpha-cup' / 'teams.yaml'
        alpha_teams.write_text('Pool 1:\n  teams: [Team X]\n  advance: 2\n')

        beta_teams = tournament_dir / 'tournaments' / 'beta-cup' / 'teams.yaml'
        beta_teams.write_text('Pool 2:\n  teams: [Team Y]\n  advance: 2\n')

        # Switch to Alpha Cup and verify its teams
        client.post('/api/tournaments/switch', data={'slug': 'alpha-cup'})
        alpha_resp = client.get('/teams')
        assert alpha_resp.status_code == 200
        assert b'Team X' in alpha_resp.data
        assert b'Team Y' not in alpha_resp.data

        # Switch to Beta Cup and verify its teams
        client.post('/api/tournaments/switch', data={'slug': 'beta-cup'})
        beta_resp = client.get('/teams')
        assert beta_resp.status_code == 200
        assert b'Team Y' in beta_resp.data
        assert b'Team X' not in beta_resp.data

    def test_export_scoped_to_tournament(self, client, tournament_dir):
        """Export only includes the active tournament's data files."""
        import io
        import zipfile

        # Create two tournaments with distinct team data
        client.post('/api/tournaments/create', data={'name': 'Export A'})
        a_teams = tournament_dir / 'tournaments' / 'export-a' / 'teams.yaml'
        a_teams.write_text('Pool EA:\n  teams: [EA1]\n  advance: 1\n')

        client.post('/api/tournaments/create', data={'name': 'Export B'})
        b_teams = tournament_dir / 'tournaments' / 'export-b' / 'teams.yaml'
        b_teams.write_text('Pool EB:\n  teams: [EB1]\n  advance: 1\n')

        # Switch to Export A and export
        client.post('/api/tournaments/switch', data={'slug': 'export-a'})
        response = client.get('/api/export/tournament')
        assert response.status_code == 200

        zf = zipfile.ZipFile(io.BytesIO(response.data))
        teams_data = zf.read('teams.yaml').decode('utf-8')
        assert 'EA1' in teams_data
        assert 'EB1' not in teams_data


# ---------------------------------------------------------------------------
# TestTournamentList
# ---------------------------------------------------------------------------

class TestTournamentList:
    """Tests for the tournament list page."""

    def test_tournaments_page(self, client, tournament_dir):
        """GET /tournaments returns 200 with the tournament list."""
        # Create a couple of tournaments
        client.post('/api/tournaments/create', data={'name': 'Tourney One'})
        client.post('/api/tournaments/create', data={'name': 'Tourney Two'})

        response = client.get('/tournaments')
        assert response.status_code == 200
        assert b'Tourney One' in response.data
        assert b'Tourney Two' in response.data
        # Default tournament should also appear
        assert b'Default' in response.data
