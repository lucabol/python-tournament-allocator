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
