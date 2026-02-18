# Allow Multiple Score Submissions (Last-Wins Logic)

**Date:** 2025-01-28  
**Author:** McManus (Backend Dev)  
**Context:** Issue with "already reported" messages persisting after schedule regeneration

## Decision

Changed score submission behavior from "reject duplicates" to "last submission wins":

1. **Removed client-side localStorage check** - Users can now submit scores multiple times for the same match
2. **Updated server-side logic** - Instead of rejecting duplicate submissions with 409 error, the server now updates the existing pending result with the latest submission

## Rationale

The original implementation had two layers of duplicate prevention:
- Client-side: localStorage tracking of submitted matches (persisted across schedule regenerations)
- Server-side: Rejection of duplicate pending reports with 409 error

This caused issues when schedules were regenerated:
- Server correctly cleared `pending_results.yaml`
- But client localStorage still had old match keys marked as "reported"
- Users saw "already reported" alerts even though pending results were cleared

User confirmed that allowing multiple submissions is acceptable and simplifies the workflow. This eliminates the stale localStorage problem entirely.

## Implementation

**File:** `src/templates/live_content.html`
- Removed localStorage check before showing report form (lines 633-637)
- Removed `markAsReported()` call after successful submission (line 727)

**File:** `src/app.py`
- Changed duplicate detection from error response to update logic (lines 2694-2715)
- Now uses `existing_idx` to find and update existing pending results
- Keeps the timestamp updated to reflect latest submission

## Impact

- Players can re-report scores if they made a mistake
- Organizers see only the latest submission in pending results
- No stale localStorage issues after schedule regeneration
- Simpler mental model: "last report wins"
