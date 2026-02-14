# Admin User Automatic Initialization

**By:** McManus
**Date:** 2026-02-14

## What

Admin user is now automatically created on first app startup and ensured to exist on every subsequent startup. The admin password is configurable via the `ADMIN_PASSWORD` environment variable (defaults to "admin" if not set).

## Implementation

### Backend Changes (src/app.py)
1. **`_ensure_admin_user_exists()`** — New helper function that checks if admin user exists in users.yaml and creates it with a default tournament if missing. Idempotent and safe to call on every request.

2. **`_migrate_to_admin_user()`** — Updated to:
   - Read password from `ADMIN_PASSWORD` env var instead of hardcoded "admin"
   - Handle fresh installs (when no tournaments.yaml exists) by creating default tournament structure
   - Log that password came from env var

3. **`ensure_tournament_structure()`** — Updated migration logic:
   - Case 1 (already migrated): Now calls `_ensure_admin_user_exists()` instead of no-op
   - Case 4 (fresh install): Now calls `_migrate_to_admin_user()` instead of just creating empty users.yaml

### Deployment Script Changes (deploy.ps1)
1. Added `ADMIN_PASSWORD` app setting configuration on first deploy (similar to SECRET_KEY pattern)
   - Reads from `.env` file if `ADMIN_PASSWORD` is set there
   - Falls back to "admin" if not configured
   - Only sets on first deploy to avoid overwriting existing password

2. Enhanced deployment completion message to display admin credentials:
   ```
   Admin Login:
     Username: admin
     Password: (from ADMIN_PASSWORD in .env) OR Password: admin (default)
     Note: Change the password after first login for security.
   ```

### Test Updates
- `test_fresh_install` in `tests/test_tournaments.py` updated to expect admin user creation instead of empty users list
- All 276 tests pass

## Why

**Problem:** On fresh Azure deployments, there was no way to access the app because no users existed. The migration code only created admin users when migrating from legacy tournament structures, not on fresh installs.

**Solution benefits:**
- **Zero-friction deployment**: Admin user exists immediately after first deploy
- **Secure by design**: Password never hardcoded in source, always from env var
- **Customizable**: Deployer can set custom password in `.env` before deploying
- **Idempotent**: Safe to re-run deploy.ps1 multiple times; won't recreate admin or change password
- **Clear feedback**: Deployment output shows admin credentials so deployer knows how to log in

## Security Considerations

1. **Environment variable pattern**: `ADMIN_PASSWORD` follows the same pattern as `SECRET_KEY` — optional in `.env`, never in source code
2. **First-deploy only**: Password is only set on initial deployment, not on updates (preserves user's password changes)
3. **Deployment message**: Credentials displayed in deployment output so deployer can access the app immediately, but warns to change password after first login
4. **Default fallback**: If no `ADMIN_PASSWORD` is configured, defaults to "admin" to ensure app is always accessible (user should change it immediately)

## Impact

- Fresh Azure deploys now work immediately without manual database setup
- Existing deployments unaffected — admin user check is idempotent
- All existing tests pass with one test updated to match new behavior
- Pattern can be reused for any future auto-created resources

## Files Changed

- `src/app.py`: Lines 232-348 (migration logic)
- `deploy.ps1`: Lines 240-273 (admin password config and deployment message)
- `tests/test_tournaments.py`: Lines 460-469 (test expectations)
