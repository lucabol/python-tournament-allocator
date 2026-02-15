#!/usr/bin/env python3
"""
HTTP-based Tournament Allocator Restore Tool

Downloads current state as backup, then uploads restore ZIP to Flask /api/admin/import endpoint.

Usage:
    python scripts/restore.py backup.zip
    python scripts/restore.py  # Will prompt for file path

Configuration:
    Requires .env file or environment variables:
    - BACKUP_API_KEY: API key for authentication
    - AZURE_APP_NAME: App Service name (e.g., 'tournament-allocator')

Exit codes:
    0: Success
    1: Configuration error or restore failed
"""

import os
import sys
import requests
import zipfile
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables from .env file
load_dotenv()

# Configuration
API_KEY = os.getenv('BACKUP_API_KEY')
APP_NAME = os.getenv('AZURE_APP_NAME')


def validate_config():
    """Validate required configuration is present."""
    if not API_KEY:
        print("❌ Error: BACKUP_API_KEY not found in .env file or environment", file=sys.stderr)
        print("   Add BACKUP_API_KEY=your-key-here to .env file", file=sys.stderr)
        return False
    
    if not APP_NAME:
        print("❌ Error: AZURE_APP_NAME not found in .env file or environment", file=sys.stderr)
        print("   Add AZURE_APP_NAME=your-app-name to .env file", file=sys.stderr)
        return False
    
    return True


def get_backup_file_path():
    """Get backup file path from CLI arg or prompt."""
    if len(sys.argv) > 1:
        # Path provided as CLI argument
        return sys.argv[1]
    else:
        # Prompt user
        return input("Enter path to backup ZIP file: ").strip()


def validate_file(file_path):
    """Validate backup file exists and is readable."""
    path = Path(file_path)
    
    if not path.exists():
        print(f"❌ Error: File not found: {file_path}", file=sys.stderr)
        return False
    
    if not path.is_file():
        print(f"❌ Error: Not a file: {file_path}", file=sys.stderr)
        return False
    
    if not file_path.endswith('.zip'):
        print(f"⚠️  Warning: File does not have .zip extension: {file_path}")
        response = input("Continue anyway? (yes/no): ").strip().lower()
        if response != 'yes':
            print("Restore cancelled.")
            return False
    
    return True


def inspect_backup_contents(zip_path):
    """Inspect ZIP and extract user/tournament structure."""
    user_tournaments = {}
    
    try:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            for name in zf.namelist():
                # Look for pattern: users/{username}/tournaments/{slug}/
                # Note: Flask export uses relpath from DATA_DIR, so no 'data/' prefix
                parts = name.split('/')
                if len(parts) >= 4 and parts[0] == 'users' and parts[2] == 'tournaments':
                    username = parts[1]
                    slug = parts[3]
                    
                    if username not in user_tournaments:
                        user_tournaments[username] = set()
                    
                    if slug:  # Not empty (could be a directory marker)
                        user_tournaments[username].add(slug)
        
        # Convert sets to sorted lists
        return {user: sorted(list(tournaments)) for user, tournaments in user_tournaments.items()}
    
    except Exception as e:
        print(f"⚠️  Warning: Could not inspect backup contents: {e}", file=sys.stderr)
        return {}


def show_backup_contents(zip_path):
    """Display user and tournament list from backup."""
    contents = inspect_backup_contents(zip_path)
    
    if not contents:
        print("\n📋 Backup Contents: No user data found")
        return
    
    print(f"\n📋 Backup Contents:")
    user_count = len(contents)
    total_tournaments = sum(len(tournaments) for tournaments in contents.values())
    print(f"   Users: {user_count}")
    print(f"   Total tournaments: {total_tournaments}")
    print()
    
    for username in sorted(contents.keys()):
        tournaments = contents[username]
        print(f"   • {username} ({len(tournaments)} tournament{'s' if len(tournaments) != 1 else ''})")
        for slug in tournaments:
            print(f"     - {slug}")


def confirm_restore(file_path):
    """Show confirmation prompt before restore."""
    file_size = os.path.getsize(file_path)
    file_size_mb = file_size / 1024 / 1024
    
    # Show backup contents first
    show_backup_contents(file_path)
    
    print("\n⚠️  WARNING: This will replace ALL data on the App Service.")
    print(f"   Target: {APP_NAME}.azurewebsites.net")
    print(f"   Source: {file_path}")
    print(f"   Size: {file_size_mb:.2f} MB")
    print()
    
    response = input("Type 'RESTORE' to continue: ").strip()
    
    if response != 'RESTORE':
        print("Restore cancelled.")
        return False
    
    return True


def download_pre_restore_backup():
    """Download current state from server before restoring."""
    from datetime import datetime
    
    url = f"https://{APP_NAME}.azurewebsites.net/api/admin/export"
    headers = {'Authorization': f'Bearer {API_KEY}'}
    
    print(f"\n💾 Creating pre-restore backup...")
    
    try:
        response = requests.get(url, headers=headers, stream=True, timeout=120)
        
        # Handle errors
        if response.status_code == 401:
            print("❌ Error: Authentication failed (401 Unauthorized)", file=sys.stderr)
            print("   Check your BACKUP_API_KEY in .env file", file=sys.stderr)
            return False
        
        if response.status_code == 500:
            print("❌ Error: Server error (500 Internal Server Error)", file=sys.stderr)
            print("   Check app logs for details", file=sys.stderr)
            return False
        
        if response.status_code != 200:
            print(f"❌ Error: Unexpected response ({response.status_code})", file=sys.stderr)
            print(f"   Response: {response.text}", file=sys.stderr)
            return False
        
        # Create backups directory if needed
        script_dir = Path(__file__).parent.parent
        backups_dir = script_dir / 'backups'
        backups_dir.mkdir(exist_ok=True)
        
        # Generate timestamped filename
        timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
        output_path = backups_dir / f'tournament-backup-{timestamp}.zip'
        
        # Save response content
        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        # Get file size
        file_size = os.path.getsize(output_path)
        
        print(f"   ✅ Pre-restore backup saved: {output_path.relative_to(script_dir)}")
        print(f"   Size: {file_size / 1024 / 1024:.2f} MB")
        
        return True
        
    except requests.exceptions.Timeout:
        print("❌ Error: Request timed out after 120 seconds", file=sys.stderr)
        print("   The server may be unresponsive", file=sys.stderr)
        return False
    
    except requests.exceptions.ConnectionError as e:
        print("❌ Error: Connection failed", file=sys.stderr)
        print(f"   Could not connect to {url}", file=sys.stderr)
        print(f"   Details: {e}", file=sys.stderr)
        return False
    
    except Exception as e:
        print(f"❌ Error: Unexpected error during backup", file=sys.stderr)
        print(f"   {e}", file=sys.stderr)
        return False


def upload_restore(file_path):
    """Upload backup ZIP to Flask API for restore."""
    url = f"https://{APP_NAME}.azurewebsites.net/api/admin/import"
    headers = {'Authorization': f'Bearer {API_KEY}'}
    
    # Create pre-restore backup BEFORE uploading
    if not download_pre_restore_backup():
        print("❌ Failed to create pre-restore backup. Aborting restore.", file=sys.stderr)
        return False
    
    print(f"\n📤 Uploading backup to {APP_NAME}.azurewebsites.net...")
    
    try:
        # Open file and prepare multipart upload
        with open(file_path, 'rb') as f:
            files = {'file': (os.path.basename(file_path), f, 'application/zip')}
            
            # Upload with timeout (allow 5 minutes for upload + processing)
            response = requests.post(
                url, 
                headers=headers, 
                files=files, 
                timeout=300
            )
        
        # Handle errors
        if response.status_code == 401:
            print("❌ Error: Authentication failed (401 Unauthorized)", file=sys.stderr)
            print("   Check your BACKUP_API_KEY in .env file", file=sys.stderr)
            return False
        
        if response.status_code == 400:
            print("❌ Error: Bad request (400)", file=sys.stderr)
            print(f"   Server response: {response.text}", file=sys.stderr)
            return False
        
        if response.status_code == 500:
            print("❌ Error: Server error (500 Internal Server Error)", file=sys.stderr)
            print(f"   Server response: {response.text}", file=sys.stderr)
            print("   Check app logs for details", file=sys.stderr)
            return False
        
        if response.status_code != 200:
            print(f"❌ Error: Unexpected response ({response.status_code})", file=sys.stderr)
            print(f"   Response: {response.text}", file=sys.stderr)
            return False
        
        # Parse JSON response
        try:
            result = response.json()
            print("✅ Restore completed successfully!")
            print(f"   Message: {result.get('message', 'Data restored')}")
            
            return True
            
        except ValueError:
            # Response wasn't JSON - show text
            print("✅ Restore completed!")
            print(f"   Server response: {response.text}")
            return True
        
    except requests.exceptions.Timeout:
        print("❌ Error: Request timed out after 300 seconds", file=sys.stderr)
        print("   The restore may still be processing on the server", file=sys.stderr)
        print("   Check the app to verify if restore completed", file=sys.stderr)
        return False
    
    except requests.exceptions.ConnectionError as e:
        print("❌ Error: Connection failed", file=sys.stderr)
        print(f"   Could not connect to {url}", file=sys.stderr)
        print(f"   Details: {e}", file=sys.stderr)
        return False
    
    except FileNotFoundError:
        print(f"❌ Error: File not found: {file_path}", file=sys.stderr)
        return False
    
    except Exception as e:
        print(f"❌ Error: Unexpected error during upload", file=sys.stderr)
        print(f"   {e}", file=sys.stderr)
        return False


def main():
    """Main entry point."""
    print("=== Tournament Allocator Restore ===\n")
    
    # Validate configuration
    if not validate_config():
        return 1
    
    # Get backup file path
    file_path = get_backup_file_path()
    
    # Validate file
    if not validate_file(file_path):
        return 1
    
    # Confirm restore
    if not confirm_restore(file_path):
        return 0
    
    # Upload and restore
    success = upload_restore(file_path)
    
    if not success:
        return 1
    
    print(f"\nℹ️  The app may take 30-60 seconds to fully reload the data.")
    print(f"   Visit: https://{APP_NAME}.azurewebsites.net")
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
