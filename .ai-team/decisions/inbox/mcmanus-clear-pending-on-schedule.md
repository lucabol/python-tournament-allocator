# Clear Pending Results on Schedule Generation

**Decision:** When generating a new schedule, clear the `pending_results.yaml` file along with other tournament state.

**Context:** The pending results file tracks match scores that have been reported but not yet confirmed. When a new schedule is generated, these pending results become stale because they reference matches from the old schedule.

**Implementation:**
- Added `save_pending_results([])` call in the `/schedule` route after `save_results()` 
- This ensures pending results are cleared before the success response is returned
- Follows the same pattern as clearing pool play and bracket results

**Why Now:**
Users were seeing ghost "pending" indicators in the UI after regenerating schedules, because the old pending results were never cleared.

**Related Files:**
- `src/app.py` - Lines 2458-2468 in schedule generation route
