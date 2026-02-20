# Session: 2026-02-13 — Instagram Bracket & Print Page Removal

**Requested by:** Luca Bolognese

## Summary

Completed feature update to add bracket results to the Instagram page and remove the print view route. Work spanned 3 agents:

- **Fenster** added Gold/Silver bracket display sections to `insta.html`, deleted `print.html` template, removed Print nav link from `base.html`, updated `index.html` broken references
- **McManus** removed `print_view()` route, `update_print_settings()` API endpoint, `save_print_settings()` helper (kept `load_print_settings()` for internal use by `_get_live_data()`)
- **Hockney** removed print test reference from `TestEnhancedDashboard`, added `test_insta_page_shows_bracket_data` test to verify bracket rendering on insta page

## Key Decisions

1. **Bracket layout on insta page**: Compact inline format (`Team A v Team B` with winner highlighted green, scores as `X / Y`). Byes skipped, no match codes.
2. **Print page deprecation**: Full removal — route, template, nav link gone. No backward compatibility needed.
3. **print_settings.yaml lifecycle**: Removed API/UI surface, but kept data file references in migration/export for backward compatibility with existing tournaments.

## Results

- All 268 tests pass
- Commit: 6cb665c
- No test failures or regressions
- Instagram page now displays Gold/Silver bracket results alongside pools and awards
