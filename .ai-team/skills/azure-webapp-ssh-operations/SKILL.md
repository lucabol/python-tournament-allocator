---
name: "azure-webapp-ssh-operations"
description: "Using az webapp ssh for remote filesystem operations on Azure App Service Linux containers"
domain: "azure"
confidence: "low"
source: "earned"
---

## Context
Azure App Service on Linux provides SSH access to the container via `az webapp ssh`. This enables direct filesystem operations on the persistent `/home/` directory without using FTP (deprecated) or Kudu SCM APIs (complex for bulk operations). Common use case: backup/restore of application data stored in `/home/data`.

## Patterns

### Remote Command Execution
```bash
# Execute command and exit
az webapp ssh --name <app-name> --resource-group <rg> <<< "ls -la /home/data"

# Multiple commands
az webapp ssh --name <app-name> --resource-group <rg> <<< "cd /home/data && ls -la"
```

### Creating Remote Archive
```python
# Python subprocess approach
import subprocess

remote_tar = "/tmp/backup.tar.gz"
tar_command = f"tar -czf {remote_tar} -C /home data 2>/dev/null && echo SUCCESS"

result = subprocess.run(
    ['az', 'webapp', 'ssh', '--name', app_name, '--resource-group', rg],
    input=tar_command + '\nexit\n',
    capture_output=True,
    text=True,
    timeout=120
)

if 'SUCCESS' not in result.stdout:
    # Handle error
    pass
```

### Downloading Files via stdout
```python
# Download by redirecting remote file to stdout
download_command = f"cat {remote_file}"

result = subprocess.run(
    ['az', 'webapp', 'ssh', '--name', app_name, '--resource-group', rg],
    input=download_command + '\nexit\n',
    capture_output=True,  # Binary stdout
    timeout=120
)

# Write binary stdout to local file
with open(local_file, 'wb') as f:
    f.write(result.stdout)
```

### Verification Pattern
```python
def verify_app_service(app_name: str, resource_group: str) -> bool:
    """Check if App Service is accessible before SSH operations."""
    result = subprocess.run(
        ['az', 'webapp', 'show', '--name', app_name, '--resource-group', resource_group],
        capture_output=True,
        text=True,
        check=False
    )
    return result.returncode == 0
```

## Prerequisites
- Azure CLI installed (`az --version`)
- Authenticated session (`az login`, check with `az account show`)
- Target is Linux App Service (Windows doesn't support SSH)
- SSH access enabled (default for Linux containers)

## Limitations
- **Timeout risk**: Large files or slow operations need appropriate timeout values (120s+ recommended)
- **Binary data**: Use `capture_output=True` without `text=True` for binary downloads
- **Session cleanup**: Always send `exit\n` after commands to prevent hanging sessions
- **Error detection**: Check for success markers (e.g., `echo SUCCESS`) since exit codes may not propagate reliably through SSH

## Common Use Cases

### Backup /home/data directory
```python
# 1. Create remote tar
tar_cmd = "tar -czf /tmp/data.tar.gz -C /home data && echo SUCCESS"
result = subprocess.run(
    ['az', 'webapp', 'ssh', '--name', app, '--resource-group', rg],
    input=tar_cmd + '\nexit\n',
    capture_output=True,
    text=True,
    timeout=120
)

# 2. Download tar
download_cmd = "cat /tmp/data.tar.gz"
result = subprocess.run(
    ['az', 'webapp', 'ssh', '--name', app, '--resource-group', rg],
    input=download_cmd + '\nexit\n',
    capture_output=True,
    timeout=120
)
with open('backup.tar.gz', 'wb') as f:
    f.write(result.stdout)
```

### Restore data directory
```python
# Upload via stdin redirection not directly supported
# Alternative: Use az webapp deployment source config-zip or Kudu API
```

## Anti-Patterns
- **Using text=True for binary data** — corrupts downloads
- **No timeout** — hangs indefinitely on stuck commands
- **Forgetting exit command** — leaves SSH sessions open
- **Assuming exit codes work** — check stdout markers instead

## Why Not Alternatives?

| Alternative | Why SSH is Better |
|-------------|-------------------|
| FTP | Deprecated by Azure, requires separate credentials |
| Kudu SCM API | Complex authentication, requires recursive file tree walking |
| az webapp download | Only works for deployment artifacts, not `/home/data` |
| Azure Storage Mount | Requires separate Storage Account setup |

SSH provides direct filesystem access with only Azure CLI dependency.
