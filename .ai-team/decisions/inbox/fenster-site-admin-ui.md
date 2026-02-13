### Site admin backup/restore UI uses typed-confirmation pattern
**By:** Fenster
**Date:** 2026-02-12
**What:** The site-level import (replace all data) requires the user to type "REPLACE" in a `prompt()` dialog, not just click OK in a `confirm()`. This is a deliberate UX escalation — the action destroys all user data site-wide, so the friction should match the severity. The section is gated behind `{% if current_user == 'admin' %}` and visually distinct with a red danger-zone border.
**Why:** A simple confirm dialog is too easy to click through accidentally. Typing a specific word forces the admin to pause and read. This pattern should be reused for any future site-wide destructive action.
**Affected files:** `src/templates/tournaments.html`, `src/static/style.css`
