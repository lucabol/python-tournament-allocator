# Decision: Use match_code as Bracket Match Key

## Context
Pending score badges (📩) were not appearing on bracket pages (sbracket.html, dbracket.html) even though the backend was correctly passing pending_results.

## Problem
- Live page was submitting scores with match keys like `"Team1_vs_Team2_PoolName"`
- Bracket templates were looking for keys like `"winners_RoundName_MatchNumber"`
- These formats didn't match, so pending results were never displayed

## Solution
Use the `match_code` field (e.g., "W1-M1", "L2-M3", "GF") as the canonical match key for all bracket matches.

### Changes Made
1. **live_content.html**: When generating match_key for bracket matches, use `match.match_code` instead of team-based key
2. **sbracket.html**: Changed from `"winners_" ~ round_name ~ "_" ~ match.match_number` to `match.get('match_code', '')`
3. **dbracket.html**: Same change for winners/losers brackets, grand final, and bracket reset matches

## Benefits
- Simpler: match_code is already unique and present in all match objects
- Consistent: same key used in schedule, live page, and bracket displays
- Future-proof: works for single/double elimination, gold/silver brackets, all special matches

## Impact
Existing pending_results.yaml files with old key format won't match. This is acceptable since pending results are temporary and will be resolved/dismissed naturally.
