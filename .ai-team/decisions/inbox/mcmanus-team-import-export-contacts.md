# Team Import/Export with Contact Information

**Date:** 2026-02-19  
**Author:** McManus (Backend Developer)  
**Status:** Implemented

## Context

The tournament allocator needed to support importing and exporting team information that includes contact details (email and phone numbers) in addition to team names.

## Decision

Enhanced the team YAML import/export functionality to support team objects with email and phone fields while maintaining backward compatibility with simple string-based team lists.

### Import Format

The system now accepts teams in three formats:

1. **Team object with contact info** (new):
   ```yaml
   Pool A:
     teams:
       - name: "Team Name"
         email: "team@example.com"
         phone: "555-1234"
   ```

2. **Mixed format** (backward compatible):
   ```yaml
   Pool A:
     teams:
       - name: "Team 1"
         email: "team1@example.com"
       - Team 2  # Simple string
   ```

3. **Simple string format** (legacy):
   ```yaml
   Pool A:
     teams:
       - Team 1
       - Team 2
   ```

### Implementation Details

- **Import**: When teams with email/phone are imported, the contact information is stored in `registrations.yaml`
- **Export**: The `/api/export-teams` endpoint merges team data from `teams.yaml` with contact info from `registrations.yaml`
- **Backward Compatibility**: Teams without contact info continue to be exported as simple strings
- **Data Separation**: Team names remain in `teams.yaml` for pool assignments; contact details are stored in `registrations.yaml`

## Rationale

This approach maintains data integrity by:
1. Keeping the existing `teams.yaml` structure unchanged (just team names per pool)
2. Using `registrations.yaml` as the source of truth for contact information
3. Supporting seamless import/export with or without contact details
4. Enabling administrators to export tournament configurations that can be shared and reimported

## Impact

- Existing tournaments with simple string team names will continue to work without modification
- Administrators can now import tournament configurations with pre-filled contact information
- The export functionality provides a complete snapshot that can be reimported
- No breaking changes to existing data structures or API endpoints

## Testing

Created and validated test scenarios covering:
- Import with team objects containing email and phone
- Import with mixed format (some objects, some strings)
- Export merging teams with registrations
- Backward compatibility with existing string-only format
