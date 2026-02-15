#!/usr/bin/env python3
"""
Restore Tournament Allocator data from backup ZIP to Azure App Service.

Usage:
    python scripts/restore.py backup.zip --app-name <webapp> --resource-group <rg>
    python scripts/restore.py backup.zip --app-name <webapp> --resource-group <rg> --force
    python scripts/restore.py backup.zip --app-name <webapp> --resource-group <rg> --no-backup

Requirements:
    - Azure CLI installed and authenticated (run 'az login' first)
    - Backup ZIP created by backup.py

Safety:
    - Creates pre-restore backup automatically (unless --no-backup)
    - Stops App Service during restore to prevent data corruption
    - Validates ZIP structure before uploading
    - Validates restored files remotely after extraction
"""

import argparse
import os
import sys
import zipfile
import subprocess
import json
from datetime import datetime


def run_az_command(args, **kwargs):
    """
    Run an Azure CLI command with proper shell handling for Windows.
    
    On Windows, subprocess needs shell=True to find az.cmd in PATH.
    """
    use_shell = sys.platform.startswith('win')
    
    if use_shell:
        # On Windows, convert list to string command
        if isinstance(args, list):
            # Properly quote arguments that contain spaces
            cmd = ' '.join(f'"{arg}"' if ' ' in str(arg) else str(arg) for arg in args)
        else:
            cmd = args
        return subprocess.run(cmd, shell=True, **kwargs)
    else:
        # On Unix, use list form
        return subprocess.run(args, **kwargs)


def error(message: str, code: int = 1):
    """Print error and exit."""
    print(f"❌ ERROR: {message}", file=sys.stderr)
    sys.exit(code)


def run_az(command: list, capture_output: bool = True, check: bool = True) -> subprocess.CompletedProcess:
    """Run Azure CLI command."""
    cmd = ['az'] + command
    result = run_az_command(cmd, capture_output=capture_output, text=True, check=False)
    if check and result.returncode != 0:
        error(f"Azure CLI command failed: {' '.join(cmd)}\n{result.stderr}", code=2)
    return result


def check_azure_cli():
    """Verify Azure CLI is installed and authenticated."""
    # Check installation
    result = run_az_command(['az', '--version'], capture_output=True, check=False)
    if result.returncode != 0:
        error("Azure CLI not found. Install from: https://aka.ms/azure-cli")
    
    # Check authentication
    result = run_az(['account', 'show'], check=False)
    if result.returncode != 0:
        error("Not authenticated with Azure. Run 'az login' first.")


def validate_zip_structure(zip_path: str):
    """Validate ZIP contains required files."""
    if not os.path.exists(zip_path):
        error(f"Backup file not found: {zip_path}")
    
    print(f"📦 Validating backup structure: {zip_path}")
    
    required_files = ['users.yaml', '.secret_key']
    
    try:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            names = zf.namelist()
            
            # Check required files
            missing = [f for f in required_files if f not in names]
            if missing:
                error(f"Invalid backup ZIP. Missing required files: {', '.join(missing)}")
            
            # Check for directory traversal attempts
            for name in names:
                if name.startswith('/') or '..' in name:
                    error(f"Invalid file path in ZIP: {name}")
            
            print(f"   ✓ Found {len(names)} files")
            print(f"   ✓ Required files present: {', '.join(required_files)}")
            
    except zipfile.BadZipFile:
        error("Invalid ZIP file format")


def create_pre_restore_backup(app_name: str, resource_group: str):
    """Create backup before restore."""
    print("\n💾 Creating pre-restore backup...")
    
    # Import here to avoid issues if backup.py doesn't exist yet
    backup_script = os.path.join(os.path.dirname(__file__), 'backup.py')
    if not os.path.exists(backup_script):
        error("backup.py not found. Cannot create pre-restore backup.", code=1)
    
    # Run backup.py
    result = subprocess.run([
        sys.executable, backup_script,
        '--app-name', app_name,
        '--resource-group', resource_group,
        '--prefix', 'pre-restore'
    ], capture_output=True, text=True, check=False)
    
    if result.returncode != 0:
        print(f"⚠️  Warning: Pre-restore backup failed:\n{result.stderr}", file=sys.stderr)
        print("   Continuing with restore...")
    else:
        print("   ✓ Pre-restore backup created")


def stop_app_service(app_name: str, resource_group: str):
    """Stop App Service."""
    print("\n⏸️  Stopping App Service...")
    run_az(['webapp', 'stop', '--name', app_name, '--resource-group', resource_group])
    print("   ✓ App Service stopped")


def start_app_service(app_name: str, resource_group: str):
    """Start App Service."""
    print("\n▶️  Starting App Service...")
    run_az(['webapp', 'start', '--name', app_name, '--resource-group', resource_group])
    print("   ✓ App Service started")


def upload_and_extract(zip_path: str, app_name: str, resource_group: str):
    """Upload ZIP and extract remotely."""
    print("\n📤 Uploading backup to App Service...")
    
    # Upload ZIP to temp location
    remote_zip = '/tmp/restore.zip'
    
    # Use az webapp ssh to upload
    with open(zip_path, 'rb') as f:
        zip_data = f.read()
    
    # Write file remotely using base64 encoding to avoid binary issues
    import base64
    encoded = base64.b64encode(zip_data).decode('ascii')
    
    # Split into chunks (Azure CLI has command length limits)
    chunk_size = 50000
    chunks = [encoded[i:i+chunk_size] for i in range(0, len(encoded), chunk_size)]
    
    print(f"   Uploading {len(zip_data)} bytes in {len(chunks)} chunk(s)...")
    
    # Create empty file first
    ssh_cmd = ['webapp', 'ssh', '--name', app_name, '--resource-group', resource_group,
               '--command', f'echo "" > {remote_zip}.b64']
    run_az(ssh_cmd)
    
    # Append chunks
    for i, chunk in enumerate(chunks):
        if i % 10 == 0:
            print(f"   Uploading chunk {i+1}/{len(chunks)}...")
        ssh_cmd = ['webapp', 'ssh', '--name', app_name, '--resource-group', resource_group,
                   '--command', f'echo "{chunk}" >> {remote_zip}.b64']
        run_az(ssh_cmd)
    
    # Decode base64 to binary
    print("   Decoding uploaded data...")
    ssh_cmd = ['webapp', 'ssh', '--name', app_name, '--resource-group', resource_group,
               '--command', f'base64 -d {remote_zip}.b64 > {remote_zip}']
    run_az(ssh_cmd)
    
    # Clean up base64 file
    ssh_cmd = ['webapp', 'ssh', '--name', app_name, '--resource-group', resource_group,
               '--command', f'rm {remote_zip}.b64']
    run_az(ssh_cmd)
    
    print("   ✓ Upload complete")
    
    # Extract to /home/data
    print("\n📂 Extracting backup to /home/data...")
    
    ssh_cmd = ['webapp', 'ssh', '--name', app_name, '--resource-group', resource_group,
               '--command', f'unzip -o {remote_zip} -d /home/data']
    result = run_az(ssh_cmd, check=False)
    
    if result.returncode != 0:
        error(f"Failed to extract ZIP:\n{result.stderr}", code=3)
    
    print("   ✓ Extraction complete")


def validate_remote_files(app_name: str, resource_group: str):
    """Validate restored files exist remotely."""
    print("\n🔍 Validating restored files...")
    
    required_files = ['users.yaml', '.secret_key']
    
    for file in required_files:
        ssh_cmd = ['webapp', 'ssh', '--name', app_name, '--resource-group', resource_group,
                   '--command', f'test -f /home/data/{file} && echo "exists" || echo "missing"']
        result = run_az(ssh_cmd)
        
        if 'missing' in result.stdout:
            error(f"Validation failed: {file} not found after restore", code=4)
        
        print(f"   ✓ {file}")
    
    print("   ✓ All required files present")


def cleanup_remote_temp(app_name: str, resource_group: str):
    """Remove temporary files from remote."""
    print("\n🧹 Cleaning up remote temp files...")
    
    ssh_cmd = ['webapp', 'ssh', '--name', app_name, '--resource-group', resource_group,
               '--command', 'rm -f /tmp/restore.zip']
    run_az(ssh_cmd, check=False)  # Don't fail if cleanup fails
    
    print("   ✓ Cleanup complete")


def main():
    parser = argparse.ArgumentParser(
        description='Restore Tournament Allocator data to Azure App Service',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/restore.py backup.zip --app-name myapp --resource-group myrg
  python scripts/restore.py backup.zip --app-name myapp --resource-group myrg --no-backup
  python scripts/restore.py backup.zip --app-name myapp --resource-group myrg --force

Exit codes:
  0: Success
  1: Invalid ZIP or Azure CLI not available
  2: App Service connection failed
  3: Restore operation failed
  4: Validation failed after restore
        """
    )
    
    parser.add_argument('backup_zip', help='Path to backup ZIP file')
    parser.add_argument('--app-name', required=True, help='Azure App Service name')
    parser.add_argument('--resource-group', required=True, help='Azure resource group name')
    parser.add_argument('--no-backup', action='store_true',
                        help='Skip pre-restore backup (not recommended)')
    parser.add_argument('--force', action='store_true',
                        help='Skip confirmation prompt')
    
    args = parser.parse_args()
    
    print("=== Azure App Service Restore ===\n")
    print(f"Backup file: {args.backup_zip}")
    print(f"App name: {args.app_name}")
    print(f"Resource group: {args.resource_group}")
    print(f"Pre-restore backup: {'disabled' if args.no_backup else 'enabled'}")
    print()
    
    # Pre-flight checks
    check_azure_cli()
    validate_zip_structure(args.backup_zip)
    
    # Confirmation
    if not args.force:
        print("\n⚠️  WARNING: This will replace all data on the App Service.")
        print(f"   Target: {args.app_name}.azurewebsites.net")
        response = input("\nType 'RESTORE' to continue: ")
        if response != 'RESTORE':
            print("Restore cancelled.")
            sys.exit(0)
    
    try:
        # Create pre-restore backup (unless disabled)
        if not args.no_backup:
            create_pre_restore_backup(args.app_name, args.resource_group)
        
        # Stop app service
        stop_app_service(args.app_name, args.resource_group)
        
        # Upload and extract
        upload_and_extract(args.backup_zip, args.app_name, args.resource_group)
        
        # Validate
        validate_remote_files(args.app_name, args.resource_group)
        
        # Cleanup
        cleanup_remote_temp(args.app_name, args.resource_group)
        
        # Restart app service
        start_app_service(args.app_name, args.resource_group)
        
        print("\n✅ Restore complete!")
        print(f"\nApp URL: https://{args.app_name}.azurewebsites.net")
        print("\nNote: It may take 1-2 minutes for the app to fully restart.")
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Restore interrupted by user.")
        print("   The App Service may be in an inconsistent state.")
        print("   Consider running restore again or restoring from pre-restore backup.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}", file=sys.stderr)
        print("   The App Service may be in an inconsistent state.")
        print("   Consider restoring from pre-restore backup.")
        sys.exit(3)


if __name__ == '__main__':
    main()
