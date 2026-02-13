### 2026-02-14: Clear result buttons removed from all result tracking UIs

**By:** Fenster

**What:** Removed all "Clear" (✕) buttons and associated JavaScript functions (`clearResult`, `clearBracketResult`) from pool play tracking (`tracking.html`), single elimination brackets (`sbracket.html`), and double elimination brackets (`dbracket.html`). Users now clear match results by deleting both score values in the input boxes and letting the auto-save mechanism trigger a clearing action.

**Why:** Luca requested removal — the explicit clear button added visual clutter, and the natural user workflow for clearing a result is to delete the scores anyway. The deletion workflow is more intuitive than having a separate button, and it reduces the number of UI actions on completed matches. The auto-save debounce already handles the update flow seamlessly when both scores are cleared.

**Impact:** The backend `/api/clear-result` endpoint still exists but is no longer called from the frontend. The score input fields remain fully functional with 500ms debounced auto-save. Templates affected: `tracking.html`, `sbracket.html`, `dbracket.html`.
