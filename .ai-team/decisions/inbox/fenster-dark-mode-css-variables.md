### Dark mode uses CSS custom properties with [data-theme="dark"] selector
**By:** Fenster
**Date:** 2026-02-14
**What:** Dark mode is implemented purely client-side using CSS custom properties. `:root` defines light theme colors, `[data-theme="dark"]` overrides them. A `<script>` in `<head>` applies the saved theme from `localStorage` before rendering to prevent FOUC. The toggle button in the navbar switches between 🌙 (light) and ☀️ (dark). Any new CSS that introduces hardcoded colors (e.g., `background: #fef2f2`) needs a corresponding `[data-theme="dark"]` override in `style.css`.
**Why:** CSS variables allow the entire app to theme-switch without JS DOM manipulation per element. The `<head>` script prevents a white flash on dark-mode page loads. All agents adding new UI components with hardcoded colors must add dark overrides or the dark theme will have visual inconsistencies.
