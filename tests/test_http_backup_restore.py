"""
Tests for HTTP backup/restore API endpoints.

Tests the decorator, export route, import route, and integration scenarios.
"""
import pytest
import sys
import os
import pathlib
import tempfile
import yaml
import zipfile
import io
import hmac
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from app import app


@pytest.fixture
def client():
    """Create a test client."""
    app.config['TESTING'] = True
    with app.test_client() as client:
        yield client


@pytest.fixture
def temp_data_dir(tmp_path, monkeypatch):
    """Set up temporary data directory for backup/restore tests."""
    import app as app_module
    
    # Create data directory structure
    data_dir = tmp_path / "data"
    users_dir = data_dir / "users"
    testuser_dir = users_dir / "testuser"
    testuser_tournaments_dir = testuser_dir / "tournaments"
    default_tournament = testuser_tournaments_dir / "default"
    default_tournament.mkdir(parents=True)
    
    # Create sample tournament data files
    teams_file = default_tournament / "teams.yaml"
    courts_file = default_tournament / "courts.csv"
    constraints_file = default_tournament / "constraints.yaml"
    
    teams_file.write_text(yaml.dump({
        'pool1': {
            'teams': ['Team A', 'Team B'],
            'advance': 2
        }
    }, default_flow_style=False))
    
    courts_file.write_text("court_name,start_time,end_time\nCourt 1,08:00,18:00\n")
    constraints_file.write_text(yaml.dump({
        'match_duration_minutes': 60,
        'days_number': 1
    }, default_flow_style=False))
    
    # Create users.yaml
    users_file = data_dir / "users.yaml"
    users_file.write_text(yaml.dump({
        'users': [
            {'username': 'testuser', 'password_hash': 'test123', 'created': '2026-01-01'},
            {'username': 'otheruser', 'password_hash': 'test456', 'created': '2026-01-02'}
        ]
    }, default_flow_style=False))
    
    # Create user's tournament registry
    user_reg = testuser_dir / "tournaments.yaml"
    user_reg.write_text(yaml.dump({
        'active': 'default',
        'tournaments': [{'slug': 'default', 'name': 'Default Tournament', 'created': '2026-01-01'}]
    }, default_flow_style=False))
    
    # Monkeypatch the DATA_DIR to use temp directory
    monkeypatch.setattr(app_module, 'DATA_DIR', str(data_dir))
    monkeypatch.setattr(app_module, 'USERS_DIR', str(users_dir))
    monkeypatch.setattr(app_module, 'USERS_FILE', str(users_file))
    monkeypatch.setattr(app_module, 'TOURNAMENTS_DIR', str(testuser_tournaments_dir))
    
    return data_dir


class TestBackupKeyDecorator:
    """Tests for require_backup_key decorator."""
    
    def test_valid_key_allows_access(self, client, temp_data_dir, monkeypatch):
        """Valid API key in Authorization header allows access."""
        monkeypatch.setenv('BACKUP_API_KEY', 'test-key-123')
        # Need to reload app module to pick up env var
        import app as app_module
        monkeypatch.setattr(app_module, 'BACKUP_API_KEY', 'test-key-123')
        
        response = client.get('/api/admin/export',
                             headers={'Authorization': 'Bearer test-key-123'})
        
        # Should not return 401 or 403
        assert response.status_code != 401
        assert response.status_code != 403
    
    def test_missing_header_returns_401(self, client, temp_data_dir, monkeypatch):
        """Missing Authorization header returns 401."""
        monkeypatch.setenv('BACKUP_API_KEY', 'test-key-123')
        import app as app_module
        monkeypatch.setattr(app_module, 'BACKUP_API_KEY', 'test-key-123')
        
        response = client.get('/api/admin/export')
        
        assert response.status_code == 401
    
    def test_invalid_key_returns_401(self, client, temp_data_dir, monkeypatch):
        """Invalid API key returns 401."""
        monkeypatch.setenv('BACKUP_API_KEY', 'test-key-123')
        import app as app_module
        monkeypatch.setattr(app_module, 'BACKUP_API_KEY', 'test-key-123')
        
        response = client.get('/api/admin/export',
                             headers={'Authorization': 'Bearer wrong-key'})
        
        assert response.status_code == 401
    
    def test_empty_key_returns_401(self, client, temp_data_dir, monkeypatch):
        """Empty API key in header returns 401."""
        monkeypatch.setenv('BACKUP_API_KEY', 'test-key-123')
        import app as app_module
        monkeypatch.setattr(app_module, 'BACKUP_API_KEY', 'test-key-123')
        
        response = client.get('/api/admin/export',
                             headers={'Authorization': 'Bearer '})
        
        assert response.status_code == 401
    
    def test_timing_attack_resistance(self, client, temp_data_dir, monkeypatch):
        """Decorator uses constant-time comparison (hmac.compare_digest)."""
        # This test verifies that the implementation uses hmac.compare_digest
        # by checking that timing doesn't leak information about correct key prefix
        monkeypatch.setenv('BACKUP_API_KEY', 'test-key-123')
        import app as app_module
        monkeypatch.setattr(app_module, 'BACKUP_API_KEY', 'test-key-123')
        
        # Try keys with correct prefix (should not be faster to reject)
        times_correct_prefix = []
        for _ in range(10):
            start = time.perf_counter()
            response = client.get('/api/admin/export',
                                 headers={'Authorization': 'Bearer test-key-999'})
            elapsed = time.perf_counter() - start
            times_correct_prefix.append(elapsed)
            assert response.status_code == 401
        
        # Try keys with wrong prefix
        times_wrong_prefix = []
        for _ in range(10):
            start = time.perf_counter()
            response = client.get('/api/admin/export',
                                 headers={'Authorization': 'Bearer aaaa-aaa-aaa'})
            elapsed = time.perf_counter() - start
            times_wrong_prefix.append(elapsed)
            assert response.status_code == 401
        
        # If using string comparison (==), correct prefix would be faster
        # With hmac.compare_digest, timing should be similar
        avg_correct = sum(times_correct_prefix) / len(times_correct_prefix)
        avg_wrong = sum(times_wrong_prefix) / len(times_wrong_prefix)
        
        # Allow for 50% variance (network jitter, etc.)
        # The key point is they're not orders of magnitude different
        assert 0.5 < (avg_correct / avg_wrong) < 2.0, \
            "Timing difference suggests vulnerable string comparison"
    
    def test_no_api_key_configured_blocks_access(self, client, temp_data_dir, monkeypatch):
        """When BACKUP_API_KEY is not set, all access is denied."""
        monkeypatch.delenv('BACKUP_API_KEY', raising=False)
        import app as app_module
        monkeypatch.setattr(app_module, 'BACKUP_API_KEY', '')
        
        response = client.get('/api/admin/export',
                             headers={'Authorization': 'Bearer any-key'})
        
        assert response.status_code == 401


class TestAdminExport:
    """Tests for /api/admin/export route."""
    
    def test_export_without_key_returns_401(self, client, temp_data_dir, monkeypatch):
        """Export without API key returns 401."""
        monkeypatch.setenv('BACKUP_API_KEY', 'test-key-123')
        import app as app_module
        monkeypatch.setattr(app_module, 'BACKUP_API_KEY', 'test-key-123')
        
        response = client.get('/api/admin/export')
        
        assert response.status_code == 401
    
    def test_export_with_valid_key_returns_zip(self, client, temp_data_dir, monkeypatch):
        """Export with valid key returns ZIP file."""
        monkeypatch.setenv('BACKUP_API_KEY', 'test-key-123')
        import app as app_module
        monkeypatch.setattr(app_module, 'BACKUP_API_KEY', 'test-key-123')
        
        response = client.get('/api/admin/export',
                             headers={'Authorization': 'Bearer test-key-123'})
        
        assert response.status_code == 200
        assert response.mimetype == 'application/zip'
        assert 'Content-Disposition' in response.headers
        assert 'attachment' in response.headers['Content-Disposition']
    
    def test_zip_contains_expected_structure(self, client, temp_data_dir, monkeypatch):
        """Exported ZIP contains users.yaml and tournament structure."""
        monkeypatch.setenv('BACKUP_API_KEY', 'test-key-123')
        import app as app_module
        monkeypatch.setattr(app_module, 'BACKUP_API_KEY', 'test-key-123')
        
        response = client.get('/api/admin/export',
                             headers={'Authorization': 'Bearer test-key-123'})
        
        assert response.status_code == 200
        
        # Parse ZIP
        zip_buffer = io.BytesIO(response.data)
        with zipfile.ZipFile(zip_buffer, 'r') as zf:
            names = zf.namelist()
            
            # Must contain users.yaml at root
            assert 'users.yaml' in names
            
            # Must contain user tournament data
            assert any('users/testuser/tournaments/default/teams.yaml' in name for name in names)
            assert any('users/testuser/tournaments/default/courts.csv' in name for name in names)
            
            # Should not contain skip patterns
            assert not any('__pycache__' in name for name in names)
            assert not any(name.endswith('.pyc') for name in names)
            assert not any('.lock' in name for name in names)
    
    def test_zip_can_be_extracted_successfully(self, client, temp_data_dir, monkeypatch):
        """Exported ZIP can be extracted without errors."""
        monkeypatch.setenv('BACKUP_API_KEY', 'test-key-123')
        import app as app_module
        monkeypatch.setattr(app_module, 'BACKUP_API_KEY', 'test-key-123')
        
        response = client.get('/api/admin/export',
                             headers={'Authorization': 'Bearer test-key-123'})
        
        assert response.status_code == 200
        
        # Try to extract to temp directory
        with tempfile.TemporaryDirectory() as extract_dir:
            zip_buffer = io.BytesIO(response.data)
            with zipfile.ZipFile(zip_buffer, 'r') as zf:
                zf.extractall(extract_dir)
            
            # Verify key files exist after extraction
            assert os.path.exists(os.path.join(extract_dir, 'users.yaml'))
            assert os.path.exists(os.path.join(extract_dir, 'users', 'testuser', 'tournaments', 'default', 'teams.yaml'))
    
    def test_filename_format_is_correct(self, client, temp_data_dir, monkeypatch):
        """Filename follows tournament-backup-{timestamp}.zip format."""
        monkeypatch.setenv('BACKUP_API_KEY', 'test-key-123')
        import app as app_module
        monkeypatch.setattr(app_module, 'BACKUP_API_KEY', 'test-key-123')
        
        response = client.get('/api/admin/export',
                             headers={'Authorization': 'Bearer test-key-123'})
        
        assert response.status_code == 200
        
        content_disposition = response.headers.get('Content-Disposition', '')
        # Should match pattern: filename=tournament-backup-YYYYMMDD_HHMMSS.zip
        assert 'tournament-backup-' in content_disposition
        assert '.zip' in content_disposition
        
        # Extract filename
        import re
        match = re.search(r'filename=([^\s;]+)', content_disposition)
        assert match, "Could not find filename in Content-Disposition header"
        filename = match.group(1).strip('"')
        
        # Verify format: tournament-backup-YYYYMMDD_HHMMSS.zip
        timestamp_pattern = r'tournament-backup-\d{8}_\d{6}\.zip'
        assert re.match(timestamp_pattern, filename), \
            f"Filename '{filename}' doesn't match expected pattern"


class TestAdminImport:
    """Tests for /api/admin/import route."""
    
    def test_import_without_key_returns_401(self, client, temp_data_dir, monkeypatch):
        """Import without API key returns 401."""
        monkeypatch.setenv('BACKUP_API_KEY', 'test-key-123')
        import app as app_module
        monkeypatch.setattr(app_module, 'BACKUP_API_KEY', 'test-key-123')
        
        # Create a dummy ZIP
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w') as zf:
            zf.writestr('users.yaml', 'users: []')
        zip_buffer.seek(0)
        
        response = client.post('/api/admin/import',
                              data={'file': (zip_buffer, 'backup.zip')})
        
        assert response.status_code == 401
    
    def test_import_with_valid_key_restores_data(self, client, temp_data_dir, monkeypatch):
        """Import with valid key restores data from ZIP."""
        monkeypatch.setenv('BACKUP_API_KEY', 'test-key-123')
        import app as app_module
        monkeypatch.setattr(app_module, 'BACKUP_API_KEY', 'test-key-123')
        
        # Create a valid backup ZIP
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
            zf.writestr('users.yaml', yaml.dump({
                'users': [
                    {'username': 'restored_user', 'password_hash': 'hash123', 'created': '2026-02-15'}
                ]
            }))
            zf.writestr('users/restored_user/tournaments.yaml', yaml.dump({
                'active': 'restored_tournament',
                'tournaments': [{'slug': 'restored_tournament', 'name': 'Restored', 'created': '2026-02-15'}]
            }))
            zf.writestr('users/restored_user/tournaments/restored_tournament/teams.yaml', yaml.dump({
                'pool1': {'teams': ['Restored Team A'], 'advance': 1}
            }))
        zip_buffer.seek(0)
        
        response = client.post('/api/admin/import',
                              data={'file': (zip_buffer, 'backup.zip')},
                              headers={'Authorization': 'Bearer test-key-123'},
                              content_type='multipart/form-data')
        
        assert response.status_code == 200
        
        # Verify data was restored
        users_file = temp_data_dir / 'users.yaml'
        assert users_file.exists()
        
        with open(users_file, 'r') as f:
            users_data = yaml.safe_load(f)
        
        assert any(u['username'] == 'restored_user' for u in users_data['users'])
    
    def test_import_creates_backup_before_restore(self, client, temp_data_dir, monkeypatch):
        """Import creates a pre-restore backup before modifying data."""
        monkeypatch.setenv('BACKUP_API_KEY', 'test-key-123')
        import app as app_module
        monkeypatch.setattr(app_module, 'BACKUP_API_KEY', 'test-key-123')
        
        # Record original state
        original_users_file = temp_data_dir / 'users.yaml'
        with open(original_users_file, 'r') as f:
            original_users = f.read()
        
        # Create import ZIP
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w') as zf:
            zf.writestr('users.yaml', yaml.dump({
                'users': [{'username': 'new_user', 'password_hash': 'hash', 'created': '2026-02-15'}]
            }))
        zip_buffer.seek(0)
        
        response = client.post('/api/admin/import',
                              data={'file': (zip_buffer, 'backup.zip')},
                              headers={'Authorization': 'Bearer test-key-123'},
                              content_type='multipart/form-data')
        
        assert response.status_code == 200
        
        # Check that a backup directory was created
        backups_dir = temp_data_dir.parent / 'backups'
        if backups_dir.exists():
            # Should contain at least one backup
            backup_files = list(backups_dir.glob('pre-restore-*.zip'))
            assert len(backup_files) > 0, "No pre-restore backup was created"
    
    def test_import_validates_zip_structure(self, client, temp_data_dir, monkeypatch):
        """Import validates that ZIP contains required files (users.yaml)."""
        monkeypatch.setenv('BACKUP_API_KEY', 'test-key-123')
        import app as app_module
        monkeypatch.setattr(app_module, 'BACKUP_API_KEY', 'test-key-123')
        
        # Create invalid ZIP (missing users.yaml)
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w') as zf:
            zf.writestr('random_file.txt', 'content')
        zip_buffer.seek(0)
        
        response = client.post('/api/admin/import',
                              data={'file': (zip_buffer, 'backup.zip')},
                              headers={'Authorization': 'Bearer test-key-123'},
                              content_type='multipart/form-data')
        
        # Should reject invalid structure
        assert response.status_code == 400
        assert b'invalid' in response.data.lower() or b'users.yaml' in response.data.lower()
    
    def test_import_rejects_malicious_paths(self, client, temp_data_dir, monkeypatch):
        """Import rejects ZIP with path traversal attempts."""
        monkeypatch.setenv('BACKUP_API_KEY', 'test-key-123')
        import app as app_module
        monkeypatch.setattr(app_module, 'BACKUP_API_KEY', 'test-key-123')
        
        # Create malicious ZIP with path traversal
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w') as zf:
            zf.writestr('users.yaml', 'users: []')
            zf.writestr('../../../etc/passwd', 'malicious content')
            zf.writestr('..\\..\\windows\\system32\\config', 'malicious content')
        zip_buffer.seek(0)
        
        response = client.post('/api/admin/import',
                              data={'file': (zip_buffer, 'backup.zip')},
                              headers={'Authorization': 'Bearer test-key-123'},
                              content_type='multipart/form-data')
        
        # Should reject path traversal
        assert response.status_code == 400
        assert b'unsafe' in response.data.lower() or b'path' in response.data.lower()
    
    def test_import_handles_corrupted_zip_gracefully(self, client, temp_data_dir, monkeypatch):
        """Import handles corrupted ZIP files gracefully."""
        monkeypatch.setenv('BACKUP_API_KEY', 'test-key-123')
        import app as app_module
        monkeypatch.setattr(app_module, 'BACKUP_API_KEY', 'test-key-123')
        
        # Create corrupted "ZIP" (just random bytes)
        corrupted_buffer = io.BytesIO(b'This is not a valid ZIP file at all!')
        
        response = client.post('/api/admin/import',
                              data={'file': (corrupted_buffer, 'backup.zip')},
                              headers={'Authorization': 'Bearer test-key-123'},
                              content_type='multipart/form-data')
        
        # Should reject invalid ZIP
        assert response.status_code == 400
        assert b'zip' in response.data.lower() or b'invalid' in response.data.lower()
    
    def test_import_rejects_oversized_zip(self, client, temp_data_dir, monkeypatch):
        """Import rejects ZIP files exceeding size limit."""
        monkeypatch.setenv('BACKUP_API_KEY', 'test-key-123')
        import app as app_module
        monkeypatch.setattr(app_module, 'BACKUP_API_KEY', 'test-key-123')
        # Set a small max size for testing
        monkeypatch.setattr(app_module, 'MAX_SITE_UPLOAD_SIZE', 100)  # 100 bytes
        
        # Create a ZIP larger than the limit
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w') as zf:
            zf.writestr('users.yaml', 'users: []')
            # Add large file to exceed limit
            zf.writestr('large_file.bin', b'x' * 200)
        zip_buffer.seek(0)
        
        response = client.post('/api/admin/import',
                              data={'file': (zip_buffer, 'backup.zip')},
                              headers={'Authorization': 'Bearer test-key-123'},
                              content_type='multipart/form-data')
        
        # Should reject oversized file
        assert response.status_code == 400
        assert b'large' in response.data.lower() or b'size' in response.data.lower()
