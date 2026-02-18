# Decision: Bracket Pending Score Badge Implementation

**Date:** 2025-01-XX  
**Author:** Fenster (Frontend Dev)  
**Context:** Bug fix for missing pending score indicators on bracket pages

## Problem
Player-reported scores from the Live page generated pending results, but these weren't visible on the Brackets tabs. Organizers had to check the Pools tracking page to see pending scores, creating workflow friction.

## Solution
Extended the existing pending score badge pattern from `tracking.html` to both bracket templates:
- `sbracket.html` (single elimination)
- `dbracket.html` (double elimination)

### Implementation Details

**Match Key Format for Brackets:**
- Regular rounds: `{bracket_type}_{round_name}_{match_number}`
- Grand Finals: `{bracket_type}_Grand Final_1`
- Bracket Resets: `{bracket_type}_Bracket Reset_1`

**Examples:**
- `winners_Quarterfinal_1`
- `losers_Round 2_3`
- `grand_final_Grand Final_1`
- `silver_grand_final_Grand Final_1`

**Badge Placement:**
Pending badges appear in the match header alongside playable/completed indicators, only when:
1. A pending result exists for that match key
2. The match has not yet been completed

**JavaScript Functions:**
Added `acceptPendingScore()` and `dismissPendingScore()` functions to both templates, matching the tracking.html implementation.

## Technical Notes
- Brackets use different match keys than pool matches (bracket type + round + number vs team names + pool)
- The `data-match-key` attribute was added to all bracket match divs for JavaScript to reference
- Both desktop and mobile layouts supported (mobile uses `.m-match-item` selector)
- Handles all bracket types: winners, losers, silver, grand finals, and bracket resets

## Files Modified
- `src/app.py`: Added pending_results loading to `/sbracket` and `/dbracket` routes
- `src/templates/sbracket.html`: Added badges to gold and silver bracket matches
- `src/templates/dbracket.html`: Added badges to winners, losers, grand finals, and bracket resets
