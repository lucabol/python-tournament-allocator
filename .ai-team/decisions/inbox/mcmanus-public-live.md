# Public Live Tournament Routes

**By:** McManus
**Date:** 2026-02-12

## Decision

Added public (unauthenticated) routes for spectators to view live tournament data at `/live/<username>/<slug>`, with matching API endpoints for partial HTML and SSE streaming.

## What Changed

- **`src/app.py`**: Added `_resolve_public_tournament_dir()` helper, 3 public route handlers (`public_live`, `api_public_live_html`, `api_public_live_stream`), updated `before_request` whitelist, added `public_mode` flag to existing `/live` route, added `share_url` to `/tracking` template context.
- **No new files created** — reuses existing `live.html` and `live_content.html` templates with the `public_mode` flag for conditional rendering.

## Why

- Spectators and players need to follow a tournament in real time without needing an account.
- URL pattern `/<username>/<slug>` is simple, shareable, and bookmarkable.
- Path validation mirrors the existing `api_delete_tournament` pattern to prevent traversal attacks.
- The SSE stream builds file paths directly to avoid coupling to the auth-gated `g.data_dir` flow.

## Impact

- **Security**: Read-only access only. No writes. Path traversal blocked by validation.
- **Auth**: Three new endpoints bypass `before_request` auth check. No session or login required.
- **Templates**: `public_mode` variable available in `live.html` — Fenster/Hockney can use it to hide nav, adjust SSE URLs, etc.
- **Tests**: 228 existing tests pass. New route tests to be written by Hockney.
