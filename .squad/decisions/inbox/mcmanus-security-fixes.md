# Decision: Security Fixes for F01, F02, F03

**Author:** McManus (Backend Dev)
**Date:** 2025-07-22
**Status:** Implemented

## Context

Kobayashi's security audit identified 3 HIGH severity findings. These fixes address all three without any user-visible changes.

## Decisions Made

### D1 — CSRF: Global fetch() override instead of per-template changes

**Choice:** Override `window.fetch` in `base.html` to automatically inject `X-CSRFToken` header, plus auto-inject hidden `csrf_token` fields into all forms via DOMContentLoaded.

**Why:** Modifying 8+ templates individually is error-prone and creates maintenance burden. The global override ensures all future fetch() calls and forms are automatically protected.

**Trade-off:** Templates that don't extend `base.html` (e.g., `live.html`, `team_register.html`) don't get the override, but their endpoints are CSRF-exempt anyway since they're public.

### D2 — CSRF Exempt endpoints

**Exempt from CSRF:**
- `public_register` — public team registration, no session
- `api_report_result` — public player score reports, rate-limited
- `api_message` — public player messages from live page
- `api_admin_import` — uses API key auth, not session

**Not exempt:** Login and account registration forms (they extend `base.html` and get CSRF tokens automatically).

### D3 — @login_required as defense-in-depth

Added `@login_required` to all 28 routes from F02, even though `before_request` already redirects unauthenticated users for most page routes. This provides explicit per-route auth that:
- Works independently of the `before_request` hook
- Makes auth requirements visible at the route definition
- Returns proper redirects for API endpoints instead of relying on the hook

### D4 — Path traversal: Simple validation over send_from_directory

**Choice:** Added `if '/' in filename or '\\' in filename or '..' in filename: abort(400)` rather than switching to `send_from_directory()`.

**Why:** Minimal change, matches existing pattern used elsewhere (e.g., tournament slug validation), and the existing `send_file()` call works correctly once the filename is validated.

## Files Changed

- `src/app.py` — CSRFProtect init, 4 CSRF exemptions, 28 @login_required decorators, path traversal fix
- `src/templates/base.html` — CSRF meta tag, fetch override, form auto-inject
- `requirements.txt` — Added Flask-WTF
- `tests/test_app.py` — Disabled CSRF in test fixture
