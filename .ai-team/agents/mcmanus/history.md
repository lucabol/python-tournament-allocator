# McManus — Backend Dev History

## Completed Work

### 2025-07-22 — Security Fixes (F01, F02, F03)
Fixed the 3 HIGH severity findings from Kobayashi's security audit:
- **F01 — CSRF Protection:** Installed Flask-WTF, enabled CSRFProtect globally. Added CSRF meta tag to `base.html` with global fetch() override and auto-inject for forms. Exempted public endpoints: `public_register`, `api_report_result`, `api_message`, `api_admin_import`.
- **F02 — @login_required on ~30 routes:** Added explicit `@login_required` decorator to all 28 state-mutating routes identified in the audit (API endpoints + page routes for teams, courts, settings, schedule, tournaments).
- **F03 — Path traversal in award image:** Added validation in `api_awards_image` to reject filenames containing `/`, `\`, or `..`.

All 283 core tests pass. No UX changes.

## Learnings

- Flask-WTF's `CSRFProtect` validates POST/PUT/DELETE/PATCH by default. Use `@csrf.exempt` for public endpoints that don't use sessions.
- The global `fetch()` override in `base.html` is the cleanest way to add CSRF headers to all AJAX calls without touching every template individually. Same approach for auto-injecting hidden `csrf_token` fields into forms via `DOMContentLoaded`.
- Test fixtures need `app.config['WTF_CSRF_ENABLED'] = False` since CSRF is initialized at import time before `TESTING` is set.
- The `before_request` hook provides defense-in-depth but should not be the sole auth gate — explicit `@login_required` on each route is required for API endpoints.

### 2025-07-22 — Security Fixes (F04–F10)
Fixed all 7 MEDIUM severity findings from Kobayashi's security audit:
- **F04 — Path traversal in logo endpoint:** Added `..`, `/`, `\` validation on `username` and `slug` query params in `api_logo` before constructing filesystem path.
- **F05 — Session lifetime:** Reduced `PERMANENT_SESSION_LIFETIME` from 3650 days (10 years) to 30 days.
- **F06 — Security headers:** Added `@app.after_request` handler setting `X-Content-Type-Options`, `X-Frame-Options`, `X-XSS-Protection`, and `Referrer-Policy`.
- **F07 — Password strength:** Increased minimum password length from 4 to 8 characters in `create_user()`. Only affects new registrations.
- **F08 — Login rate limiting:** Installed Flask-Limiter, applied `5 per minute` limit to login POST only. No rate limiting on other routes.
- **F09 — Debug mode:** Changed `app.run(debug=True)` to use `FLASK_DEBUG` env var (defaults to false).
- **F10 — Secret key:** Already loaded from `SECRET_KEY` env var with file fallback — no change needed.

All 110 app tests pass. F05 and F07 have minor visible UX impact (login every 30 days, 8-char passwords); all others invisible.

### 2025-07-22 — Bracket Result Key Unification
Unified the bracket result key system so the Bracket tab and Schedule tab always show the same data. Root cause was three different key formats for the same match (match_code like `W1-M1`, match_key like `winners_Winners Quarterfinal_1`, and round_name internal tracking).

**Changes:**
- **`save_bracket_result()`**: Primary key is now `match_code` (e.g. `W1-M1`). Old-format key stored as secondary for backward compat.
- **`api_generate_random_bracket_results()`**: All 10 result-saving blocks now use `match_code` as primary key with old-format fallback.
- **`enrich_schedule_with_results()`**: Removed `derive_match_code()` heuristic function and `round_indices` mapping (~30 lines). Results now looked up directly by match_code key. Team-pair fallback kept for old-format results.
- **3 new integration tests**: Full round-trip test (schedule → pool results → bracket results → enriched schedule verification), save-under-match_code verification, and clear-both-keys verification.

All 113 app tests pass, all 144 bracket consistency tests pass.

## Learnings (Bracket Keys)

- When multiple code paths store data under different key formats, the key unification approach is: pick one canonical key, store under it as primary, and store under old keys as secondary for backward compat. This is safer than building translation layers between formats.
- The `derive_match_code()` heuristic was fragile because it reconstructed match_code from round_indices built by iterating results in insertion order. Eliminating heuristic reconstruction in favor of direct storage is always preferable.
