### show_test_buttons tests written (TestShowTestButtons)
**By:** Hockney
**Date:** 2026-02-13
**What:** Added `TestShowTestButtons` class (5 tests) at the end of `tests/test_app.py`. Tests cover: default False, toggle on via POST, toggle off (unchecked checkbox), teams page hides button by default, teams page shows button when enabled. Tests 1-3 and 5 pass now. Test 4 (`test_teams_page_hides_test_button_by_default`) will pass once Fenster wraps the test button in `{% if show_test_buttons %}` in `teams.html`.
**Why:** Validates the full lifecycle of the `show_test_buttons` constraint — default value, persistence through form toggle, and conditional rendering in templates.
