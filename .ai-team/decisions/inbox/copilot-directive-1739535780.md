### 2026-02-15: Pre-backup file location (VERIFIED)
**By:** McManus
**What:** Pre-backup files are already stored in `backups/` directory within the project root using Windows-compatible paths via `os.path.join(BASE_DIR, 'backups', f'pre-restore-{timestamp}')`.
**Why:** The implementation at line 3559 in `src/app.py` has always used the proper `backups/` directory. No `/tmp` usage exists in the backup/restore code. This was verified by checking both current code and git history (commit 5861616 initial implementation).
