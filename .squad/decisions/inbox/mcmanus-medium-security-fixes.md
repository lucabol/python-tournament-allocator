# Decision: Medium Security Fixes (F04–F10)

**Author:** McManus (Backend Dev)
**Date:** 2025-07-22
**Status:** Implemented

## Context
Kobayashi's security audit identified 7 MEDIUM severity findings. These are the second batch after the 3 HIGH findings (F01–F03) were already fixed.

## Decisions Made

1. **F04 — Path traversal in logo endpoint:** Applied same validation pattern as `_resolve_public_tournament_dir` — reject `..`, `/`, `\` in query params. Consistent with F03 fix.

2. **F05 — Session lifetime reduced to 30 days:** Down from 10 years. Users will need to re-login monthly. Acceptable security/convenience tradeoff for a tournament app.

3. **F06 — Security headers via `@app.after_request`:** Added 4 standard headers. Deliberately did NOT add `Content-Security-Policy` — the app uses inline scripts extensively and CSP would break functionality without a significant template refactor.

4. **F07 — Minimum password length increased to 8:** Only enforced on new registrations. Existing accounts are unaffected — no forced password reset. Error message updated accordingly.

5. **F08 — Flask-Limiter for login rate limiting:** 5 attempts per minute on login POST only. No global rate limits — tournament events involve many rapid API calls from organizers. Uses in-memory storage (acceptable for single-worker gunicorn deployment per F14 finding).

6. **F09 — Debug mode gated by env var:** `FLASK_DEBUG` env var controls debug mode, defaults to `false`. Production startup via gunicorn (startup.sh) is unaffected since gunicorn ignores `app.run()`.

7. **F10 — Secret key already secure:** `_get_or_create_secret_key()` already checks `SECRET_KEY` env var first, falling back to file-persisted key. No change needed.

## Impact
- F04, F06, F08, F09, F10: Invisible to users
- F05: Users re-login every 30 days instead of never
- F07: New accounts need 8+ character passwords
