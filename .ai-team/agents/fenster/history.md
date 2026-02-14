# Project Context

- **Owner:** Luca Bolognese (lucabol@microsoft.com)
- **Project:** Python Flask tournament scheduling and management web application
- **Stack:** Python 3.11+, Flask, Jinja2, pandas, numpy, OR-Tools CP-SAT, PyYAML, pytest
- **Created:** 2026-02-11

## Core Context

Fenster is responsible for all Jinja2 templates, CSS styling, and client-side JavaScript UI patterns in the Flask application. Key patterns maintained across all templates:

- **CSS class patterns**: Buttons use `.btn` + modifier (`.btn-primary`, `.btn-danger`, `.btn-success`, `.btn-secondary`) + size (`.btn-sm`, `.btn-xs`, `.btn-lg`). Cards use `.card`, sections use `.section`. Tables use `.data-table`. Inline forms use `.inline-form`. Flash messages use `.alert .alert-{category}`.
- **Template structure**: Pages use `page-header` div with `h1`, flash messages block, then `section` blocks. Forms follow POST-redirect pattern. Delete buttons use `onsubmit="return confirm(...)"`.
- **Navbar**: Uses `.nav-brand` + `.nav-links` with `request.endpoint` checks for active state. Tournament name shown dynamically in brand area via `tournament_name` context variable. Includes 🌙/☀️ dark mode toggle and hamburger menu (mobile).
- **New tournament UI**: `tournaments.html` with create form, tournament list table, active badge, switch/delete actions. Added `.active-tournament`, `.badge`, `.badge-active` CSS classes. Button colors use existing `.btn-success`, `.btn-primary`, `.btn-danger` classes.
- **Public live mode**: `live.html` uses Jinja conditionals (`public_mode`, `public_username`, `public_slug`) to build dynamic AJAX/SSE URLs for public vs authenticated access. URL variables declared at top of `<script>` block, before `DOMContentLoaded`.
- **Export/Import pattern**: Hidden file input triggered by visible button, auto-submits on change via `onchange` handler. Confirm dialog before submit, reset input value on cancel. Used in both `index.html` (single tournament) and `tournaments.html` (all tournaments). IDs must be unique across page.
- **Admin-only sections**: Use `{% if current_user == 'admin' %}` conditional. Site-level admin actions use `section-danger-zone` class (red border, light red background) and `prompt()`-based confirmation requiring typed word (e.g., "REPLACE", "DELETE").
- **Danger zone pattern**: `.section-danger-zone` — red border + `#fef2f2` background, stacks with `.section`. Reusable for destructive admin UI.
- **Dark mode**: Client-side CSS custom properties via `:root` (light theme) and `[data-theme="dark"]` overrides. Theme persists in localStorage. Head script applies before rendering to prevent FOUC. All new UI with hardcoded colors needs dark overrides.
- **Mobile responsive**: Hamburger menu (☰) visible below 768px, toggles `.nav-open` on `.nav-links` for vertical dropdown. QR code rendering for live URL sharing with fallback copy-to-clipboard.

## Learnings

<!-- Append new learnings below. Each entry is something lasting about the project. -->

### 2026-02-13: Awards feature frontend
- **What**: Created `awards.html` template with add-award form (name/player inputs + image picker grid), current awards list with delete buttons, and all JS for API interaction. Added Awards nav link in `base.html` between Print and Live. Added read-only Awards section to `live_content.html` as a collapsible `<details>` block. Created 10 SVG award icons in `src/static/awards/` (trophy, medals, star, crown, flame, volleyball, target, thumbs-up). Added CSS classes: `.awards-grid`, `.award-card`, `.award-card-img`, `.award-card-info`, `.image-picker`, `.image-picker-item`, `.award-form`.
- **Image source pattern**: Images starting with `custom-` load from `/api/awards/image/{filename}`, others from `/static/awards/{filename}`. This dual-source pattern is used in both `awards.html` and `live_content.html`.
- **API endpoints expected by frontend**: `api_awards_samples` (GET), `api_awards_add` (POST), `api_awards_delete` (POST), `api_awards_upload_image` (POST), `api_awards_image` (GET, takes `filename` param). McManus needs to implement these in `app.py`.
- **Template variable**: `awards` — list of `[{id, name, player, image}, ...]`. Needs to be injected by the route handler and context processor (for live pages).

### 2026-02-13: Coordinator fix — hardcoded URLs replaced with url_for()
- **Problem**: Site admin section in `tournaments.html` used hardcoded `/api/export/site` and `/api/import/site` URLs.
- **Fix**: Replaced with `{{ url_for('api_export_site') }}` and `{{ url_for('api_import_site') }}`.
- **Lesson**: Always use `url_for()` in templates — hardcoded paths break if routes are renamed or prefixed.

### 2026-02-13: Delete Account danger zone added to Settings page
- **What**: Added a `section-danger-zone` block at the bottom of `constraints.html` with a "Delete Account" heading, warning text, and a red delete button. The `confirmDeleteAccount()` JS function uses `prompt()` requiring the user to type "DELETE", then POSTs to `{{ url_for('api_delete_account') }}` and redirects on success.
- **Pattern**: Matches the typed-confirmation pattern from the site admin danger zone in `tournaments.html`. Uses `url_for()` for the API URL per established convention.

### 2026-02-13: Show Test Buttons toggle
- **What**: Added a "Show Test Buttons" checkbox to Settings (`constraints.html`) and wrapped Test buttons in `teams.html`, `courts.html`, `tracking.html`, and `dbracket.html` with `{% if show_test_buttons %}`. The `show_test_buttons` variable is injected globally via the context processor (loads from constraints). Default is `False`.
- **Pattern**: Checkbox follows the Silver Bracket checkbox pattern (same CSS class, `updateSetting()` JS call, help tooltip). Context processor injects the value so templates don't need `constraints` passed explicitly.

### 2026-02-13: Instagram-friendly tournament summary page
- **What**: Created `insta.html` — a phone-screenshot-optimized "story card" layout for sharing tournament results on Instagram. Added "Insta" nav link in `base.html` between Awards and Live. Route (`/insta`) and endpoint whitelisting were already in place; only the template was missing.
- **Design approach**: Self-contained inline `<style>` block (same pattern as `print.html`). Dark gradient background (deep purple to midnight blue), white/light text, max-width 480px centered. All styles use `insta-` prefix to avoid collisions with existing CSS.
- **Sections**: Tournament header (logo, club, name, date), Champions (gold/silver with gradient text and emoji), Pool Standings (compact tables with green advancing highlight), Awards (grid of small cards with icons), footer watermark.
- **Visual patterns**: Gradient text for title and gold champion name (`background-clip: text`), semi-transparent cards and borders for glassy feel, `radial-gradient` overlay for subtle light effects, green accent for advancing teams with marker.
- **Data source**: Uses `_get_live_data()` — same context as the live page. Template variables: `constraints`, `bracket_data`, `silver_bracket_data`, `standings`, `pools`, `awards`.

### 2026-02-13: Instagram page session completed

### 2026-02-13: Azure restore script implementation
- **What**: Created `scripts/restore.py` for restoring data to Azure App Service from backup ZIP. Script validates ZIP structure (requires `users.yaml`, `.secret_key`), creates pre-restore backup (calls `backup.py`), stops App Service, uploads ZIP via base64-encoded chunks through `az webapp ssh`, extracts remotely to `/home/data`, validates files, restarts app. Exit codes: 0 (success), 1 (invalid ZIP/Azure CLI), 2 (connection failed), 3 (restore failed), 4 (validation failed).
- **Azure CLI patterns**: Uses `az webapp ssh --command` for remote execution. Binary uploads split into base64 chunks to avoid command length limits. App stop/start via `az webapp stop/start`. Remote validation with `test -f` commands.
- **Safety features**: Pre-restore backup saved to `backups/pre-restore-YYYYMMDD-HHMMSS.zip` (unless `--no-backup`). Typed confirmation prompt (must type "RESTORE"). App Service stopped during restore to prevent corruption. Validation after extraction. Cleanup of temp files.
- **File structure**: Backup restores to `/home/data` on Azure (set via `TOURNAMENT_DATA_DIR` env var in `deploy.ps1`). This directory is persistent across deploys (`/home` mount survives, `/home/site/wwwroot` is replaced).

📌 **Team update (2026-02-14):** Azure backup/restore workflow coordinated with Keaton — backup uses SSH tar streaming; restore uses base64-chunked upload with app stop. See decisions.md for full architecture.
