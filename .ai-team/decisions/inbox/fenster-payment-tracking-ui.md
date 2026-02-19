# Payment Tracking UI Design

**Date:** 2025-01-XX  
**Author:** Fenster (Frontend Developer)  
**Status:** Implemented

## Decision

Implemented payment tracking UI with the following design approach:

### 1. Payment Checkbox Placement
- Added checkbox to the **left** of each team name in pool cards
- Used a subtle design that only shows the 💰 emoji when checked
- Checkbox integrates smoothly with existing team name input layout via flex wrapper

### 2. Unpaid Teams Button
- Placed button in the **registration controls section** alongside "Copy Link"
- Used 💰 emoji for visual consistency with the paid checkbox indicator
- Button labeled "Unpaid Teams" for clarity

### 3. Modal Design
- Reused existing `.modal-overlay` pattern for consistency
- Grid layout for unpaid team items (1 column, responsive)
- Each unpaid team card shows:
  - Team name with 🏐 emoji (visual consistency)
  - Email with ✉️ emoji (easy to spot for contact info)
  - Clean card-based layout with borders

### 4. Visual Feedback
- Checkboxes use standard form styling with green success color when checked
- Modal displays "All teams have paid!" success message when list is empty
- Loading and error states handled gracefully

## Rationale

- **Checkbox position**: Left side keeps it close to team identity without interfering with name editing
- **Emoji indicators**: Provides visual cues without adding text clutter (💰 for paid, 🏐 for team, ✉️ for email)
- **Modal pattern reuse**: Maintains consistency with existing help/info modals in the app
- **Registration section placement**: Logical location since payment is part of registration workflow

## Technical Notes

- No backend API endpoints implemented yet (expects `/api/toggle-paid` and `/api/unpaid-teams`)
- CSS uses existing design tokens (colors, spacing, shadows) for consistency
- Dark theme support included
- Team wrapper uses flexbox to accommodate checkbox without disrupting existing inline edit functionality
