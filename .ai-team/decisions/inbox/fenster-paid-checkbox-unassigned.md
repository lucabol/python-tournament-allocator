# Decision: Added Paid Checkbox to Unassigned Teams

**Date:** 2025-01-20  
**Made by:** Fenster (Frontend Developer)

## Context
The paid checkbox (💰 indicator) was only available for teams already assigned to pools, but not for unassigned teams in the "Registered Teams" section. This made it impossible for organizers to track payment status until after pool assignment.

## Decision
Added the paid checkbox to unassigned team cards using the same pattern as pool cards:
- Uses the same `togglePaid()` JavaScript function calling `/api/toggle-paid`
- Same visual styling with 💰 indicator
- Checkbox state loaded from `reg.paid` property in registration data
- Placed next to team name for consistent UI across both sections

## Rationale
- Consistent UX across all team displays
- Allows tracking payment status earlier in workflow (before pool assignment)
- Reuses existing backend API and frontend function (no new code needed)
- Maintains visual consistency with pool card styling
