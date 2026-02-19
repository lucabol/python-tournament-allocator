# Decision: Paid Status Field Must Always Be Explicitly Set

**Date:** 2025-01-27  
**Author:** McManus (Backend Developer)  
**Status:** Implemented

## Context

Two related bugs were identified in team registration handling:

1. Paid status was being reset when teams were moved between pools
2. The unpaid-teams API endpoint was returning undefined team names

## Root Cause

When creating new registration records during YAML file imports or test data generation, the `paid` field was not being explicitly set. This caused it to default to `None` or be missing entirely, which was then interpreted as unpaid.

Additionally, the unpaid-teams endpoint was using dictionary access (`reg['team_name']`) instead of safe access (`reg.get('team_name')`), causing errors when registration records had missing fields.

## Decision

**All registration record creation must explicitly include `'paid': False`**

This applies to:
1. YAML file imports (when teams are loaded into pools)
2. Public team registration submissions
3. Test data generation
4. API-driven team assignments

When updating existing registrations, preserve the existing `paid` value using:
```python
if 'paid' not in existing_reg:
    existing_reg['paid'] = False
```

## Implementation

### Files Changed
- `src/app.py` (4 locations)

### Changes Made

1. **YAML import (2 locations):** Added `'paid': False` to new registration records and preserved existing paid status when updating records
2. **Test data generation:** Added `'paid': False` to test registration records  
3. **Unpaid teams endpoint:** Changed from `reg['team_name']` to `reg.get('team_name', 'Unknown Team')` with validation

## Rationale

- **Explicit is better than implicit:** Every registration should have a clearly defined paid status
- **Preservation over deletion:** When teams move between pools, their payment status must persist
- **Defense in depth:** Use safe dictionary access to handle edge cases gracefully

## Impact

- Paid status now persists correctly when teams are deleted from pools or pools are deleted
- Unpaid teams endpoint returns proper team names instead of undefined values
- All registration records have consistent schema with paid field
