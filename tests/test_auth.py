"""
Tests for user authentication and tournament isolation.
"""
import pytest
import sys
import os
import yaml

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from app import app, create_user, authenticate_user, load_users


@pytest.fixture
def auth_dir(tmp_path, monkeypatch):
    """Set up temp directory with auth support for testing."""
    import app as app_module

    users_dir = tmp_path / 'users'
    users_file = tmp_path / 'users.yaml'
    users_file.write_text(yaml.dump({'users': []}, default_flow_style=False))

    tournaments_file = tmp_path / 'tournaments.yaml'
    tournaments_file.write_text(yaml.dump({'active': None, 'tournaments': []}, default_flow_style=False))

    monkeypatch.setattr(app_module, 'DATA_DIR', str(tmp_path))
    monkeypatch.setattr(app_module, 'USERS_FILE', str(users_file))
    monkeypatch.setattr(app_module, 'USERS_DIR', str(users_dir))
    monkeypatch.setattr(app_module, 'TOURNAMENTS_FILE', str(tournaments_file))
    monkeypatch.setattr(app_module, 'TOURNAMENTS_DIR', str(tmp_path / 'tournaments'))

    return tmp_path


@pytest.fixture
def client():
    """Create a test client (unauthenticated by default)."""
    app.config['TESTING'] = True
    with app.test_client() as c:
        yield c


class TestUserCreation:
    """Tests for user registration."""

    def test_create_user_success(self, auth_dir):
        """Valid username and password creates a user."""
        ok, msg = create_user('alice', 'pass1234')
        assert ok is True
        assert 'created' in msg.lower()
        users = load_users()
        assert any(u['username'] == 'alice' for u in users)

    def test_create_user_short_username(self, auth_dir):
        """Username shorter than 2 chars is rejected."""
        ok, msg = create_user('a', 'pass1234')
        assert ok is False

    def test_create_user_invalid_chars(self, auth_dir):
        """Username with invalid characters is rejected."""
        ok, msg = create_user('al ice', 'pass1234')
        assert ok is False

    def test_create_user_short_password(self, auth_dir):
        """Password shorter than 4 chars is rejected."""
        ok, msg = create_user('alice', 'abc')
        assert ok is False

    def test_create_user_duplicate(self, auth_dir):
        """Duplicate username is rejected."""
        create_user('alice', 'pass1234')
        ok, msg = create_user('alice', 'otherpass')
        assert ok is False
        assert 'taken' in msg.lower()

    def test_create_user_case_insensitive(self, auth_dir):
        """Usernames are case-insensitive (lowercased)."""
        create_user('Alice', 'pass1234')
        ok, _ = create_user('alice', 'otherpass')
        assert ok is False

    def test_create_user_creates_directory(self, auth_dir):
        """Creating a user also creates their tournament directory."""
        create_user('bob', 'pass1234')
        user_dir = auth_dir / 'users' / 'bob' / 'tournaments'
        assert user_dir.is_dir()

    def test_create_user_seeds_default_tournament(self, auth_dir):
        """New user gets a default tournament with data files."""
        create_user('bob', 'pass1234')
        default_dir = auth_dir / 'users' / 'bob' / 'tournaments' / 'default'
        assert default_dir.is_dir()
        assert (default_dir / 'constraints.yaml').exists()
        assert (default_dir / 'teams.yaml').exists()
        assert (default_dir / 'courts.csv').exists()
        # Tournament registry should list the default tournament
        import yaml as _yaml
        reg = _yaml.safe_load(
            (auth_dir / 'users' / 'bob' / 'tournaments.yaml').read_text())
        assert reg['active'] == 'default'
        assert any(t['slug'] == 'default' for t in reg['tournaments'])


class TestAuthentication:
    """Tests for login authentication."""

    def test_authenticate_valid(self, auth_dir):
        """Correct credentials return True."""
        create_user('alice', 'secret123')
        assert authenticate_user('alice', 'secret123') is True

    def test_authenticate_wrong_password(self, auth_dir):
        """Wrong password returns False."""
        create_user('alice', 'secret123')
        assert authenticate_user('alice', 'wrongpass') is False

    def test_authenticate_nonexistent_user(self, auth_dir):
        """Nonexistent user returns False."""
        assert authenticate_user('nobody', 'anything') is False

    def test_authenticate_case_insensitive(self, auth_dir):
        """Authentication is case-insensitive on username."""
        create_user('alice', 'secret123')
        assert authenticate_user('Alice', 'secret123') is True


class TestAuthRoutes:
    """Tests for login, register, and logout routes."""

    def test_unauthenticated_redirects_to_login(self, auth_dir, client):
        """Unauthenticated requests to protected routes redirect to login."""
        response = client.get('/')
        assert response.status_code == 302
        assert '/login' in response.headers['Location']

    def test_login_page_renders(self, auth_dir, client):
        """Login page is accessible without auth."""
        response = client.get('/login')
        assert response.status_code == 200
        assert b'Login' in response.data

    def test_register_page_renders(self, auth_dir, client):
        """Register page is accessible without auth."""
        response = client.get('/register')
        assert response.status_code == 200
        assert b'Register' in response.data or b'Create Account' in response.data

    def test_register_and_login(self, auth_dir, client):
        """Register creates user and logs in automatically."""
        response = client.post('/register', data={
            'username': 'newuser',
            'password': 'pass1234',
            'confirm_password': 'pass1234',
        }, follow_redirects=True)
        assert response.status_code == 200
        # Should be redirected to index (logged in)
        with client.session_transaction() as sess:
            assert sess.get('user') == 'newuser'

    def test_register_password_mismatch(self, auth_dir, client):
        """Mismatched passwords show error."""
        response = client.post('/register', data={
            'username': 'newuser',
            'password': 'pass1234',
            'confirm_password': 'different',
        }, follow_redirects=True)
        assert b'match' in response.data.lower()

    def test_login_success(self, auth_dir, client):
        """Valid login sets session and redirects."""
        create_user('alice', 'secret123')
        response = client.post('/login', data={
            'username': 'alice',
            'password': 'secret123',
        })
        assert response.status_code == 302
        with client.session_transaction() as sess:
            assert sess.get('user') == 'alice'

    def test_login_failure(self, auth_dir, client):
        """Invalid login shows error."""
        create_user('alice', 'secret123')
        response = client.post('/login', data={
            'username': 'alice',
            'password': 'wrong',
        }, follow_redirects=True)
        assert b'Invalid' in response.data

    def test_logout_clears_session(self, auth_dir, client):
        """Logout clears session and redirects to login."""
        create_user('alice', 'secret123')
        client.post('/login', data={'username': 'alice', 'password': 'secret123'})
        response = client.get('/logout')
        assert response.status_code == 302
        with client.session_transaction() as sess:
            assert 'user' not in sess

    def test_logged_in_user_skips_login_page(self, auth_dir, client):
        """Already logged-in user visiting /login is redirected to index."""
        create_user('alice', 'secret123')
        client.post('/login', data={'username': 'alice', 'password': 'secret123'})
        response = client.get('/login')
        assert response.status_code == 302


class TestTournamentIsolation:
    """Tests for per-user tournament isolation."""

    def test_users_see_own_tournaments(self, auth_dir, client):
        """User A's tournaments are not visible to User B."""
        # Create two users
        create_user('alice', 'pass1234')
        create_user('bob', 'pass1234')

        # Alice creates a tournament
        client.post('/login', data={'username': 'alice', 'password': 'pass1234'})
        client.post('/api/tournaments/create', data={'name': 'Alice Cup'})

        # Check Alice sees the tournament
        response = client.get('/tournaments')
        assert b'Alice Cup' in response.data

        # Logout and login as Bob
        client.get('/logout')
        client.post('/login', data={'username': 'bob', 'password': 'pass1234'})

        # Bob should NOT see Alice's tournament
        response = client.get('/tournaments')
        assert b'Alice Cup' not in response.data

    def test_session_persistence_flag(self, auth_dir, client):
        """Login sets session.permanent = True for long-lived cookie."""
        create_user('alice', 'pass1234')
        client.post('/login', data={'username': 'alice', 'password': 'pass1234'})
        with client.session_transaction() as sess:
            assert sess.permanent is True
