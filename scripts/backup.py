#!/usr/bin/env python3
"""
HTTP-based Tournament Allocator Backup Tool

Downloads backup from Flask /api/admin/export endpoint via HTTP.
Saves as timestamped ZIP file in backups/ directory.

Usage:
    python scripts/backup.py

Configuration:
    Requires .env file or environment variables:
    - BACKUP_API_KEY: API key for authentication
    - AZURE_APP_NAME: App Service name (e.g., 'tournament-allocator')

Exit codes:
    0: Success
    1: Configuration error or backup failed
"""

import os
import sys
import requests
from dotenv import load_dotenv
from datetime import datetime
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


def download_backup():
    """Download backup ZIP from Flask API."""
    url = f"https://{APP_NAME}.azurewebsites.net/api/admin/export"
    headers = {'Authorization': f'Bearer {API_KEY}'}
    
    print(f"📥 Downloading backup from {APP_NAME}.azurewebsites.net...")
    
    try:
        response = requests.get(url, headers=headers, stream=True, timeout=120)
        
        # Handle errors
        if response.status_code == 401:
            print("❌ Error: Authentication failed (401 Unauthorized)", file=sys.stderr)
            print("   Check your BACKUP_API_KEY in .env file", file=sys.stderr)
            return None
        
        if response.status_code == 500:
            print("❌ Error: Server error (500 Internal Server Error)", file=sys.stderr)
            print("   Check app logs for details", file=sys.stderr)
            return None
        
        if response.status_code != 200:
            print(f"❌ Error: Unexpected response ({response.status_code})", file=sys.stderr)
            print(f"   Response: {response.text}", file=sys.stderr)
            return None
        
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
        
        print(f"✅ Backup downloaded successfully!")
        print(f"   Location: {output_path}")
        print(f"   Size: {file_size / 1024 / 1024:.2f} MB")
        
        return output_path
        
    except requests.exceptions.Timeout:
        print("❌ Error: Request timed out after 120 seconds", file=sys.stderr)
        print("   The server may be unresponsive", file=sys.stderr)
        return None
    
    except requests.exceptions.ConnectionError as e:
        print("❌ Error: Connection failed", file=sys.stderr)
        print(f"   Could not connect to {url}", file=sys.stderr)
        print(f"   Details: {e}", file=sys.stderr)
        return None
    
    except Exception as e:
        print(f"❌ Error: Unexpected error during download", file=sys.stderr)
        print(f"   {e}", file=sys.stderr)
        return None


def main():
    """Main entry point."""
    print("=== Tournament Allocator Backup ===\n")
    
    # Validate configuration
    if not validate_config():
        return 1
    
    # Download backup
    result = download_backup()
    
    if result is None:
        return 1
    
    return 0


if __name__ == '__main__':
    sys.exit(main())
