# Session Log: 2026-02-16 Scribe Inbox Merge

**Requested by:** Luca Bolognese

## Work Summary

Scribe processed 10 decision inbox files and merged them into `decisions.md`.

### New Decisions Added (in merge order)

1. **HTTP backup/restore architecture with API key authentication** (McManus, 2026-02-14)
   - Replaces SSH-based backup with HTTP routes secured by API key
   - Enables automated backup via standard HTTP tools without SSH access
   - Security: timing-attack-safe key comparison via hmac

2. **Backup API routes must bypass session authentication** (McManus, 2026-02-15)
   - Added `/api/admin/export` and `/api/admin/import` to `before_request` whitelist
   - Routes use custom `@require_backup_key` decorator instead of session auth
   - Enables automated backup/restore without browser sessions

3. **One-time data migration from old location to TOURNAMENT_DATA_DIR** (McManus, 2026-02-15)
   - Shell-based migration in `startup.sh` moves data from `/home/site/wwwroot/data` to `/home/data`
   - Idempotent and runs before Flask starts
   - Decision: Shell migrations belong in `startup.sh`, not Python `before_request` hooks

4. **Auto-generate backup API key in deployment script** (Keaton, 2026-02-15)
   - `deploy.ps1` auto-generates 32-byte random hex key if missing
   - Syncs between Azure App Settings and local `.env`
   - Preserves existing key on subsequent deploys

5. **Pre-restore backup file location (VERIFIED)** (McManus, 2026-02-15)
   - Verified pre-backup files use `backups/` directory via `os.path.join()`
   - No `/tmp` usage; Windows-compatible paths confirmed
   - Implementation at line 3559 in `src/app.py`

6. **Remove Admin User Concept** (Verbal, 2026-02-19)
   - Deleted all privileged admin logic, functions, routes, and env vars
   - Removed ADMIN_PASSWORD, `is_admin()`, `_ensure_admin_user_exists()`, `/api/export/site`, `/api/import/site`
   - Each user manages their own tournaments; no admin needed
   - 450/457 tests pass

7. **Consecutive matches should be avoided via soft CP-SAT penalty** (Verbal, 2026-02-20)
   - When `pool_in_same_court` enabled, add soft penalties discouraging consecutive matches
   - Graduated: 2-in-a-row light penalty, 3-in-a-row heavy penalty
   - Soft constraint (penalty in objective) preserves schedule feasibility

8. **Consecutive match detection approach** (McManus, 2026-02-16)
   - Added boolean variables to CP-SAT model detecting matches too close together (within 2× duration)
   - Uses reification: `model.Add(abs_diff < threshold).OnlyEnforceIf(is_consecutive)`
   - O(T × M²) complexity; detection variables ready for objective penalty
   - Next step: Add `consecutive_penalty × penalty_weight` to objective

9. **Test Structure for Consecutive Match Feature** (Hockney, 2026-02-16)
   - Created `tests/test_consecutive.py` with 10 test cases
   - Uses monkey-patching to inject custom match lists
   - Tests verify both optimization goal and soft constraint property
   - 20-minute threshold accounts for typical match+break duration

## Actions Taken

1. Merged 9 new decision entries into `decisions.md`
2. Deleted all 10 inbox files from `.ai-team/decisions/inbox/`
3. No deduplication needed — all decisions were independent

## Notes

- No overlapping/duplicate decisions detected
- No consolidation needed — each decision covers distinct topics
- All decisions properly formatted with date, author, what/why sections
- No affected agent history files to update (none exist yet)
