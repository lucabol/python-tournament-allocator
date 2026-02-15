### 2026-02-15: Backup API routes must bypass session authentication

**By:** McManus

**What:** The `/api/admin/export` and `/api/admin/import` routes have been added to the `before_request` whitelist so they can use API key authentication instead of session-based login.

**Why:** These routes use the `@require_backup_key` decorator which validates a `BACKUP_API_KEY` from environment variables. They're designed for automated backup/restore operations that can't use browser sessions. By adding them to the whitelist (alongside other non-session routes like public live views), they bypass the "redirect to login if no session" check and handle their own authentication.

**Pattern:** Any route that uses custom authentication (API keys, public access, etc.) should be added to the `before_request` whitelist at the top of `set_active_tournament()`. Session-based routes stay off the whitelist and get the default "require login" behavior.
