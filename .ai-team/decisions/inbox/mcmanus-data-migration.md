### 2026-02-15: One-time data migration from old location to TOURNAMENT_DATA_DIR

**By:** McManus

**What:** Added shell-based migration logic in `startup.sh` that moves user data from the legacy location (`/home/site/wwwroot/data`) to the new persistent location (`/home/data`) on first startup.

**Why:** When we deployed the `TOURNAMENT_DATA_DIR` change (2026-02-11), existing Azure deployments had all their user data in `/home/site/wwwroot/data`. The backup system correctly targets `/home/data`, but that directory was empty on existing sites. This one-time migration runs before Flask starts, detects the situation, and relocates the data automatically.

**Pattern:**
- Migration runs in `startup.sh` BEFORE Flask starts (not in Python)
- Checks if target is empty (ignoring `.lock` file)
- Checks if source exists with `users/` directory
- Uses `mv` (not `cp`) to relocate files
- Idempotent — safe to run multiple times
- Logs when migration runs for debugging

**Decision:** Shell-based migrations for filesystem changes belong in `startup.sh`, not in Python `before_request` hooks. This ensures the filesystem is in the correct state before any application code runs.
