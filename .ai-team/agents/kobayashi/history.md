# Kobayashi — History

## Project Context
- **Project:** Python Flask tournament scheduling and management web application
- **Stack:** Python 3.11+, Flask, Jinja2, pandas, numpy, OR-Tools CP-SAT, PyYAML, pytest
- **Owner:** Luca Bolognese
- **Joined:** 2026-02-21

## Learnings
- **Architecture:** Multi-user Flask app with per-user file-based storage under `data/users/{username}/tournaments/{slug}/`. No database — all state in YAML/CSV files.
- **Auth:** werkzeug password hashing (bcrypt), Flask session-based auth, `@login_required` decorator defined but inconsistently applied. `before_request` hook provides partial auth gating.
- **Key files:** `src/app.py` (~4815 lines, monolithic), `src/core/` (business logic), `scripts/backup.py` + `scripts/restore.py` (admin backup via API key), `deploy.ps1` (Azure deployment), `startup.sh` (gunicorn).
- **Security positives:** `yaml.safe_load` everywhere, HMAC backup key comparison, path traversal checks in `_resolve_public_tournament_dir`, ZIP import name filtering.
- **Security gaps found:** No CSRF, ~30 routes missing `@login_required`, path traversal in `/api/awards/image/<filename>` and `/api/logo`, debug=True in production entry point, 10-year session lifetime, no security headers, weak password policy (4 chars), no login brute-force protection.
- **Audit report:** Written to `.squad/decisions/inbox/kobayashi-security-audit.md` on 2025-07-22.
