# Debug Logging for Bracket Pending Score Badges

## Context
User reported that pending score badges (📩) are not appearing on bracket pages even though:
- Backend routes pass `pending_results` to templates
- Templates check for pending results with correct match_code keys
- JavaScript functions for accept/dismiss exist

## Investigation
Added comprehensive debug logging to diagnose the issue:

1. **Console Logging**: Added JavaScript console.log statements to both sbracket.html and dbracket.html to output:
   - The entire `pending_results` dictionary
   - `current_user` and `active_tournament` values
   - This will show if data is reaching the browser

2. **HTML Comments**: Added HTML debug comments in template loops to show:
   - Each match's `match_code` value
   - Whether a pending result was found for that match
   - Labeled by bracket type (winners/losers/silver/grand final)

3. **Key Verifications**:
   - Confirmed routes load and pass `pending_results` correctly
   - Confirmed `current_user` and `active_tournament` are available via context processor
   - Confirmed templates use correct match_code field

## Next Steps
User or developer should:
1. Navigate to bracket pages in browser
2. Open browser console (F12) to see debug output
3. View page source to see HTML debug comments
4. Check if pending_results is empty or if match_codes don't match
5. Remove debug code once issue is identified

## Technical Details
- Match keys from Live page use `match_code` format (e.g., "W1-M1", "L2-M3", "GF")
- pending_results.yaml stores this as the match_key
- Templates correctly look up by match.get('match_code', '')
- Debug output will reveal if there's a mismatch or if data isn't loading

## Files Modified
- src/templates/sbracket.html - Added console.log and HTML comments
- src/templates/dbracket.html - Added console.log and HTML comments
