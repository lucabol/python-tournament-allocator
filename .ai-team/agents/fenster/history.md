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

📌 **Team update (2026-02-16):** Player score reporting Phase 1 implemented with structured data submission. See decisions.md for details. — decided by Verbal, McManus, Fenster

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

### 2026-02-14: Dashboard QR code fixed
- **Problem**: Dashboard (`index.html`) QR code was pointing to the Dashboard page itself (`window.location.href`), not the Live page.
- **Fix**: Changed QR code generation to use the same URL construction as the `copyLiveLink()` function: `window.location.origin + '{{ url_for("live") }}'`. Now both Dashboard and Live page QR codes point to the Live page.
- **Pattern**: When QR codes should share the same target across multiple pages, construct URL explicitly using `url_for()` in Jinja rather than relying on `window.location.href`.

### 2026-02-14: Dashboard QR code now includes user/tournament parameters
- **Problem**: Dashboard QR code was generating `/live` without username and tournament slug, while Live page correctly used full URL (`/live/username/slug`).
- **Fix**: Changed both QR code generation and `copyLiveLink()` to use `url_for("public_live", username=current_user, slug=active_tournament)` instead of `url_for("live")`. This matches the pattern used in tracking.html (line 2416 in app.py).
- **Pattern**: Public live URLs require username and slug parameters. Always use `url_for("public_live", username=..., slug=...)` for shareable links, not `url_for("live")`. Context processor provides `current_user` and `active_tournament` to all templates.

### 2026-02-14: Player score reporting UI (Phase 1)
- **What**: Built frontend for player-submitted match results. Players on Live page see a "📝 Report" button on each non-completed match card in the Full Schedule section. Clicking opens an inline score entry form (adapts to single_set vs best_of_3 based on constraints). Form posts to `/api/report-result/<username>/<slug>` (or `/api/report-result` for authenticated). Client-side localStorage tracks submitted match_keys to prevent double-submission (UX courtesy, not security).
- **Organizer view**: `tracking.html` shows pending results as badges ("📩 21-15 reported") on match cells. Clicking the badge auto-fills score inputs and saves via existing `/api/results/pool` endpoint, then dismisses the pending result. "✕" button dismisses without applying. If 3+ pending results exist, a yellow notification banner appears at top of page.
- **Template changes**: `live_content.html` (added report button + inline form + JS), `tracking.html` (added pending badges + accept/dismiss handlers + notification banner), both use `pending_results` context var (McManus to add).
- **CSS additions**: `.btn-report-score`, `.report-score-form`, `.report-form-*` classes in `live.css` (green button, gray form with mobile-friendly inputs). `.pending-badge`, `.pending-dismiss`, `.pending-notification` classes in `style.css` (green accept, red dismiss, yellow banner).
- **API expectations**: `/api/report-result/<username>/<slug>` (POST, accepts `{match_key, team1, team2, pool, sets}`), `/api/pending-results` (GET, returns `{pending_results: {match_key: {sets, timestamp}}}`), `/api/dismiss-result` (POST, accepts `{match_key}`). Backend needs to implement these endpoints and pass `pending_results` dict to `tracking()` route.
- **Mobile patterns**: Form uses `inputmode="numeric"` on score inputs, 44px touch targets on buttons. Report button is small but tappable (32px min-height). Badge/dismiss buttons stack in mobile meta row.

### 2026-02-19: Team Registration Frontend
- **What**: Built complete registration UI across 4 frontend tasks: (1) Created `team_register.html` — standalone public form with tournament branding, status badge, pool list, AJAX submission, mobile-optimized. (2) Updated `teams.html` with Registration section showing Open/Close toggle, status, registration count, and Unassigned Teams grid showing registered teams awaiting assignment. (3) Implemented HTML5 drag-and-drop from unassigned team cards to pool cards with visual feedback (`.drag-over` state, opacity on dragging), plus fallback dropdown selector. (4) Added all CSS for registration page styling, unassigned teams grid, drag states, toggle buttons, dark theme support.
- **UI patterns**: Toggle buttons use `.btn-toggle-on` / `.btn-toggle-off` classes with colored borders and indicators (● for open, ○ for closed). Registration section uses gradient background matching public form. Unassigned team cards show team name, email, phone, registration date, edit/delete buttons, and dropdown pool selector. Draggable cards have `cursor: move`, show `.dragging` state (50% opacity, dashed border), drop zones show `.drag-over` state (dashed primary border, subtle background, shadow ring).
- **Template structure**: `team_register.html` is a standalone page (no base.html extension) with inline CSS for portability — gradient header with logo, tournament meta, status badge, pool tags, form with required/optional labels, success/error messaging via AJAX, responsive down to 480px. `teams.html` now has Registration section above "Add New Pool", Unassigned Teams section above Pools grid (only shows if unassigned teams exist), pool cards now have `pool-drop-zone` class and `data-pool-name` attribute for drop handling.
- **JavaScript architecture**: Registration toggle, copy link, edit/delete registration, and assign-to-pool functions all call respective API endpoints with JSON payloads, reload page on success. Drag-and-drop uses vanilla JS: `dragstart` sets `draggedTeam` object and `.dragging` class, `dragover` enables drop with `.drag-over` class, `dragleave` removes class, `drop` calls API and reloads. Dropdown assignment provides non-drag alternative (mobile/accessibility).
- **API endpoints expected**: `/api/registration/toggle` (POST), `/api/registration/edit` (POST with `old_team_name, team_name, email, phone`), `/api/registration/delete` (POST with `team_name`), `/api/assign-from-registration` (POST with `team_name, pool_name`). McManus needs to implement these and pass `registrations` (dict with `{registration_open, teams: [{team_name, email, phone, registered_at, status, assigned_pool}]}`) to teams route.
- **CSS class conventions**: `.registration-section` (gradient bg, white text), `.registration-header` (flexbox with controls), `.btn-toggle` + modifiers (toggle buttons), `.unassigned-teams` (responsive grid), `.unassigned-team-card` (card with drag states), `.pool-drop-zone` + `.drag-over` (drop target states). All classes have dark theme overrides.
- **Mobile considerations**: Unassigned teams grid switches to single column below 768px. Dropdown assignment always visible as drag-and-drop alternative. Touch-friendly 44px+ buttons. Public registration form tested down to 480px with responsive typography and padding.

