# Show Test Buttons — Frontend Implementation

**By:** Fenster
**Date:** 2026-02-13

## What
Added a "Show Test Buttons" checkbox to the Settings page (`constraints.html`) and made all Test buttons across 4 templates conditional on this setting.

### Changes
1. **`src/app.py`**: Added `show_test_buttons: False` to `get_default_constraints()`, added save handling in `api_update_settings()`, and injected `show_test_buttons` into the context processor so it's available in all templates.
2. **`src/templates/constraints.html`**: Added checkbox in General Settings section, matching existing checkbox pattern (Silver Bracket), with help tooltip.
3. **`src/templates/teams.html`**: Wrapped Test button with `{% if show_test_buttons %}`.
4. **`src/templates/courts.html`**: Same.
5. **`src/templates/tracking.html`**: Same.
6. **`src/templates/dbracket.html`**: Same.

### Design Decisions
- **Context processor** was used to make `show_test_buttons` available globally, avoiding the need to pass it in every `render_template()` call. The context processor loads constraints once per request (with try/except safety).
- **Default is `False`** — Test buttons are hidden unless explicitly enabled by the user in Settings.
- **JS functions remain in templates** — only the trigger buttons are hidden, not the JavaScript. This is harmless and avoids unnecessary churn.

All 249 tests pass.
