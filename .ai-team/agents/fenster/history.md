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
