### 2026-02-21: Standardized page header structure

**By:** Fenster

**What:** All page templates now use consistent `<div class="page-header">` wrapper with optional `<div class="page-header-actions">` for buttons/controls.

**Why:** Previously, some pages used bare `<h1>` tags while others used `page-header` div, creating visual inconsistency. The new pattern ensures:
- Consistent spacing and alignment across all pages
- Predictable flexbox layout for headers with action buttons
- Clean separation of page title from page actions
- Better responsive behavior with flex-wrap

**Pattern:**
```html
<div class="page-header">
    <h1>Page Title</h1>
    <div class="page-header-actions">
        <button class="btn btn-sm">Action</button>
    </div>
</div>
```

For pages without actions, just wrap the h1:
```html
<div class="page-header">
    <h1>Page Title</h1>
</div>
```

**CSS:** `.page-header` uses flexbox with space-between, flex-wrap, and consistent gap. `.page-header-actions` groups action buttons with consistent spacing.
