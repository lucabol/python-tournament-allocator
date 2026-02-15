#!/usr/bin/env python3
"""
Quick local test for backup routes.
Run the Flask app, then run this script to test the endpoints.
"""
import os
import sys
import requests
import tempfile
import zipfile
from datetime import datetime

# Configuration
BASE_URL = "http://localhost:5000"
API_KEY = os.environ.get('BACKUP_API_KEY', 'test-key-12345')

def test_export():
    """Test the export endpoint."""
    print("\n=== Testing Export Endpoint ===")
    url = f"{BASE_URL}/api/admin/export"
    headers = {'Authorization': f'Bearer {API_KEY}'}
    
    print(f"GET {url}")
    print(f"Authorization: Bearer {API_KEY[:10]}...")
    
    response = requests.get(url, headers=headers)
    print(f"Status: {response.status_code}")
    
    if response.status_code == 200:
        print(f"Content-Type: {response.headers.get('Content-Type')}")
        print(f"Content-Disposition: {response.headers.get('Content-Disposition')}")
        print(f"File size: {len(response.content)} bytes")
        
        # Verify it's a valid ZIP
        with tempfile.NamedTemporaryFile(delete=False, suffix='.zip') as tmp:
            tmp.write(response.content)
            tmp_path = tmp.name
        
        try:
            with zipfile.ZipFile(tmp_path, 'r') as zf:
                files = zf.namelist()
                print(f"✅ Valid ZIP with {len(files)} files")
                print(f"Sample files: {files[:5]}")
        except zipfile.BadZipFile:
            print("❌ Not a valid ZIP file")
        finally:
            os.unlink(tmp_path)
    else:
        print(f"❌ Error: {response.text}")

def test_export_unauthorized():
    """Test export with invalid key."""
    print("\n=== Testing Export (Invalid Key) ===")
    url = f"{BASE_URL}/api/admin/export"
    headers = {'Authorization': 'Bearer wrong-key'}
    
    response = requests.get(url, headers=headers)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    
    if response.status_code == 401:
        print("✅ Correctly rejected invalid key")
    else:
        print("❌ Should have returned 401")

def test_export_missing_header():
    """Test export with missing Authorization header."""
    print("\n=== Testing Export (Missing Header) ===")
    url = f"{BASE_URL}/api/admin/export"
    
    response = requests.get(url)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    
    if response.status_code == 401:
        print("✅ Correctly rejected missing header")
    else:
        print("❌ Should have returned 401")

def test_import_no_file():
    """Test import with no file."""
    print("\n=== Testing Import (No File) ===")
    url = f"{BASE_URL}/api/admin/import"
    headers = {'Authorization': f'Bearer {API_KEY}'}
    
    response = requests.post(url, headers=headers)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    
    if response.status_code == 400:
        print("✅ Correctly rejected missing file")
    else:
        print("❌ Should have returned 400")

def test_import_invalid_zip():
    """Test import with non-ZIP file."""
    print("\n=== Testing Import (Invalid ZIP) ===")
    url = f"{BASE_URL}/api/admin/import"
    headers = {'Authorization': f'Bearer {API_KEY}'}
    
    # Upload a text file pretending to be a ZIP
    files = {'file': ('test.zip', b'not a zip file', 'application/zip')}
    response = requests.post(url, headers=headers, files=files)
    print(f"Status: {response.status_code}")
    print(f"Response: {response.json()}")
    
    if response.status_code == 400:
        print("✅ Correctly rejected invalid ZIP")
    else:
        print("❌ Should have returned 400")

def main():
    """Run all tests."""
    print("=" * 60)
    print("Testing Flask Backup Routes")
    print("=" * 60)
    print(f"Base URL: {BASE_URL}")
    print(f"Using API Key: {API_KEY[:10]}...")
    
    try:
        # Test authentication
        test_export_unauthorized()
        test_export_missing_header()
        
        # Test export
        test_export()
        
        # Test import error cases
        test_import_no_file()
        test_import_invalid_zip()
        
        print("\n" + "=" * 60)
        print("✅ All basic tests completed")
        print("=" * 60)
        
    except requests.exceptions.ConnectionError:
        print("\n❌ Could not connect to Flask app.")
        print("Make sure the Flask app is running:")
        print("  export BACKUP_API_KEY='test-key-12345'")
        print("  python src/app.py")
        sys.exit(1)

if __name__ == '__main__':
    main()
