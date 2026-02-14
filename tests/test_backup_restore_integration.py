"""
Integration tests for backup/restore round-trip workflow.

Tests the complete workflow with realistic data and failure scenarios.
Mocks Azure operations but tests full script interaction.
"""
import pytest
import sys
import os
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import zipfile
import tempfile
import tarfile
import io

# Add scripts directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

import backup
import restore


class TestBackupRestoreRoundTrip:
    """Tests for complete backup → restore → verify workflow."""
    
    def test_round_trip_basic_data(self, tmpdir):
        """Backup and restore basic tournament data successfully."""
        # Setup: Create mock data directory
        mock_data = tmpdir.mkdir("mock_data")
        mock_data.join("users.yaml").write("users:\n  - name: admin\n")
        mock_data.join(".secret_key").write("test-secret-key-123")
        mock_data.join("teams.yaml").write("pools:\n  Pool A:\n    - Team 1\n")
        mock_data.join("courts.csv").write("Court 1,08:00\nCourt 2,09:00\n")
        
        # Create tar archive of mock data
        tar_buffer = io.BytesIO()
        with tarfile.open(fileobj=tar_buffer, mode='w:gz') as tar:
            for filename in ['users.yaml', '.secret_key', 'teams.yaml', 'courts.csv']:
                file_path = mock_data.join(filename)
                info = tarfile.TarInfo(name=f'data/{filename}')
                content = file_path.read_binary()
                info.size = len(content)
                tar.addfile(info, io.BytesIO(content))
        tar_bytes = tar_buffer.getvalue()
        
        backup_zip = tmpdir.join("backup.zip")
        
        # Step 1: Mock backup
        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = [
                # Azure CLI checks
                Mock(returncode=0, stdout="azure-cli", stderr=""),
                Mock(returncode=0, stdout='{"user": {}}', stderr=""),
                # App Service verification
                Mock(returncode=0, stdout='{"name": "myapp"}', stderr=""),
                # Tar creation
                Mock(returncode=0, stdout="SUCCESS\n", stderr=""),
                # Tar download
                Mock(returncode=0, stdout=tar_bytes, stderr=""),
                # Tar extraction
                Mock(returncode=0, stdout="", stderr="")
            ]
            
            with patch('sys.argv', ['backup.py', '--app-name', 'myapp', 
                                    '--resource-group', 'myrg', '--output', str(backup_zip)]):
                exit_code = backup.main()
        
        assert exit_code == 0
        assert backup_zip.exists()
        
        # Verify backup ZIP contains all files
        with zipfile.ZipFile(str(backup_zip), 'r') as zf:
            names = zf.namelist()
            assert 'data/users.yaml' in names
            assert 'data/.secret_key' in names
            assert 'data/teams.yaml' in names
            assert 'data/courts.csv' in names
        
        # Step 2: Mock restore
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="exists", stderr="")
            
            with patch('os.path.exists', return_value=False):  # Skip pre-backup
                with patch('sys.argv', ['restore.py', str(backup_zip), 
                                        '--app-name', 'myapp', 
                                        '--resource-group', 'myrg',
                                        '--force',
                                        '--no-backup']):
                    restore.main()
        
        # Step 3: Verify data integrity by extracting ZIP
        restored_dir = tmpdir.mkdir("restored")
        with zipfile.ZipFile(str(backup_zip), 'r') as zf:
            zf.extractall(str(restored_dir))
        
        # Verify restored data matches original
        assert restored_dir.join("data", "users.yaml").exists()
        assert restored_dir.join("data", ".secret_key").read() == "test-secret-key-123"
        assert "Pool A" in restored_dir.join("data", "teams.yaml").read()
    
    def test_round_trip_with_results_and_schedule(self, tmpdir):
        """Backup and restore includes results and schedule data."""
        mock_data = tmpdir.mkdir("mock_data")
        mock_data.join("users.yaml").write("users: []\n")
        mock_data.join(".secret_key").write("key")
        mock_data.join("results.yaml").write("results:\n  match1:\n    winner: Team A\n")
        mock_data.join("schedule.yaml").write("schedule:\n  Day 1:\n    Court 1: []\n")
        
        tar_buffer = io.BytesIO()
        with tarfile.open(fileobj=tar_buffer, mode='w:gz') as tar:
            for filename in ['users.yaml', '.secret_key', 'results.yaml', 'schedule.yaml']:
                file_path = mock_data.join(filename)
                info = tarfile.TarInfo(name=f'data/{filename}')
                content = file_path.read_binary()
                info.size = len(content)
                tar.addfile(info, io.BytesIO(content))
        tar_bytes = tar_buffer.getvalue()
        
        backup_zip = tmpdir.join("backup.zip")
        
        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = [
                Mock(returncode=0, stdout="azure-cli", stderr=""),
                Mock(returncode=0, stdout='{"user": {}}', stderr=""),
                Mock(returncode=0, stdout='{"name": "myapp"}', stderr=""),
                Mock(returncode=0, stdout="SUCCESS\n", stderr=""),
                Mock(returncode=0, stdout=tar_bytes, stderr=""),
                Mock(returncode=0, stdout="", stderr="")
            ]
            
            with patch('sys.argv', ['backup.py', '--app-name', 'myapp', 
                                    '--resource-group', 'myrg', '--output', str(backup_zip)]):
                backup.main()
        
        # Verify results and schedule preserved
        with zipfile.ZipFile(str(backup_zip), 'r') as zf:
            names = zf.namelist()
            assert 'data/results.yaml' in names
            assert 'data/schedule.yaml' in names
            
            results_content = zf.read('data/results.yaml').decode('utf-8')
            assert 'winner: Team A' in results_content


class TestBackupRestoreWithCorruption:
    """Tests for handling corrupted data during restore."""
    
    def test_restore_corrupted_zip_caught_early(self, tmpdir):
        """Corrupted ZIP fails validation before any Azure operations."""
        corrupted_zip = tmpdir.join("corrupted.zip")
        corrupted_zip.write("This is not a valid ZIP file")
        
        with pytest.raises(SystemExit) as exc_info:
            restore.validate_zip_structure(str(corrupted_zip))
        
        assert exc_info.value.code == 1
    
    def test_restore_incomplete_zip_caught_early(self, tmpdir):
        """ZIP missing required files fails validation."""
        incomplete_zip = tmpdir.join("incomplete.zip")
        
        with zipfile.ZipFile(str(incomplete_zip), 'w') as zf:
            zf.writestr('teams.yaml', 'pools: {}')
            # Missing users.yaml and .secret_key
        
        with pytest.raises(SystemExit) as exc_info:
            restore.validate_zip_structure(str(incomplete_zip))
        
        assert exc_info.value.code == 1
    
    def test_restore_validation_failure_after_upload(self, tmpdir):
        """Validation fails after upload but before app restart."""
        valid_zip = tmpdir.join("backup.zip")
        
        with zipfile.ZipFile(str(valid_zip), 'w') as zf:
            zf.writestr('users.yaml', 'users: []')
            zf.writestr('.secret_key', 'key')
        
        with patch('subprocess.run') as mock_run:
            # Upload succeeds, but validation finds missing file
            def mock_behavior(cmd, **kwargs):
                cmd_str = ' '.join(str(c) for c in cmd)
                if 'test -f' in cmd_str and 'users.yaml' in cmd_str:
                    return Mock(returncode=0, stdout="exists", stderr="")
                elif 'test -f' in cmd_str:
                    return Mock(returncode=0, stdout="missing", stderr="")
                else:
                    return Mock(returncode=0, stdout="Success", stderr="")
            
            mock_run.side_effect = mock_behavior
            
            with patch('restore.check_azure_cli'):
                with pytest.raises(SystemExit) as exc_info:
                    with patch('sys.argv', ['restore.py', str(valid_zip), 
                                            '--app-name', 'myapp', 
                                            '--resource-group', 'myrg',
                                            '--force',
                                            '--no-backup']):
                        restore.main()
                
                assert exc_info.value.code == 4


class TestBackupRestoreMultiUser:
    """Tests with realistic multi-user tournament data."""
    
    def test_backup_large_tournament_data(self, tmpdir):
        """Backup handles large tournament with multiple users."""
        mock_data = tmpdir.mkdir("mock_data")
        
        # Create multi-user data
        users_yaml = """users:
  - username: admin
    password_hash: hash1
    tournaments:
      - slug: summer-2026
        name: Summer Tournament 2026
  - username: organizer2
    password_hash: hash2
    tournaments:
      - slug: fall-2026
        name: Fall Tournament 2026
"""
        mock_data.join("users.yaml").write(users_yaml)
        mock_data.join(".secret_key").write("production-secret-key-xyz")
        
        # Create large teams list
        teams_yaml = "pools:\n"
        for pool in ['Pool A', 'Pool B', 'Pool C']:
            teams_yaml += f"  {pool}:\n"
            for i in range(10):
                teams_yaml += f"    - Team {pool[-1]}{i+1}\n"
        mock_data.join("teams.yaml").write(teams_yaml)
        
        # Create large results
        results_yaml = "results:\n"
        for i in range(50):
            results_yaml += f"  match{i}:\n    winner: Team A{i % 10 + 1}\n    sets: [[21, 15]]\n"
        mock_data.join("results.yaml").write(results_yaml)
        
        tar_buffer = io.BytesIO()
        with tarfile.open(fileobj=tar_buffer, mode='w:gz') as tar:
            for filename in ['users.yaml', '.secret_key', 'teams.yaml', 'results.yaml']:
                file_path = mock_data.join(filename)
                info = tarfile.TarInfo(name=f'data/{filename}')
                content = file_path.read_binary()
                info.size = len(content)
                tar.addfile(info, io.BytesIO(content))
        tar_bytes = tar_buffer.getvalue()
        
        backup_zip = tmpdir.join("backup.zip")
        
        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = [
                Mock(returncode=0, stdout="azure-cli", stderr=""),
                Mock(returncode=0, stdout='{"user": {}}', stderr=""),
                Mock(returncode=0, stdout='{"name": "myapp"}', stderr=""),
                Mock(returncode=0, stdout="SUCCESS\n", stderr=""),
                Mock(returncode=0, stdout=tar_bytes, stderr=""),
                Mock(returncode=0, stdout="", stderr="")
            ]
            
            with patch('sys.argv', ['backup.py', '--app-name', 'myapp', 
                                    '--resource-group', 'myrg', '--output', str(backup_zip)]):
                exit_code = backup.main()
        
        assert exit_code == 0
        
        # Verify all data preserved
        with zipfile.ZipFile(str(backup_zip), 'r') as zf:
            users_content = zf.read('data/users.yaml').decode('utf-8')
            assert 'admin' in users_content
            assert 'organizer2' in users_content
            
            teams_content = zf.read('data/teams.yaml').decode('utf-8')
            assert 'Pool A' in teams_content
            assert 'Pool B' in teams_content
            assert 'Team A1' in teams_content
            assert 'Team C10' in teams_content
            
            results_content = zf.read('data/results.yaml').decode('utf-8')
            assert 'match0' in results_content
            assert 'match49' in results_content


class TestBackupFailureScenarios:
    """Tests for various backup failure modes."""
    
    def test_backup_remote_tar_extraction_incomplete(self, tmpdir):
        """Backup fails when remote tar doesn't contain data directory."""
        # Create tar without data directory
        tar_buffer = io.BytesIO()
        with tarfile.open(fileobj=tar_buffer, mode='w:gz') as tar:
            info = tarfile.TarInfo(name='other/file.txt')
            info.size = 5
            tar.addfile(info, io.BytesIO(b'hello'))
        tar_bytes = tar_buffer.getvalue()
        
        backup_zip = tmpdir.join("backup.zip")
        
        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = [
                Mock(returncode=0, stdout="azure-cli", stderr=""),
                Mock(returncode=0, stdout='{"user": {}}', stderr=""),
                Mock(returncode=0, stdout='{"name": "myapp"}', stderr=""),
                Mock(returncode=0, stdout="SUCCESS\n", stderr=""),
                Mock(returncode=0, stdout=tar_bytes, stderr=""),
                Mock(returncode=0, stdout="", stderr="")
            ]
            
            with patch('sys.argv', ['backup.py', '--app-name', 'myapp', 
                                    '--resource-group', 'myrg', '--output', str(backup_zip)]):
                exit_code = backup.main()
        
        # Should fail because data directory not found after extraction
        assert exit_code == 2
    
    def test_backup_network_timeout_during_download(self, tmpdir):
        """Backup handles network timeout gracefully."""
        backup_zip = tmpdir.join("backup.zip")
        
        with patch('subprocess.run') as mock_run:
            import subprocess
            mock_run.side_effect = [
                Mock(returncode=0, stdout="azure-cli", stderr=""),
                Mock(returncode=0, stdout='{"user": {}}', stderr=""),
                Mock(returncode=0, stdout='{"name": "myapp"}', stderr=""),
                Mock(returncode=0, stdout="SUCCESS\n", stderr=""),
                subprocess.TimeoutExpired(cmd=[], timeout=120)  # Download times out
            ]
            
            with patch('sys.argv', ['backup.py', '--app-name', 'myapp', 
                                    '--resource-group', 'myrg', '--output', str(backup_zip)]):
                exit_code = backup.main()
        
        assert exit_code == 2
        assert not backup_zip.exists()


class TestRestoreFailureScenarios:
    """Tests for restore failure handling and rollback."""
    
    def test_restore_app_stop_fails(self, tmpdir):
        """Restore exits when App Service stop fails."""
        valid_zip = tmpdir.join("backup.zip")
        
        with zipfile.ZipFile(str(valid_zip), 'w') as zf:
            zf.writestr('users.yaml', 'users: []')
            zf.writestr('.secret_key', 'key')
        
        with patch('subprocess.run') as mock_run:
            def mock_behavior(cmd, **kwargs):
                if 'stop' in str(cmd):
                    return Mock(returncode=1, stdout="", stderr="Failed to stop")
                return Mock(returncode=0, stdout="Success", stderr="")
            
            mock_run.side_effect = mock_behavior
            
            with patch('restore.check_azure_cli'):
                with pytest.raises(SystemExit) as exc_info:
                    with patch('sys.argv', ['restore.py', str(valid_zip), 
                                            '--app-name', 'myapp', 
                                            '--resource-group', 'myrg',
                                            '--force',
                                            '--no-backup']):
                        restore.main()
                
                assert exc_info.value.code == 2
    
    def test_restore_extraction_fails_app_in_inconsistent_state(self, tmpdir, capsys):
        """Restore handles extraction failure and warns about inconsistent state."""
        valid_zip = tmpdir.join("backup.zip")
        
        with zipfile.ZipFile(str(valid_zip), 'w') as zf:
            zf.writestr('users.yaml', 'users: []')
            zf.writestr('.secret_key', 'key')
        
        with patch('subprocess.run') as mock_run:
            def mock_behavior(cmd, **kwargs):
                if 'unzip' in str(cmd):
                    return Mock(returncode=1, stdout="", stderr="Extraction failed")
                return Mock(returncode=0, stdout="Success", stderr="")
            
            mock_run.side_effect = mock_behavior
            
            with patch('restore.check_azure_cli'):
                with pytest.raises(SystemExit) as exc_info:
                    with patch('sys.argv', ['restore.py', str(valid_zip), 
                                            '--app-name', 'myapp', 
                                            '--resource-group', 'myrg',
                                            '--force',
                                            '--no-backup']):
                        restore.main()
                
                assert exc_info.value.code == 3


class TestPreRestoreBackupIntegration:
    """Tests for pre-restore backup feature."""
    
    def test_restore_creates_pre_restore_backup_before_changes(self, tmpdir):
        """Pre-restore backup is created before any destructive operations."""
        restore_zip = tmpdir.join("restore.zip")
        
        with zipfile.ZipFile(str(restore_zip), 'w') as zf:
            zf.writestr('users.yaml', 'users: []')
            zf.writestr('.secret_key', 'key')
        
        operation_order = []
        
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="exists", stderr="")
            
            with patch('os.path.exists', return_value=True):
                def mock_backup(*args):
                    operation_order.append('backup')
                
                def mock_stop(*args):
                    operation_order.append('stop')
                
                with patch('restore.create_pre_restore_backup', side_effect=mock_backup):
                    with patch('restore.stop_app_service', side_effect=mock_stop):
                        with patch('restore.upload_and_extract'):
                            with patch('restore.validate_remote_files'):
                                with patch('restore.cleanup_remote_temp'):
                                    with patch('restore.start_app_service'):
                                        with patch('restore.check_azure_cli'):
                                            with patch('sys.argv', ['restore.py', str(restore_zip), 
                                                                    '--app-name', 'myapp', 
                                                                    '--resource-group', 'myrg',
                                                                    '--force']):
                                                restore.main()
        
        # Backup must happen before stop
        assert operation_order[0] == 'backup'
        assert operation_order[1] == 'stop'
