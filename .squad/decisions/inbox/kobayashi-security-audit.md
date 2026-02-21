# Security Audit — Tournament Allocator

**Auditor:** Kobayashi (Security Engineer)  
**Date:** 2025-07-22  
**Scope:** Full OWASP Top 10 audit of Flask tournament allocator application  
**Classification:** Analysis only — no code changes made

---

## Executive Summary

The application has a solid foundation: password hashing via werkzeug, `yaml.safe_load` everywhere, path traversal checks on public endpoints, HMAC-based backup API key comparison, and per-user data isolation. However, there are several medium and high-severity findings primarily around **missing CSRF protection**, **missing `@login_required` on ~30 state-mutating routes**, a **path traversal vulnerability in the award image endpoint**, and **no security headers**. The most impactful fix is adding CSRF tokens and gating all authenticated routes.

---

## Findings

### F01 — No CSRF Protection on Any Form or API Endpoint
- **Severity:** HIGH
- **Location:** All POST routes in `src/app.py` (every form and AJAX endpoint)
- **Impact:** An attacker can craft a malicious page that submits forms or AJAX requests on behalf of a logged-in user — deleting tournaments, modifying scores, resetting all data, or deleting accounts. The permanent session (10-year lifetime, line 48) makes this window very large.
- **Remediation:** Install `Flask-WTF` and enable `CSRFProtect(app)`. For AJAX endpoints, include the CSRF token in a `<meta>` tag and send it as `X-CSRFToken` header. For traditional forms, add `{{ csrf_token() }}` hidden inputs.

### F02 — ~30 State-Mutating Routes Missing `@login_required`
- **Severity:** HIGH
- **Location:** `src/app.py` — the following routes lack `@login_required`:
  - `/api/teams/edit_pool` (line 1994)
  - `/api/teams/edit_team` (line 2014)
  - `/api/teams/update_advance` (line 2049)
  - `/api/courts/edit` (line 2115)
  - `/api/settings/update` (line 2140)
  - `/api/reset` (line 2178) — **resets all tournament data**
  - `/api/test-data` (line 2191)
  - `/api/test-teams` (line 2233)
  - `/api/test-courts` (line 2284)
  - `/api/generate-random-results` (line 2303)
  - `/api/generate-random-bracket-results` (line 2365)
  - `/api/awards/add` (line 3165)
  - `/api/awards/delete` (line 3190)
  - `/api/awards/upload-image` (line 3220)
  - `/api/test-awards` (line 3245)
  - `/api/results/pool` (line 3831)
  - `/api/results/bracket` (line 3913)
  - `/api/clear-result` (line 3997)
  - `/api/upload-logo` (line 3771)
  - `/api/export/tournament` (line 4312)
  - `/api/import/tournament` (line 4339)
  - `/api/tournaments/create` (line 4659)
  - `/api/tournaments/delete` (line 4701)
  - `/api/tournaments/clone` (line 4736)
  - `/api/tournaments/switch` (line 4795)
  - `/teams` POST (line 1355)
  - `/courts` POST (line 1913)
  - `/settings` POST (line 2769)
  - `/schedule` POST (line 2851)
- **Impact:** While the `before_request` hook redirects unauthenticated users for most page routes, the hook explicitly skips `None` endpoints and relies on session checks. The AJAX API routes (especially `/api/reset`, `/api/test-data`, `/api/import/tournament`) are particularly dangerous without explicit auth guards. Combined with F01 (no CSRF), any authenticated user's browser can be weaponized.
- **Remediation:** Add `@login_required` decorator to every state-mutating route. The `before_request` hook provides defense-in-depth but should not be the sole auth gate for API endpoints.

### F03 — Path Traversal in Award Image Endpoint
- **Severity:** HIGH
- **Location:** `src/app.py` lines 3236–3242 (`api_awards_image`)
- **Impact:** The `filename` parameter is taken directly from the URL path and joined with `_tournament_dir()` without sanitization. An attacker could request `/api/awards/image/../../users.yaml` to read the global user registry (including password hashes) or any other file the process can read.
- **Remediation:** Validate that `filename` contains no path separators and starts with an expected prefix:
  ```python
  if '/' in filename or '\\' in filename or '..' in filename:
      abort(400)
  if not filename.startswith('custom-'):
      abort(400)
  ```
  Alternatively, use `flask.send_from_directory()` which has built-in path traversal protection.

### F04 — Path Traversal in Logo Endpoint (Public Access)
- **Severity:** MEDIUM
- **Location:** `src/app.py` lines 3745–3768 (`api_logo`)
- **Impact:** The `username` and `slug` query parameters are used to construct a filesystem path and then `glob.glob()` is called. While `_resolve_public_tournament_dir` (used elsewhere) has traversal checks, the `api_logo` route does NOT use it — it constructs the path directly from `request.args`. An attacker could supply `username=../../etc&slug=passwd` to attempt to glob outside the data directory.
- **Remediation:** Apply the same traversal checks used in `_resolve_public_tournament_dir`:
  ```python
  for part in (username, slug):
      if '..' in part or '/' in part or '\\' in part:
          abort(400)
  ```

### F05 — Overly Long Session Lifetime (10 Years)
- **Severity:** MEDIUM
- **Location:** `src/app.py` line 48 (`app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=3650)`)
- **Impact:** Session cookies remain valid for a decade. If a cookie is stolen (via XSS, network interception, or physical access), the attacker has persistent access for years. Combined with no session invalidation mechanism, there's no way for a user to "log out of all devices."
- **Remediation:** Reduce to 30 days maximum. Consider implementing session ID rotation on login and a "revoke all sessions" feature.

### F06 — No Security Headers
- **Severity:** MEDIUM
- **Location:** `src/app.py` (global — no `after_request` handler)
- **Impact:** Missing headers expose the application to clickjacking (`X-Frame-Options`), MIME-type sniffing (`X-Content-Type-Options`), and makes it harder to mitigate XSS (`Content-Security-Policy`). The SSE streaming endpoints are particularly vulnerable without proper CSP.
- **Remediation:** Add an `@app.after_request` handler:
  ```python
  @app.after_request
  def set_security_headers(response):
      response.headers['X-Content-Type-Options'] = 'nosniff'
      response.headers['X-Frame-Options'] = 'SAMEORIGIN'
      response.headers['X-XSS-Protection'] = '1; mode=block'
      response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
      return response
  ```

### F07 — Weak Password Policy
- **Severity:** MEDIUM
- **Location:** `src/app.py` line 119 (`if len(password) < 4`)
- **Impact:** A 4-character minimum password is trivially brute-forced. There are no complexity requirements, no rate limiting on login attempts, and no account lockout.
- **Remediation:** Increase minimum to 8 characters. Add login rate limiting (e.g., 5 attempts per minute per IP/username). Consider `Flask-Limiter` for rate limiting.

### F08 — No Login Brute-Force Protection
- **Severity:** MEDIUM
- **Location:** `src/app.py` lines 1211–1224 (login route)
- **Impact:** An attacker can attempt unlimited login requests to brute-force user credentials. The username registry is stored in a flat YAML file, making enumeration trivial if file access is gained.
- **Remediation:** Implement rate limiting on the `/login` POST endpoint. Use the existing `check_rate_limit()` pattern or add `Flask-Limiter`.

### F09 — Debug Mode Enabled in Production Entry Point
- **Severity:** MEDIUM
- **Location:** `src/app.py` line 4815 (`app.run(debug=True, port=5000)`)
- **Impact:** If the app is accidentally started with `python app.py` instead of gunicorn, the Werkzeug debugger is exposed, allowing arbitrary code execution on the server. The debugger provides an interactive Python console.
- **Remediation:** Change to `app.run(debug=os.environ.get('FLASK_DEBUG', 'false').lower() == 'true', port=5000)` or simply `app.run(debug=False)`.

### F10 — Secret Key Persisted to Unprotected File
- **Severity:** MEDIUM
- **Location:** `src/app.py` lines 28–41 (`_get_or_create_secret_key`)
- **Impact:** The Flask secret key (used to sign session cookies) is written to `DATA_DIR/.secret_key` as a plain file. If the data directory is exposed (e.g., via the admin export endpoint, misconfigured web server, or a path traversal bug), the secret key is compromised. An attacker with the secret key can forge arbitrary session cookies, impersonating any user.
- **Remediation:** The `.secret_key` file should be excluded from admin exports. Add it to `SITE_EXPORT_SKIP_EXTS` or filter by name. Better yet, require `SECRET_KEY` to be set via environment variable and fail startup if missing.

### F11 — Admin Export Includes Password Hashes and Secret Key
- **Severity:** MEDIUM
- **Location:** `src/app.py` lines 4541–4583 (`api_admin_export`)
- **Impact:** The admin backup endpoint exports the entire `DATA_DIR` as a ZIP, which includes `users.yaml` (containing bcrypt password hashes) and `.secret_key`. If the backup file is intercepted or stored insecurely, all password hashes and the session signing key are compromised.
- **Remediation:** Exclude `.secret_key` from exports. Consider excluding `users.yaml` or at least stripping password hashes from the export.

### F12 — `|safe` Filter Used with User-Controllable Data
- **Severity:** LOW
- **Location:** `src/templates/live_content.html` line 633
- **Impact:** The `|safe` filter is used to render `constraints.get('scoring_format')` into JavaScript. Since this value comes from `constraints.yaml` which is controlled by authenticated organizers (not public users), the risk is limited to self-XSS. However, the pattern is fragile — if the scoring_format value is ever populated from user input without validation, it becomes exploitable.
- **Remediation:** Use `{{ constraints.get('scoring_format', 'best_of_3') | tojson }}` instead of manual string quoting with `|safe`. The `tojson` filter properly escapes for JavaScript context.

### F13 — ZIP Bomb / Decompression Bomb Risk
- **Severity:** LOW
- **Location:** `src/app.py` lines 4339–4386 (tournament import), lines 4434–4538 (user import), lines 4586–4647 (admin import)
- **Impact:** While file size is checked before decompression for user imports (`MAX_UPLOAD_SIZE`), the tournament import endpoint (`api_import_tournament`, line 4339) does NOT check file size before reading into memory. The admin import checks size but does not validate the total uncompressed size. A crafted ZIP with high compression ratio could exhaust server memory.
- **Remediation:** Check `file.content_length` or read with a size limit. For ZIP extraction, validate total uncompressed size against `MAX_UNCOMPRESSED_SIZE` before extracting.

### F14 — In-Memory Rate Limiting Not Shared Across Workers
- **Severity:** LOW
- **Location:** `src/app.py` lines 88–89 (`_rate_limit_store = {}`)
- **Impact:** The rate limiting store is a Python dictionary in process memory. With gunicorn configured with `--threads 4` (startup.sh line 34), this works within a single process but would not work if multiple workers are used. An attacker could bypass rate limits by hitting different workers.
- **Remediation:** Acceptable for the current single-worker deployment. If scaling to multiple workers, switch to Redis-based rate limiting or use `Flask-Limiter` with a shared backend.

### F15 — No `HttpOnly` / `Secure` / `SameSite` Cookie Configuration
- **Severity:** LOW
- **Location:** `src/app.py` (Flask session configuration, lines 47–48)
- **Impact:** Flask defaults `SESSION_COOKIE_HTTPONLY=True` which is good, but `SESSION_COOKIE_SECURE` defaults to `False` (cookies sent over HTTP) and `SESSION_COOKIE_SAMESITE` defaults to `None` in older Flask versions. In production on Azure HTTPS, cookies should be marked `Secure` and `SameSite=Lax`.
- **Remediation:** Add:
  ```python
  app.config['SESSION_COOKIE_SECURE'] = True
  app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
  ```

### F16 — Open User Registration (No Invite/Approval)
- **Severity:** LOW
- **Location:** `src/app.py` lines 1227–1246 (register route)
- **Impact:** Anyone can create an account and start creating tournaments. While each user's data is isolated, this consumes server storage and could be abused for resource exhaustion.
- **Remediation:** Consider adding an invite code, admin approval, or registration toggle (environment variable `REGISTRATION_ENABLED`).

### F17 — Error Messages Leak Internal Paths
- **Severity:** LOW
- **Location:** `src/app.py` lines 3079–3080 (`error = f"Error generating schedule: {str(e)}"`)
- **Impact:** Exception messages are rendered to the user in the template, potentially exposing internal file paths, Python stack trace details, or library version information.
- **Remediation:** Log the full exception server-side and show a generic error message to the user.

---

## Positive Security Observations

1. **✅ YAML Deserialization:** All YAML loading uses `yaml.safe_load()` — no unsafe deserialization found.
2. **✅ Password Hashing:** Uses `werkzeug.security.generate_password_hash` / `check_password_hash` (bcrypt-based).
3. **✅ Backup API Key Comparison:** Uses `hmac.compare_digest()` for timing-safe comparison (line 188).
4. **✅ Path Traversal Guards:** `_resolve_public_tournament_dir()` checks for `..`, `/`, `\\` in username/slug.
5. **✅ File Upload Validation:** Logo and award uploads validate against `ALLOWED_LOGO_EXTENSIONS` allowlist.
6. **✅ ZIP Import Sanitization:** ZIP imports check for path traversal (`..`) and filter against `ALLOWED_IMPORT_NAMES`.
7. **✅ User Data Isolation:** Per-user directory structure under `USERS_DIR` with session-based access.
8. **✅ File Locking:** Uses `filelock.FileLock` for concurrent access protection.

---

## Priority Remediation Roadmap

| Priority | Finding | Effort |
|----------|---------|--------|
| P0 | F03 — Path traversal in award image | 5 min |
| P0 | F04 — Path traversal in logo endpoint | 5 min |
| P1 | F01 — Add CSRF protection | 2-4 hrs |
| P1 | F02 — Add `@login_required` to all routes | 30 min |
| P1 | F09 — Disable debug mode | 2 min |
| P2 | F06 — Add security headers | 15 min |
| P2 | F05 — Reduce session lifetime | 2 min |
| P2 | F07 — Strengthen password policy | 15 min |
| P2 | F08 — Login rate limiting | 30 min |
| P2 | F10 — Protect secret key from export | 10 min |
| P2 | F15 — Secure cookie flags | 5 min |
| P3 | F11 — Exclude sensitive data from exports | 15 min |
| P3 | F12 — Fix `|safe` usage | 5 min |
| P3 | F13 — ZIP bomb protection | 15 min |
| P3 | F16 — Registration controls | 30 min |
| P3 | F17 — Sanitize error messages | 15 min |
