# Registration Link Fix

**Date:** 2025-01-24  
**Agent:** Fenster (Frontend Dev)  
**Status:** Implemented

## Context
The "Copy Link" button on the Teams page needed to generate a public registration link that doesn't require authentication.

## Decision
Updated `copyRegistrationLink()` function in `teams.html` to build the correct public URL:

```javascript
const url = window.location.origin + `/register/${username}/${slug}`;
```

This generates URLs pointing to the `/register/<username>/<slug>` route in Flask, which is public (no `@login_required` decorator) and allows teams to self-register without logging into the tournament organizer's account.

## Rationale
- The public registration route exists specifically for this purpose
- Teams shouldn't need organizer credentials to register
- Direct URL construction ensures no accidental redirection through authenticated routes
- Using `window.location.origin` makes the link work across different deployment environments

## Impact
- Teams can now successfully register via the copied link
- No authentication barriers for team registration
- Maintains separation between organizer admin panel and public team registration
