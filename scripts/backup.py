#!/usr/bin/env python3
"""
Azure App Service Backup Tool

Downloads the /home/data directory from an Azure App Service instance
and creates a timestamped ZIP backup locally.

Usage:
    python scripts/backup.py --app-name <webapp> --resource-group <rg>
    python scripts/backup.py --app-name <webapp> --resource-group <rg> --output /path/to/backup.zip

Exit codes:
    0: Success
    1: Azure CLI not available or not authenticated
    2: App Service connection failed
    3: Backup write failure
"""
import argparse
import subprocess
import sys
import os
import tempfile
import shutil
from datetime import datetime
from pathlib import Path


def check_azure_cli():
    """Verify Azure CLI is installed and user is authenticated."""
    try:
        result = subprocess.run(
            ['az', '--version'],
            capture_output=True,
            text=True,
            check=False
        )
        if result.returncode != 0:
            print("Error: Azure CLI not found. Install from https://aka.ms/InstallAzureCLI", file=sys.stderr)
            return False
    except FileNotFoundError:
        print("Error: Azure CLI not found. Install from https://aka.ms/InstallAzureCLI", file=sys.stderr)
        return False

    try:
        result = subprocess.run(
            ['az', 'account', 'show'],
            capture_output=True,
            text=True,
            check=False
        )
        if result.returncode != 0:
            print("Error: Not authenticated with Azure CLI. Run 'az login' first.", file=sys.stderr)
            return False
    except Exception as e:
        print(f"Error: Failed to check Azure CLI authentication: {e}", file=sys.stderr)
        return False

    return True


def verify_app_service(app_name: str, resource_group: str) -> bool:
    """Check if the App Service exists and is accessible."""
    try:
        result = subprocess.run(
            ['az', 'webapp', 'show', '--name', app_name, '--resource-group', resource_group],
            capture_output=True,
            text=True,
            check=False
        )
        if result.returncode != 0:
            print(f"Error: Cannot access App Service '{app_name}' in resource group '{resource_group}'", file=sys.stderr)
            print(f"Details: {result.stderr.strip()}", file=sys.stderr)
            return False
        return True
    except Exception as e:
        print(f"Error: Failed to verify App Service: {e}", file=sys.stderr)
        return False


def download_data_directory(app_name: str, resource_group: str, temp_dir: str) -> bool:
    """
    Download /home/data directory from Azure App Service using az webapp ssh.
    
    Strategy:
    1. SSH into the container and create a tar archive of /home/data
    2. Download the tar file via SSH
    3. Extract to temp directory
    """
    remote_tar = "/tmp/data-backup.tar.gz"
    local_tar = os.path.join(temp_dir, "data-backup.tar.gz")
    
    print(f"Creating remote archive of /home/data...")
    
    # Create tar on remote server
    tar_command = f"tar -czf {remote_tar} -C /home data 2>/dev/null && echo SUCCESS"
    try:
        result = subprocess.run(
            ['az', 'webapp', 'ssh', '--name', app_name, '--resource-group', resource_group],
            input=tar_command + '\nexit\n',
            capture_output=True,
            text=True,
            check=False,
            timeout=120
        )
        
        if 'SUCCESS' not in result.stdout:
            print(f"Error: Failed to create remote tar archive", file=sys.stderr)
            print(f"Output: {result.stdout}", file=sys.stderr)
            print(f"Errors: {result.stderr}", file=sys.stderr)
            return False
            
    except subprocess.TimeoutExpired:
        print("Error: Timeout while creating remote archive", file=sys.stderr)
        return False
    except Exception as e:
        print(f"Error: Failed to create remote archive: {e}", file=sys.stderr)
        return False

    print(f"Downloading archive from App Service...")
    
    # Download tar file using scp-like approach via az webapp ssh
    # We'll use a different approach: run cat on the remote tar and redirect to local file
    download_command = f"cat {remote_tar}"
    try:
        result = subprocess.run(
            ['az', 'webapp', 'ssh', '--name', app_name, '--resource-group', resource_group],
            input=download_command + '\nexit\n',
            capture_output=True,
            check=False,
            timeout=120
        )
        
        if result.returncode != 0:
            print(f"Error: Failed to download archive", file=sys.stderr)
            print(f"Errors: {result.stderr}", file=sys.stderr)
            return False
            
        # Write binary output to local tar file
        with open(local_tar, 'wb') as f:
            f.write(result.stdout)
            
    except subprocess.TimeoutExpired:
        print("Error: Timeout while downloading archive", file=sys.stderr)
        return False
    except Exception as e:
        print(f"Error: Failed to download archive: {e}", file=sys.stderr)
        return False

    print(f"Extracting archive...")
    
    # Extract tar file
    try:
        result = subprocess.run(
            ['tar', '-xzf', local_tar, '-C', temp_dir],
            capture_output=True,
            text=True,
            check=False
        )
        
        if result.returncode != 0:
            print(f"Error: Failed to extract archive", file=sys.stderr)
            print(f"Details: {result.stderr}", file=sys.stderr)
            return False
            
    except FileNotFoundError:
        print("Error: tar command not found. Install tar or use WSL on Windows.", file=sys.stderr)
        return False
    except Exception as e:
        print(f"Error: Failed to extract archive: {e}", file=sys.stderr)
        return False

    # Verify data directory exists
    data_dir = os.path.join(temp_dir, 'data')
    if not os.path.exists(data_dir):
        print(f"Error: Extracted archive does not contain 'data' directory", file=sys.stderr)
        return False

    print(f"Download complete: {data_dir}")
    return True


def create_backup_zip(temp_dir: str, output_path: str) -> bool:
    """Create a ZIP file from the downloaded data directory."""
    data_dir = os.path.join(temp_dir, 'data')
    
    if not os.path.exists(data_dir):
        print(f"Error: Data directory not found: {data_dir}", file=sys.stderr)
        return False

    print(f"Creating backup ZIP: {output_path}")
    
    try:
        # Create parent directory if needed
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        
        # Create ZIP file
        shutil.make_archive(
            output_path.replace('.zip', ''),
            'zip',
            root_dir=temp_dir,
            base_dir='data'
        )
        
        # shutil.make_archive doesn't add .zip if already present
        expected_path = output_path if output_path.endswith('.zip') else f"{output_path}.zip"
        generated_path = output_path.replace('.zip', '') + '.zip'
        
        if generated_path != expected_path and os.path.exists(generated_path):
            shutil.move(generated_path, expected_path)
        
        if not os.path.exists(expected_path):
            print(f"Error: Backup ZIP was not created at expected path: {expected_path}", file=sys.stderr)
            return False
            
        file_size = os.path.getsize(expected_path)
        print(f"Backup created successfully: {expected_path} ({file_size / 1024 / 1024:.2f} MB)")
        return True
        
    except Exception as e:
        print(f"Error: Failed to create backup ZIP: {e}", file=sys.stderr)
        return False


def main():
    parser = argparse.ArgumentParser(
        description='Backup Azure App Service /home/data directory to local ZIP file'
    )
    parser.add_argument(
        '--app-name',
        required=True,
        help='Azure App Service name'
    )
    parser.add_argument(
        '--resource-group',
        required=True,
        help='Azure resource group name'
    )
    parser.add_argument(
        '--output',
        help='Output ZIP file path (default: backups/azure-backup-YYYYMMDD-HHMMSS.zip)'
    )
    
    args = parser.parse_args()
    
    # Check prerequisites
    print("Checking Azure CLI...")
    if not check_azure_cli():
        return 1
    
    print(f"Verifying App Service: {args.app_name}")
    if not verify_app_service(args.app_name, args.resource_group):
        return 2
    
    # Determine output path
    if args.output:
        output_path = args.output
    else:
        timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        script_dir = Path(__file__).parent.parent
        backups_dir = script_dir / 'backups'
        backups_dir.mkdir(exist_ok=True)
        output_path = str(backups_dir / f'azure-backup-{timestamp}.zip')
    
    # Ensure .zip extension
    if not output_path.endswith('.zip'):
        output_path += '.zip'
    
    # Create temporary directory
    with tempfile.TemporaryDirectory(prefix='azure-backup-') as temp_dir:
        print(f"Using temporary directory: {temp_dir}")
        
        # Download data directory
        if not download_data_directory(args.app_name, args.resource_group, temp_dir):
            print("Backup failed during download.", file=sys.stderr)
            return 2
        
        # Create ZIP file
        if not create_backup_zip(temp_dir, output_path):
            print("Backup failed during ZIP creation.", file=sys.stderr)
            return 3
    
    print("\nBackup completed successfully!")
    print(f"Location: {output_path}")
    return 0


if __name__ == '__main__':
    sys.exit(main())
