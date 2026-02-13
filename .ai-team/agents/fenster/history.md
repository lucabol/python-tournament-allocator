# Project Context

- **Owner:** Luca Bolognese (lucabol@microsoft.com)
- **Project:** Python Flask tournament scheduling and management web application
- **Stack:** Python 3.11+, Flask, Jinja2, pandas, numpy, OR-Tools CP-SAT, PyYAML, pytest
- **Created:** 2026-02-11

## Learnings

<!-- Append new learnings below. Each entry is something lasting about the project. -->

- **CSS class patterns**: Buttons use `.btn` + modifier (`.btn-primary`, `.btn-danger`, `.btn-success`, `.btn-secondary`) + size (`.btn-sm`, `.btn-xs`, `.btn-lg`). Cards use `.card`, sections use `.section`. Tables use `.data-table`. Inline forms use `.inline-form`. Flash messages use `.alert .alert-{category}`.
- **Template structure**: Pages use `page-header` div with `h1`, flash messages block, then `section` blocks. Forms follow POST-redirect pattern. Delete buttons use `onsubmit="return confirm(...)"`.
- **Navbar**: Uses `.nav-brand` + `.nav-links` with `request.endpoint` checks for active state. Tournament name now shown dynamically in brand area via `tournament_name` context variable.
- **New tournament UI**: Created `tournaments.html` with create form, tournament list table, active badge, switch/delete actions. Added `.active-tournament`, `.badge`, `.badge-active` CSS classes.
- **Public live mode**: `live.html` uses Jinja conditionals (`public_mode`, `public_username`, `public_slug`) to build dynamic AJAX/SSE URLs for public vs authenticated access. URL variables declared at top of `<script>` block, before `DOMContentLoaded`.
- **Share link bar**: `tracking.html` has a `{% if share_url %}` block after the page header showing the live link URL with a clipboard copy button. Uses inline styles for the `.share-link-bar` component.
- **Export/Import pattern**: Hidden file input triggered by visible button, auto-submits on change via `onchange` handler. Confirm dialog before submit, reset input value on cancel. Used in both `index.html` (single tournament) and `tournaments.html` (all tournaments). IDs must be unique across page (`import-all-file`/`import-all-form` for user-level).
- **Admin-only sections**: Use `{% if current_user == 'admin' %}` conditional (context processor provides `current_user`). Site-level admin actions in `tournaments.html` use `section-danger-zone` CSS class (red border + light red background) and a `prompt()`-based confirmation requiring the user to type "REPLACE" — stronger than a simple `confirm()`. IDs: `import-site-file`/`import-site-form`.
- **Danger zone pattern**: `.section-danger-zone` class in `style.css` — red border + `#fef2f2` background, stacks with `.section`. Reusable for any destructive admin UI.

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

### 2026-02-13: Awards feature frontend
- **What**: Created `awards.html` template with add-award form (name/player inputs + image picker grid), current awards list with delete buttons, and all JS for API interaction. Added Awards nav link in `base.html` between Print and Live. Added read-only Awards section to `live_content.html` as a collapsible `<details>` block. Created 10 SVG award icons in `src/static/awards/` (trophy, medals, star, crown, flame, volleyball, target, thumbs-up). Added CSS classes: `.awards-grid`, `.award-card`, `.award-card-img`, `.award-card-info`, `.image-picker`, `.image-picker-item`, `.award-form`.
- **Image source pattern**: Images starting with `custom-` load from `/api/awards/image/{filename}`, others from `/static/awards/{filename}`. This dual-source pattern is used in both `awards.html` and `live_content.html`.
- **API endpoints expected by frontend**: `api_awards_samples` (GET), `api_awards_add` (POST), `api_awards_delete` (POST), `api_awards_upload_image` (POST), `api_awards_image` (GET, takes `filename` param). McManus needs to implement these in `app.py`.
- **Template variable**: `awards` — list of `[{id, name, player, image}, ...]`. Needs to be injected by the route handler and context processor (for live pages).

### 2026-02-13: Instagram-friendly tournament summary page
- **What**: Created `insta.html` — a phone-screenshot-optimized "story card" layout for sharing tournament results on Instagram. Added "Insta" nav link in `base.html` between Awards and Live. Route (`/insta`) and endpoint whitelisting were already in place; only the template was missing.
- **Design approach**: Self-contained inline `<style>` block (same pattern as `print.html`). Dark gradient background (deep purple to midnight blue), white/light text, max-width 480px centered. All styles use `insta-` prefix to avoid collisions with existing CSS.
- **Sections**: Tournament header (logo, club, name, date), Champions (gold/silver with gradient text and emoji), Pool Standings (compact tables with green advancing highlight), Awards (grid of small cards with icons), footer watermark.
- **Visual patterns**: Gradient text for title and gold champion name (`background-clip: text`), semi-transparent cards and borders for glassy feel, `radial-gradient` overlay for subtle light effects, green accent for advancing teams with marker.
- **Data source**: Uses `_get_live_data()` — same context as the live page. Template variables: `constraints`, `bracket_data`, `silver_bracket_data`, `standings`, `pools`, `awards`.

### 2026-02-13: Instagram page session completed
- **Session overview**: McManus added `/insta` route reusing `_get_live_data()`, Fenster created `insta.html` template with vibrant gradient card layout and added nav link, Hockney wrote 4 tests in `TestInstaPage` class.
- **Test results**: All 267 tests pass.
- **Commit**: 04da995 (pushed)
- **Design pattern**: Inline styles + `insta-` prefixed classes follow the `print.html` precedent for self-contained pages. This pattern is now established for future single-page-layout features.

### 2026-02-13: Bracket results added to insta.html + Print page removed
- **What**: Added condensed bracket results section to `insta.html` between Pool Standings and Awards. Covers Gold Bracket (winners bracket, losers bracket, grand final, bracket reset) and Silver Bracket (same structure). Deleted `print.html` template, removed Print nav link from `base.html`, and replaced broken `print_view` references in `index.html` with links to the Insta page.
- **Bracket display pattern**: Compact inline layout — each match is `Team A v Team B` with winner highlighted in green (`insta-winner` class). Scores shown as `X / Y` on the right. Byes are skipped. No match codes or playability indicators. Uses `insta-bracket-match`, `insta-bracket-round`, `insta-bracket-sub`, `insta-grand-final`, `insta-match-done`, `insta-winner`, `insta-vs`, `insta-score` CSS classes.
- **Print page removal**: `print.html` was deleted, its nav link removed from `base.html`, and its `url_for('print_view')` references in `index.html` were updated to point to `url_for('insta')`. The `print_view` route had already been removed from `app.py` by another agent.
- **Test results**: All 268 tests pass.

### 2026-02-14: Hamburger menu, dark mode, clear result button
- **Hamburger menu**: Added a `☰` hamburger button (`.hamburger`) visible only below 768px. On click, toggles `.nav-open` on `.nav-links` via inline JS. Nav links render as a vertical dropdown on mobile. Added `.nav-right-controls` wrapper to group theme toggle + hamburger. Desktop layout untouched — hamburger has `display: none` by default.
- **Dark mode**: Defined `[data-theme="dark"]` CSS custom properties overriding all major colors (bg, card, text, borders, shadows). Added 🌙/☀️ toggle button (`.theme-toggle`) in navbar. Theme persists in `localStorage`. An inline `<script>` in `<head>` applies the saved theme before rendering to prevent FOUC. Dark overrides added for danger zones, completed matches, alerts, standings, score inputs, bracket matches, and select arrows.
- **Clear result button**: Added `✕` button (`.btn-clear-result`) on each completed match in `tracking.html` (both desktop table and mobile accordion). Calls `clearResult(matchKey)` JS function which POSTs to `/api/clear-result` and reloads on success. McManus implemented the `/api/clear-result` endpoint accepting `{match_key: string}` and removing the result from `results.yaml`. Hockney wrote 4 tests in `TestClearResult` class covering success, nonexistent key, missing key, and tracking page reflection.
- **CSS classes added**: `.theme-toggle`, `.nav-right-controls`, `.hamburger`, `.hamburger span`, `.hamburger.open`, `.btn-clear-result`, `@media (max-width: 768px)` hamburger block, `[data-theme="dark"]` block with ~15 overrides.
- **Test results**: All 276 tests pass.
- **Feature status**: Complete. Button only shows on completed matches, has confirm dialog, subtle styling (red on hover), works in both desktop and mobile views.

### 2026-02-14: QR code replaces live link on dashboard
- **What**: Removed the inline `.share-link-bar` block from `tracking.html` (the `{% if share_url %}` section showing the live URL + copy button). Replaced the "📡 Copy Live Link" button in the Quick Actions bar of `index.html` with a client-side QR code rendered via `qrcode-generator@1.4.4` CDN library. The QR code encodes the live page URL, displays at ~100×100px in a white-background rounded container, and has a "📡 Live Page" label beneath it. Clicking the QR code copies the live URL to clipboard (reuses `copyLiveLink()` logic). Updated the test assertion in `test_dashboard_shows_export_bar` from `Copy Live Link` to `Live Page`.
- **QR code approach**: Uses `qrcode-generator` (~4KB) loaded from jsdelivr CDN. Generates an inline SVG (`qr.createSvgTag`) — works in both light and dark mode since the container has an explicit white background. The SVG is generated immediately on page load via an IIFE.
- **Dark mode**: The QR container uses `background:#fff` so the QR code is always black-on-white regardless of theme. The label uses `var(--text-muted)` to adapt to theme.
- **Test results**: All 276 tests pass.
