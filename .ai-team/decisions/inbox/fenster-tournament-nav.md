### Tournament link placement in navbar

**Decision:** "Tournaments" nav link is placed first (before Dashboard) since it's the entry point for selecting which tournament to work on. The nav brand text dynamically shows the active tournament name via the `tournament_name` context variable, falling back to "Tournament Allocator" when none is set.

**Rationale:** Users need to see at a glance which tournament they're working on. Putting the selector first makes it discoverable and the brand text makes it always visible.

**Affected files:** `src/templates/base.html`, `src/static/style.css`
