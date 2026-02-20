### 2026-02-21: Registration tab added to main navigation

**By:** Fenster
**What:** Added "Registration" as a navigation tab after "Live" in base.html. Tab links to the public team registration page for the current user's active tournament.
**Why:** Requested by user for easier access to the registration page. Placing it after Live follows the user-facing flow: spectators use Live to watch, then Registration to sign up. Conditional rendering matches the Live tab pattern (only shows when active_tournament exists).
