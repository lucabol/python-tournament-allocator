### Tournament page button colors use existing CSS class modifiers
**By:** Fenster
**Date:** 2026-02-14
**What:** Changed button colors on the Tournaments page using existing `.btn-*` CSS classes rather than inline styles: Switch → `.btn-success` (green), Clone → `.btn-primary` (blue), Delete → `.btn-danger` (red, unchanged). No new CSS was added.
**Why:** The project already has `.btn-success`, `.btn-primary`, and `.btn-danger` classes in `style.css` with proper hover states and dark mode support. Reusing existing classes is more maintainable than inline styles and keeps the template consistent with the rest of the app.
**Affected files:** `src/templates/tournaments.html`
