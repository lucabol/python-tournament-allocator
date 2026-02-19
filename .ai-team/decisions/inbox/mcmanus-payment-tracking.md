# Payment Tracking Feature

**Decision Date:** 2025-01-XX  
**Status:** Implemented  
**Component:** Backend / Registration System

## Context

Tournament organizers need to track which registered teams have paid their entry fees. Previously, there was no way to mark teams as paid or retrieve a list of teams that still need to pay.

## Decision

Added payment tracking to the registration system with the following implementation:

### Data Model
- Added `paid` field (boolean) to team registrations in `registrations.yaml`
- Defaults to `false` for all new registrations
- Persists across application restarts
- Automatically added to existing registrations via `load_registrations()`

### API Endpoints

#### POST `/api/toggle-paid`
- Requires: `team_name` in JSON body
- Toggles paid status for a team
- Returns: `{'success': True, 'paid': <new_status>}`
- Requires login

#### GET `/api/unpaid-teams`
- Returns list of teams where `paid=false`
- Includes: team_name, email, phone, status, assigned_pool
- Useful for sending payment reminders
- Requires login

### Implementation Details
1. **Data persistence:** The `paid` field is stored in `registrations.yaml` alongside other team data
2. **Backward compatibility:** Existing registrations without the paid field are automatically initialized to `false` when loaded
3. **Default behavior:** New registrations via `/register/<username>/<slug>` automatically set `paid: false`

## Rationale

- **Toggle vs. Set:** Used toggle pattern to match existing API conventions (e.g., `/api/registrations/toggle`)
- **Unpaid list:** Provides all contact info in one request to facilitate bulk email/notification operations
- **Backward compatibility:** Automatic field initialization ensures no migration script needed

## Testing

Added comprehensive test suite in `tests/test_registration.py::TestPaymentTracking`:
- Default unpaid status for new registrations
- Toggle functionality (paid → unpaid → paid)
- Error handling for non-existent teams
- Contact info in unpaid list
- Persistence across multiple loads

## Future Considerations

- Frontend UI to display payment status in teams table
- Bulk operations (mark all as paid/unpaid)
- Payment history/timestamps
- Integration with payment processors
