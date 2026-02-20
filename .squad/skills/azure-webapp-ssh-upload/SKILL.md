---
name: "azure-webapp-ssh-upload"
description: "Uploading binary files to Azure App Service using base64 encoding through az webapp ssh"
domain: "cloud-deployment"
confidence: "low"
source: "earned"
---

## Context
Azure App Service's `az webapp ssh` command provides remote shell access, but has command-length limitations that make direct binary uploads challenging. Base64 encoding with chunked transmission provides a reliable workaround for uploading files like ZIPs or databases.

## Patterns

### Basic SSH Command Execution
```python
# Execute remote command
run_az(['webapp', 'ssh', '--name', app_name, '--resource-group', rg_name,
        '--command', 'echo "Hello" > /tmp/test.txt'])
```

### Binary File Upload via Base64 Chunks
```python
import base64

def upload_file_to_webapp(local_path: str, remote_path: str, app_name: str, rg: str):
    """Upload file using base64 encoding to avoid binary issues."""
    with open(local_path, 'rb') as f:
        data = f.read()
    
    # Encode to base64
    encoded = base64.b64encode(data).decode('ascii')
    
    # Split into chunks (Azure CLI has command length limits)
    chunk_size = 50000
    chunks = [encoded[i:i+chunk_size] for i in range(0, len(encoded), chunk_size)]
    
    # Create empty file
    run_az(['webapp', 'ssh', '--name', app_name, '--resource-group', rg,
            '--command', f'echo "" > {remote_path}.b64'])
    
    # Append chunks
    for chunk in chunks:
        run_az(['webapp', 'ssh', '--name', app_name, '--resource-group', rg,
                '--command', f'echo "{chunk}" >> {remote_path}.b64'])
    
    # Decode to binary
    run_az(['webapp', 'ssh', '--name', app_name, '--resource-group', rg,
            '--command', f'base64 -d {remote_path}.b64 > {remote_path}'])
    
    # Cleanup
    run_az(['webapp', 'ssh', '--name', app_name, '--resource-group', rg,
            '--command', f'rm {remote_path}.b64'])
```

### Remote File Validation
```python
def file_exists_remote(file_path: str, app_name: str, rg: str) -> bool:
    """Check if file exists on remote."""
    result = run_az(['webapp', 'ssh', '--name', app_name, '--resource-group', rg,
                     '--command', f'test -f {file_path} && echo "exists" || echo "missing"'])
    return 'exists' in result.stdout
```

## Common Use Cases
- **Database restores**: Upload backup files and restore remotely
- **Configuration deployment**: Upload config files without full app redeployment
- **Data migration**: Transfer data files between environments
- **Log retrieval**: Download logs or dumps from production

## Why Base64 Encoding?
- **Binary safety**: Shell commands expect text, base64 ensures no binary corruption
- **Command length limits**: Chunking avoids Azure CLI command length restrictions
- **Reliable transmission**: No escaping issues with special characters

## Anti-Patterns
- **Large files without progress**: Add progress indicators for multi-chunk uploads
- **No cleanup**: Always remove temp .b64 files after decode
- **No validation**: Verify file integrity after upload (size or checksum)
- **Direct binary echo**: Using `echo` with binary data corrupts files

## Examples

### ZIP File Upload and Extract
```python
# Upload backup ZIP
upload_file_to_webapp('backup.zip', '/tmp/backup.zip', app_name, rg)

# Extract remotely
run_az(['webapp', 'ssh', '--name', app_name, '--resource-group', rg,
        '--command', 'unzip -o /tmp/backup.zip -d /home/data'])

# Validate extraction
if not file_exists_remote('/home/data/users.yaml', app_name, rg):
    raise Exception('Extraction failed')
```

### Stop App Service During Operations
```python
# Stop app to prevent file corruption during restore
run_az(['webapp', 'stop', '--name', app_name, '--resource-group', rg])

try:
    upload_file_to_webapp('data.zip', '/tmp/data.zip', app_name, rg)
    run_az(['webapp', 'ssh', '--name', app_name, '--resource-group', rg,
            '--command', 'unzip -o /tmp/data.zip -d /home/data'])
finally:
    # Always restart
    run_az(['webapp', 'start', '--name', app_name, '--resource-group', rg])
```

### Remote Directory Operations
```bash
# Create backup directory
az webapp ssh --name myapp --resource-group myrg \
    --command 'mkdir -p /home/backups/$(date +%Y%m%d)'

# List files in data directory
az webapp ssh --name myapp --resource-group myrg \
    --command 'ls -lh /home/data'

# Check disk usage
az webapp ssh --name myapp --resource-group myrg \
    --command 'df -h /home'
```

## Notes
- Azure App Service `/home` directory is persistent across deployments
- `/home/site/wwwroot` is replaced on each deploy
- SSH access requires Basic (B1+) or higher tier
- Command timeout is typically 600 seconds for long operations
