"""
Tests for scripts/backup.py — Azure App Service backup tool.

Mocks all Azure CLI calls to test backup creation workflow.
"""
import pytest
import sys
import os
from unittest.mock import Mock, patch, MagicMock, call
from pathlib import Path
import tempfile
import zipfile
import subprocess

# Add scripts directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'scripts'))

import backup


class TestAzureCLIAvailability:
    """Tests for Azure CLI installation and authentication checks."""
    
    def test_azure_cli_installed_and_authenticated(self):
        """Azure CLI is installed and user is authenticated."""
        with patch('subprocess.run') as mock_run:
            # Mock successful az --version
            mock_run.side_effect = [
                Mock(returncode=0, stdout="azure-cli 2.50.0", stderr=""),
                Mock(returncode=0, stdout='{"user": {...}}', stderr="")
            ]
            
            result = backup.check_azure_cli()
            
            assert result is True
            assert mock_run.call_count == 2
            mock_run.assert_any_call(['az', '--version'], capture_output=True, text=True, check=False)
            mock_run.assert_any_call(['az', 'account', 'show'], capture_output=True, text=True, check=False)
    
    def test_azure_cli_not_installed(self):
        """Azure CLI not installed returns False."""
        with patch('subprocess.run', side_effect=FileNotFoundError):
            result = backup.check_azure_cli()
            assert result is False
    
    def test_azure_cli_version_check_fails(self):
        """az --version returns non-zero code."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(returncode=1, stdout="", stderr="command not found")
            result = backup.check_azure_cli()
            assert result is False
    
    def test_azure_cli_not_authenticated(self):
        """Azure CLI installed but user not authenticated."""
        with patch('subprocess.run') as mock_run:
            # First call (--version) succeeds, second (account show) fails
            mock_run.side_effect = [
                Mock(returncode=0, stdout="azure-cli 2.50.0", stderr=""),
                Mock(returncode=1, stdout="", stderr="Please run 'az login'")
            ]
            
            result = backup.check_azure_cli()
            assert result is False
    
    def test_azure_cli_authentication_check_exception(self):
        """Exception during authentication check returns False."""
        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = [
                Mock(returncode=0, stdout="azure-cli 2.50.0", stderr=""),
                Exception("Network error")
            ]
            
            result = backup.check_azure_cli()
            assert result is False


class TestAppServiceVerification:
    """Tests for App Service existence and accessibility checks."""
    
    def test_app_service_exists_and_accessible(self):
        """App Service exists and is accessible."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=0,
                stdout='{"name": "myapp", "state": "Running"}',
                stderr=""
            )
            
            result = backup.verify_app_service("myapp", "myrg")
            
            assert result is True
            mock_run.assert_called_once_with(
                ['az', 'webapp', 'show', '--name', 'myapp', '--resource-group', 'myrg'],
                capture_output=True,
                text=True,
                check=False
            )
    
    def test_app_service_not_found(self):
        """App Service does not exist."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(
                returncode=1,
                stdout="",
                stderr="ResourceNotFound: The Resource 'myapp' was not found"
            )
            
            result = backup.verify_app_service("myapp", "myrg")
            assert result is False
    
    def test_app_service_verification_exception(self):
        """Exception during verification returns False."""
        with patch('subprocess.run', side_effect=Exception("Connection timeout")):
            result = backup.verify_app_service("myapp", "myrg")
            assert result is False


class TestDataDirectoryDownload:
    """Tests for downloading /home/data from App Service."""
    
    def test_download_successful(self, tmpdir):
        """Successfully downloads and extracts /home/data."""
        temp_dir = str(tmpdir)
        
        # Create mock tar archive content
        import tarfile
        import io
        tar_buffer = io.BytesIO()
        with tarfile.open(fileobj=tar_buffer, mode='w:gz') as tar:
            # Add mock data directory contents
            content = b'teams: []'
            info = tarfile.TarInfo(name='data/teams.yaml')
            info.size = len(content)
            tar.addfile(info, io.BytesIO(content))
        tar_bytes = tar_buffer.getvalue()
        
        with patch('subprocess.run') as mock_run:
            # Mock tar creation on remote
            mock_run.side_effect = [
                Mock(returncode=0, stdout="SUCCESS\n", stderr=""),  # tar creation
                Mock(returncode=0, stdout=tar_bytes, stderr=""),    # cat download
                Mock(returncode=0, stdout="", stderr="")            # tar extraction
            ]
            
            result = backup.download_data_directory("myapp", "myrg", temp_dir)
            
            assert result is True
            assert mock_run.call_count == 3
            
            # Verify data directory was created
            assert os.path.exists(os.path.join(temp_dir, 'data'))
    
    def test_download_remote_tar_creation_fails(self, tmpdir):
        """Remote tar creation fails."""
        with patch('subprocess.run') as mock_run:
            mock_run.return_value = Mock(returncode=0, stdout="FAILURE\n", stderr="tar error")
            
            result = backup.download_data_directory("myapp", "myrg", str(tmpdir))
            assert result is False
    
    def test_download_remote_tar_timeout(self, tmpdir):
        """Remote tar creation times out."""
        with patch('subprocess.run', side_effect=subprocess.TimeoutExpired(cmd=[], timeout=120)):
            result = backup.download_data_directory("myapp", "myrg", str(tmpdir))
            assert result is False
    
    def test_download_transfer_fails(self, tmpdir):
        """Downloading tar file fails."""
        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = [
                Mock(returncode=0, stdout="SUCCESS\n", stderr=""),  # tar creation
                Mock(returncode=1, stdout="", stderr="Connection lost")  # cat fails
            ]
            
            result = backup.download_data_directory("myapp", "myrg", str(tmpdir))
            assert result is False
    
    def test_download_extraction_fails(self, tmpdir):
        """Tar extraction fails."""
        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = [
                Mock(returncode=0, stdout="SUCCESS\n", stderr=""),
                Mock(returncode=0, stdout=b"fake tar data", stderr=""),
                Mock(returncode=1, stdout="", stderr="Invalid tar archive")
            ]
            
            result = backup.download_data_directory("myapp", "myrg", str(tmpdir))
            assert result is False
    
    def test_download_tar_command_not_found(self, tmpdir):
        """tar command not available on system."""
        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = [
                Mock(returncode=0, stdout="SUCCESS\n", stderr=""),
                Mock(returncode=0, stdout=b"fake tar data", stderr=""),
                FileNotFoundError("tar not found")
            ]
            
            result = backup.download_data_directory("myapp", "myrg", str(tmpdir))
            assert result is False
    
    def test_download_missing_data_directory(self, tmpdir):
        """Extracted archive does not contain data directory."""
        temp_dir = str(tmpdir)
        
        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = [
                Mock(returncode=0, stdout="SUCCESS\n", stderr=""),
                Mock(returncode=0, stdout=b"fake tar", stderr=""),
                Mock(returncode=0, stdout="", stderr="")  # Extraction succeeds but no data dir
            ]
            
            result = backup.download_data_directory("myapp", "myrg", temp_dir)
            # Should fail because data directory doesn't exist
            assert result is False


class TestBackupZIPCreation:
    """Tests for creating backup ZIP file."""
    
    def test_create_backup_zip_success(self, tmpdir):
        """Successfully creates backup ZIP."""
        temp_dir = tmpdir.mkdir("backup")
        data_dir = temp_dir.mkdir("data")
        data_dir.join("teams.yaml").write("teams: []")
        data_dir.join("courts.csv").write("Court 1,08:00")
        
        output_path = str(tmpdir.join("backup.zip"))
        
        result = backup.create_backup_zip(str(temp_dir), output_path)
        
        assert result is True
        assert os.path.exists(output_path)
        
        # Verify ZIP contents
        with zipfile.ZipFile(output_path, 'r') as zf:
            names = zf.namelist()
            assert 'data/teams.yaml' in names
            assert 'data/courts.csv' in names
    
    def test_create_backup_zip_data_directory_missing(self, tmpdir):
        """Fails when data directory does not exist."""
        temp_dir = str(tmpdir.mkdir("backup"))
        output_path = str(tmpdir.join("backup.zip"))
        
        result = backup.create_backup_zip(temp_dir, output_path)
        assert result is False
    
    def test_create_backup_zip_creates_parent_directories(self, tmpdir):
        """Creates parent directories if they don't exist."""
        temp_dir = tmpdir.mkdir("backup")
        data_dir = temp_dir.mkdir("data")
        data_dir.join("teams.yaml").write("teams: []")
        
        output_path = str(tmpdir.join("nested", "path", "backup.zip"))
        
        result = backup.create_backup_zip(str(temp_dir), output_path)
        
        assert result is True
        assert os.path.exists(output_path)
    
    def test_create_backup_zip_adds_extension(self, tmpdir):
        """Adds .zip extension if not present."""
        temp_dir = tmpdir.mkdir("backup")
        data_dir = temp_dir.mkdir("data")
        data_dir.join("teams.yaml").write("teams: []")
        
        output_path_no_ext = str(tmpdir.join("backup"))
        
        result = backup.create_backup_zip(str(temp_dir), output_path_no_ext)
        
        assert result is True
        expected_path = f"{output_path_no_ext}.zip"
        assert os.path.exists(expected_path)
    
    def test_create_backup_zip_write_failure(self, tmpdir):
        """Handles write failures gracefully."""
        temp_dir = tmpdir.mkdir("backup")
        data_dir = temp_dir.mkdir("data")
        data_dir.join("teams.yaml").write("teams: []")
        
        with patch('shutil.make_archive', side_effect=Exception("Disk full")):
            result = backup.create_backup_zip(str(temp_dir), "/readonly/backup.zip")
            assert result is False


class TestMainBackupWorkflow:
    """Tests for main() orchestration and exit codes."""
    
    def test_main_successful_backup(self, tmpdir):
        """Complete successful backup workflow."""
        output_path = str(tmpdir.join("backup.zip"))
        
        # Mock tar content
        import tarfile
        import io
        tar_buffer = io.BytesIO()
        with tarfile.open(fileobj=tar_buffer, mode='w:gz') as tar:
            info = tarfile.TarInfo(name='data/teams.yaml')
            info.size = 10
            tar.addfile(info, io.BytesIO(b'teams: []'))
        tar_bytes = tar_buffer.getvalue()
        
        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = [
                # check_azure_cli: az --version
                Mock(returncode=0, stdout="azure-cli 2.50.0", stderr=""),
                # check_azure_cli: az account show
                Mock(returncode=0, stdout='{"user": {...}}', stderr=""),
                # verify_app_service
                Mock(returncode=0, stdout='{"name": "myapp"}', stderr=""),
                # download: tar creation
                Mock(returncode=0, stdout="SUCCESS\n", stderr=""),
                # download: cat
                Mock(returncode=0, stdout=tar_bytes, stderr=""),
                # download: extraction
                Mock(returncode=0, stdout="", stderr="")
            ]
            
            with patch('sys.argv', ['backup.py', '--app-name', 'myapp', 
                                    '--resource-group', 'myrg', '--output', output_path]):
                exit_code = backup.main()
        
        assert exit_code == 0
        assert os.path.exists(output_path)
    
    def test_main_azure_cli_not_available(self):
        """Exit code 1 when Azure CLI not available."""
        with patch('subprocess.run', side_effect=FileNotFoundError):
            with patch('sys.argv', ['backup.py', '--app-name', 'myapp', '--resource-group', 'myrg']):
                exit_code = backup.main()
        
        assert exit_code == 1
    
    def test_main_app_service_connection_failed(self):
        """Exit code 2 when App Service connection fails."""
        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = [
                Mock(returncode=0, stdout="azure-cli 2.50.0", stderr=""),
                Mock(returncode=0, stdout='{"user": {...}}', stderr=""),
                Mock(returncode=1, stdout="", stderr="ResourceNotFound")
            ]
            
            with patch('sys.argv', ['backup.py', '--app-name', 'myapp', '--resource-group', 'myrg']):
                exit_code = backup.main()
        
        assert exit_code == 2
    
    def test_main_download_failed(self):
        """Exit code 2 when download fails."""
        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = [
                Mock(returncode=0, stdout="azure-cli 2.50.0", stderr=""),
                Mock(returncode=0, stdout='{"user": {...}}', stderr=""),
                Mock(returncode=0, stdout='{"name": "myapp"}', stderr=""),
                Mock(returncode=0, stdout="FAILURE\n", stderr="tar error")
            ]
            
            with patch('sys.argv', ['backup.py', '--app-name', 'myapp', '--resource-group', 'myrg']):
                exit_code = backup.main()
        
        assert exit_code == 2
    
    def test_main_zip_creation_failed(self, tmpdir):
        """Exit code 3 when ZIP creation fails."""
        import tarfile
        import io
        tar_buffer = io.BytesIO()
        with tarfile.open(fileobj=tar_buffer, mode='w:gz') as tar:
            content = b'teams: []'
            info = tarfile.TarInfo(name='data/teams.yaml')
            info.size = len(content)
            tar.addfile(info, io.BytesIO(content))
        tar_bytes = tar_buffer.getvalue()
        
        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = [
                Mock(returncode=0, stdout="azure-cli 2.50.0", stderr=""),
                Mock(returncode=0, stdout='{"user": {...}}', stderr=""),
                Mock(returncode=0, stdout='{"name": "myapp"}', stderr=""),
                Mock(returncode=0, stdout="SUCCESS\n", stderr=""),
                Mock(returncode=0, stdout=tar_bytes, stderr=""),
                Mock(returncode=0, stdout="", stderr="")
            ]
            
            with patch('shutil.make_archive', side_effect=Exception("Write failed")):
                with patch('sys.argv', ['backup.py', '--app-name', 'myapp', '--resource-group', 'myrg']):
                    exit_code = backup.main()
        
        assert exit_code == 3
    
    def test_main_default_output_path_with_timestamp(self, tmpdir):
        """Uses timestamped filename when --output not specified."""
        import tarfile
        import io
        tar_buffer = io.BytesIO()
        with tarfile.open(fileobj=tar_buffer, mode='w:gz') as tar:
            content = b'teams: []'
            info = tarfile.TarInfo(name='data/teams.yaml')
            info.size = len(content)
            tar.addfile(info, io.BytesIO(content))
        tar_bytes = tar_buffer.getvalue()
        
        with patch('subprocess.run') as mock_run:
            mock_run.side_effect = [
                Mock(returncode=0, stdout="azure-cli 2.50.0", stderr=""),
                Mock(returncode=0, stdout='{"user": {...}}', stderr=""),
                Mock(returncode=0, stdout='{"name": "myapp"}', stderr=""),
                Mock(returncode=0, stdout="SUCCESS\n", stderr=""),
                Mock(returncode=0, stdout=tar_bytes, stderr=""),
                Mock(returncode=0, stdout="", stderr="")
            ]
            
            # Mock Path to control backup directory location
            with patch('backup.Path') as mock_path:
                backups_dir = tmpdir.mkdir("backups")
                mock_path.return_value.parent.parent = tmpdir
                
                with patch('sys.argv', ['backup.py', '--app-name', 'myapp', '--resource-group', 'myrg']):
                    # Patch datetime to get consistent timestamp
                    with patch('backup.datetime') as mock_dt:
                        mock_dt.now.return_value.strftime.return_value = "20260214-153045"
                        
                        # Capture actual output path used
                        original_create_backup = backup.create_backup_zip
                        captured_path = []
                        
                        def capture_path(temp_dir, output_path):
                            captured_path.append(output_path)
                            return True
                        
                        with patch('backup.create_backup_zip', side_effect=capture_path):
                            exit_code = backup.main()
                        
                        assert exit_code == 0
                        assert len(captured_path) == 1
                        assert 'azure-backup-20260214-153045.zip' in captured_path[0]
