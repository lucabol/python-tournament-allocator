# History Archive — Fenster

Archived entries from 2026-02-11 to 2026-02-13 (before 2 weeks).

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

### 2026-02-13: Awards feature frontend (duplicate session)
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
