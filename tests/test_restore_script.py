"""
Tests for scripts/restore.py — Azure App Service restore tool.

Mocks all Azure CLI calls to test restore workflow, validation, and rollback.
"""
import pytest
import sys
import os
from unittest.mock import Mock, patch, MagicMock, call, mock_open
from pathlib import Path
import zipfile
import tempfile

# Add scripts directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

import restore


class TestAzureCLICheck:
    """Tests for Azure CLI availability checks."""
    
    def test_azure_cli_available_and_authenticated(self):
        """Azure CLI is installed and authenticated."""
        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = [
                Mock(returncode=0, stdout="azure-cli 2.50.0", stderr=""),
                Mock(returncode=0, stdout='{"user": {...}}', stderr="")
            ]
            
            # Should not raise
            restore.check_azure_cli()
    
    def test_azure_cli_not_installed(self):
        """Exits when Azure CLI not installed."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(returncode=1, stdout="", stderr="")
            
            with pytest.raises(SystemExit) as exc_info:
                restore.check_azure_cli()
            
            assert exc_info.value.code == 1
    
    def test_azure_cli_not_authenticated(self):
        """Exits when not authenticated."""
        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = [
                Mock(returncode=0, stdout="azure-cli 2.50.0", stderr=""),
                Mock(returncode=1, stdout="", stderr="Please run 'az login'")
            ]
            
            with pytest.raises(SystemExit) as exc_info:
                restore.check_azure_cli()
            
            assert exc_info.value.code == 1


class TestZIPValidation:
    """Tests for backup ZIP structure validation."""
    
    def test_valid_zip_structure(self, tmpdir):
        """Valid ZIP with required files passes validation."""
        zip_path = tmpdir.join("backup.zip")
        
        with zipfile.ZipFile(str(zip_path), 'w') as zf:
            zf.writestr('users.yaml', 'users: []')
            zf.writestr('.secret_key', 'fake-secret-key')
            zf.writestr('teams.yaml', 'pools: {}')
        
        # Should not raise
        restore.validate_zip_structure(str(zip_path))
    
    def test_zip_file_not_found(self):
        """Exits when ZIP file doesn't exist."""
        with pytest.raises(SystemExit) as exc_info:
            restore.validate_zip_structure("/nonexistent/backup.zip")
        
        assert exc_info.value.code == 1
    
    def test_zip_missing_required_files(self, tmpdir):
        """Exits when required files are missing."""
        zip_path = tmpdir.join("backup.zip")
        
        with zipfile.ZipFile(str(zip_path), 'w') as zf:
            zf.writestr('teams.yaml', 'pools: {}')
            # Missing users.yaml and .secret_key
        
        with pytest.raises(SystemExit) as exc_info:
            restore.validate_zip_structure(str(zip_path))
        
        assert exc_info.value.code == 1
    
    def test_zip_invalid_format(self, tmpdir):
        """Exits when file is not a valid ZIP."""
        zip_path = tmpdir.join("backup.zip")
        zip_path.write("not a zip file")
        
        with pytest.raises(SystemExit) as exc_info:
            restore.validate_zip_structure(str(zip_path))
        
        assert exc_info.value.code == 1
    
    def test_zip_directory_traversal_attempt(self, tmpdir):
        """Exits when ZIP contains directory traversal paths."""
        zip_path = tmpdir.join("backup.zip")
        
        with zipfile.ZipFile(str(zip_path), 'w') as zf:
            zf.writestr('users.yaml', 'users: []')
            zf.writestr('.secret_key', 'key')
            zf.writestr('../../../etc/passwd', 'malicious')
        
        with pytest.raises(SystemExit) as exc_info:
            restore.validate_zip_structure(str(zip_path))
        
        assert exc_info.value.code == 1
    
    def test_zip_absolute_path_attempt(self, tmpdir):
        """Exits when ZIP contains absolute paths."""
        zip_path = tmpdir.join("backup.zip")
        
        with zipfile.ZipFile(str(zip_path), 'w') as zf:
            zf.writestr('users.yaml', 'users: []')
            zf.writestr('.secret_key', 'key')
            zf.writestr('/etc/passwd', 'malicious')
        
        with pytest.raises(SystemExit) as exc_info:
            restore.validate_zip_structure(str(zip_path))
        
        assert exc_info.value.code == 1


class TestPreRestoreBackup:
    """Tests for pre-restore backup creation."""
    
    def test_pre_restore_backup_success(self):
        """Pre-restore backup created successfully."""
        with patch('os.path.exists', return_value=True):
            with patch('subprocess.run') as mock_run:
                mock_run.return_value = Mock(returncode=0, stdout="Backup complete", stderr="")
                
                with patch('sys.executable', '/usr/bin/python3'):
                    # Should not raise
                    restore.create_pre_restore_backup("myapp", "myrg")
                    
                    mock_run.assert_called_once()
                    args = mock_run.call_args[0][0]
                    assert any('backup.py' in str(arg) for arg in args)
                    assert '--app-name' in args
                    assert 'myapp' in args
    
    def test_pre_restore_backup_script_missing(self):
        """Exits when backup.py not found."""
        with patch('os.path.exists', return_value=False):
            with pytest.raises(SystemExit) as exc_info:
                restore.create_pre_restore_backup("myapp", "myrg")
            
            assert exc_info.value.code == 1
    
    def test_pre_restore_backup_failed_continues(self, capsys):
        """Continues restore even if pre-restore backup fails."""
        with patch('os.path.exists', return_value=True):
            with patch('subprocess.run') as mock_run:
                mock_run.return_value = Mock(returncode=1, stdout="", stderr="Backup failed")
                
                # Should not raise - just prints warning
                restore.create_pre_restore_backup("myapp", "myrg")
                
                captured = capsys.readouterr()
                assert "Warning" in captured.out or "Warning" in captured.err


class TestAppServiceControl:
    """Tests for stopping and starting App Service."""
    
    def test_stop_app_service_success(self):
        """Successfully stops App Service."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="Stopped", stderr="")
            
            restore.stop_app_service("myapp", "myrg")
            
            args = mock_run.call_args[0][0]
            assert args == ['az', 'webapp', 'stop', '--name', 'myapp', '--resource-group', 'myrg']
    
    def test_stop_app_service_failure(self):
        """Exits when stop fails."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(returncode=1, stdout="", stderr="Not found")
            
            with pytest.raises(SystemExit) as exc_info:
                restore.stop_app_service("myapp", "myrg")
            
            assert exc_info.value.code == 2
    
    def test_start_app_service_success(self):
        """Successfully starts App Service."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="Started", stderr="")
            
            restore.start_app_service("myapp", "myrg")
            
            args = mock_run.call_args[0][0]
            assert args == ['az', 'webapp', 'start', '--name', 'myapp', '--resource-group', 'myrg']
    
    def test_start_app_service_failure(self):
        """Exits when start fails."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(returncode=1, stdout="", stderr="Failed to start")
            
            with pytest.raises(SystemExit) as exc_info:
                restore.start_app_service("myapp", "myrg")
            
            assert exc_info.value.code == 2


class TestUploadAndExtract:
    """Tests for uploading ZIP and extracting remotely."""
    
    def test_upload_and_extract_success(self, tmpdir):
        """Successfully uploads and extracts backup."""
        zip_path = tmpdir.join("backup.zip")
        
        with zipfile.ZipFile(str(zip_path), 'w') as zf:
            zf.writestr('users.yaml', 'users: []')
            zf.writestr('.secret_key', 'key')
        
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="Success", stderr="")
            
            restore.upload_and_extract(str(zip_path), "myapp", "myrg")
            
            # Verify upload steps were called
            assert mock_run.call_count > 0
            
            # Check that unzip command was issued
            calls = [str(c) for c in mock_run.call_args_list]
            assert any('unzip' in str(c) for c in calls)
    
    def test_upload_and_extract_unzip_fails(self, tmpdir):
        """Exits when unzip fails."""
        zip_path = tmpdir.join("backup.zip")
        
        with zipfile.ZipFile(str(zip_path), 'w') as zf:
            zf.writestr('users.yaml', 'users: []')
            zf.writestr('.secret_key', 'key')
        
        with patch('subprocess.run') as mock_run:
            def mock_run_side_effect(cmd, **kwargs):
                # Fail on unzip command
                if 'unzip' in str(cmd):
                    return Mock(returncode=1, stdout="", stderr="Invalid archive")
                return Mock(returncode=0, stdout="Success", stderr="")
            
            mock_run.side_effect = mock_run_side_effect
            
            with pytest.raises(SystemExit) as exc_info:
                restore.upload_and_extract(str(zip_path), "myapp", "myrg")
            
            assert exc_info.value.code == 3
    
    def test_upload_large_file_chunks(self, tmpdir):
        """Large files are uploaded in chunks."""
        zip_path = tmpdir.join("backup.zip")
        
        # Create a larger ZIP (over 100KB to trigger chunking)
        with zipfile.ZipFile(str(zip_path), 'w') as zf:
            zf.writestr('users.yaml', 'users: []')
            zf.writestr('.secret_key', 'key')
            zf.writestr('large_file.txt', 'X' * 100000)
        
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="Success", stderr="")
            
            restore.upload_and_extract(str(zip_path), "myapp", "myrg")
            
            # Should have multiple append operations for chunks
            assert mock_run.call_count > 3


class TestRemoteFileValidation:
    """Tests for validating restored files exist remotely."""
    
    def test_validate_remote_files_success(self):
        """All required files exist after restore."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="exists", stderr="")
            
            restore.validate_remote_files("myapp", "myrg")
            
            # Should check for users.yaml and .secret_key
            assert mock_run.call_count == 2
    
    def test_validate_remote_files_missing_file(self):
        """Exits when required file is missing."""
        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = [
                Mock(returncode=0, stdout="exists", stderr=""),   # users.yaml
                Mock(returncode=0, stdout="missing", stderr="")   # .secret_key
            ]
            
            with pytest.raises(SystemExit) as exc_info:
                restore.validate_remote_files("myapp", "myrg")
            
            assert exc_info.value.code == 4


class TestCleanup:
    """Tests for cleanup operations."""
    
    def test_cleanup_remote_temp_success(self):
        """Successfully removes temporary files."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="", stderr="")
            
            restore.cleanup_remote_temp("myapp", "myrg")
            
            args = mock_run.call_args[0][0]
            cmd_str = ' '.join(str(arg) for arg in args)
            assert 'rm' in cmd_str
            assert '/tmp/restore.zip' in cmd_str
    
    def test_cleanup_remote_temp_failure_ignored(self):
        """Cleanup failure does not raise."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(returncode=1, stdout="", stderr="File not found")
            
            # Should not raise
            restore.cleanup_remote_temp("myapp", "myrg")


class TestMainRestoreWorkflow:
    """Tests for main() orchestration and flags."""
    
    def test_main_restore_with_backup(self, tmpdir):
        """Complete restore workflow with pre-restore backup."""
        zip_path = tmpdir.join("backup.zip")
        
        with zipfile.ZipFile(str(zip_path), 'w') as zf:
            zf.writestr('users.yaml', 'users: []')
            zf.writestr('.secret_key', 'key')
        
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="exists", stderr="")
            
            with patch('os.path.exists', return_value=True):
                with patch('sys.argv', ['restore.py', str(zip_path), 
                                        '--app-name', 'myapp', 
                                        '--resource-group', 'myrg',
                                        '--force']):
                    restore.main()
    
    def test_main_restore_no_backup_flag(self, tmpdir):
        """Restore with --no-backup skips pre-restore backup."""
        zip_path = tmpdir.join("backup.zip")
        
        with zipfile.ZipFile(str(zip_path), 'w') as zf:
            zf.writestr('users.yaml', 'users: []')
            zf.writestr('.secret_key', 'key')
        
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="exists", stderr="")
            
            with patch('restore.create_pre_restore_backup') as mock_backup:
                with patch('sys.argv', ['restore.py', str(zip_path), 
                                        '--app-name', 'myapp', 
                                        '--resource-group', 'myrg',
                                        '--force',
                                        '--no-backup']):
                    restore.main()
                
                # Pre-restore backup should not be called
                mock_backup.assert_not_called()
    
    def test_main_restore_requires_confirmation(self, tmpdir):
        """Without --force, requires user confirmation."""
        zip_path = tmpdir.join("backup.zip")
        
        with zipfile.ZipFile(str(zip_path), 'w') as zf:
            zf.writestr('users.yaml', 'users: []')
            zf.writestr('.secret_key', 'key')
        
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="azure-cli", stderr="")
            
            with patch('builtins.input', return_value='NO'):
                with patch('sys.argv', ['restore.py', str(zip_path), 
                                        '--app-name', 'myapp', 
                                        '--resource-group', 'myrg']):
                    with pytest.raises(SystemExit) as exc_info:
                        restore.main()
                    
                    assert exc_info.value.code == 0
    
    def test_main_restore_force_flag_skips_confirmation(self, tmpdir):
        """--force flag skips confirmation prompt."""
        zip_path = tmpdir.join("backup.zip")
        
        with zipfile.ZipFile(str(zip_path), 'w') as zf:
            zf.writestr('users.yaml', 'users: []')
            zf.writestr('.secret_key', 'key')
        
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="exists", stderr="")
            
            with patch('builtins.input') as mock_input:
                with patch('os.path.exists', return_value=True):
                    with patch('sys.argv', ['restore.py', str(zip_path), 
                                            '--app-name', 'myapp', 
                                            '--resource-group', 'myrg',
                                            '--force',
                                            '--no-backup']):
                        restore.main()
                
                # input() should not be called with --force
                mock_input.assert_not_called()
    
    def test_main_keyboard_interrupt_handling(self, tmpdir):
        """Handles KeyboardInterrupt gracefully."""
        zip_path = tmpdir.join("backup.zip")
        
        with zipfile.ZipFile(str(zip_path), 'w') as zf:
            zf.writestr('users.yaml', 'users: []')
            zf.writestr('.secret_key', 'key')
        
        with patch('subprocess.run') as mock_run:
            # Simulate interrupt during stop_app_service
            def interrupt_on_stop(cmd, **kwargs):
                if 'stop' in str(cmd):
                    raise KeyboardInterrupt()
                return Mock(returncode=0, stdout="Success", stderr="")
            
            mock_run.side_effect = interrupt_on_stop
            
            with patch('sys.argv', ['restore.py', str(zip_path), 
                                    '--app-name', 'myapp', 
                                    '--resource-group', 'myrg',
                                    '--force',
                                    '--no-backup']):
                with pytest.raises(SystemExit) as exc_info:
                    restore.main()
                
                assert exc_info.value.code == 1
    
    def test_main_unexpected_exception_handling(self, tmpdir):
        """Handles unexpected exceptions gracefully."""
        zip_path = tmpdir.join("backup.zip")
        
        with zipfile.ZipFile(str(zip_path), 'w') as zf:
            zf.writestr('users.yaml', 'users: []')
            zf.writestr('.secret_key', 'key')
        
        with patch('restore.stop_app_service', side_effect=Exception("Unexpected network error")):
            with patch('restore.check_azure_cli'):
                with patch('sys.argv', ['restore.py', str(zip_path), 
                                        '--app-name', 'myapp', 
                                        '--resource-group', 'myrg',
                                        '--force',
                                        '--no-backup']):
                    with pytest.raises(SystemExit) as exc_info:
                        restore.main()
                
                    assert exc_info.value.code == 3
    
    def test_main_stop_extract_validate_start_sequence(self, tmpdir):
        """Verifies correct sequence: stop → extract → validate → start."""
        zip_path = tmpdir.join("backup.zip")
        
        with zipfile.ZipFile(str(zip_path), 'w') as zf:
            zf.writestr('users.yaml', 'users: []')
            zf.writestr('.secret_key', 'key')
        
        call_sequence = []
        
        with patch('restore.stop_app_service', side_effect=lambda *a: call_sequence.append('stop')):
            with patch('restore.upload_and_extract', side_effect=lambda *a: call_sequence.append('extract')):
                with patch('restore.validate_remote_files', side_effect=lambda *a: call_sequence.append('validate')):
                    with patch('restore.cleanup_remote_temp', side_effect=lambda *a: call_sequence.append('cleanup')):
                        with patch('restore.start_app_service', side_effect=lambda *a: call_sequence.append('start')):
                            with patch('restore.check_azure_cli'):
                                with patch('sys.argv', ['restore.py', str(zip_path), 
                                                        '--app-name', 'myapp', 
                                                        '--resource-group', 'myrg',
                                                        '--force',
                                                        '--no-backup']):
                                    restore.main()
        
        assert call_sequence == ['stop', 'extract', 'validate', 'cleanup', 'start']
