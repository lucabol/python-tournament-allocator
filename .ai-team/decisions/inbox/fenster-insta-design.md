### Instagram summary page design: dark gradient card with inline styles
**By:** Fenster
**Date:** 2026-02-13
**What:** The Insta page (`insta.html`) uses a self-contained inline `<style>` block rather than adding to `style.css`. The card is a 480px-max dark gradient (purple → blue) designed for phone screenshots. All CSS classes are prefixed with `insta-` to avoid collisions. The template reuses `_get_live_data()` for its context, keeping it consistent with the live page data.
**Why:** Inline styles keep the page self-contained and avoid bloating the shared stylesheet with single-use classes. The `insta-` prefix prevents any accidental cascade into other pages. Using `_get_live_data()` means the Insta page always shows the same data as the live page — no drift, no separate data pipeline.
**Affected files:** `src/templates/insta.html` (new), `src/templates/base.html` (nav link added)
