# Team Import/Export Enhancement - Summary

## What Was Changed

Enhanced the team YAML import/export functionality to support team contact information (email and phone numbers) while maintaining full backward compatibility.

## New Features

### Enhanced Import Format

Teams can now be imported with contact information:

```yaml
Pool A:
  teams:
    - name: "Team Alpha"
      email: "alpha@example.com"
      phone: "555-1111"
    - name: "Team Beta"
      email: "beta@example.com"
    - Team Gamma  # Simple format still works
  advance: 2
```

### Export Endpoint

New `/api/export-teams` endpoint exports teams with their contact information in a format that can be reimported.

## Technical Implementation

- **Import**: Extended `load_yaml` action in `/teams` route to parse team objects with email/phone fields
- **Export**: New `/api/export-teams` route merges `teams.yaml` with `registrations.yaml` to create complete export
- **Data Storage**: Contact info stored in `registrations.yaml`, team names remain in `teams.yaml`
- **Backward Compatibility**: Simple string team names continue to work without modification

## Usage

### Import
1. Navigate to Teams page
2. Click "Import Teams" button
3. Select YAML file with teams (can include email/phone or not)
4. Teams are imported to pools, contact info saved to registrations

### Export
1. Navigate to Teams page
2. Click "Export Teams" button
3. Downloads `teams_export.yaml` with all team data and contact information
4. This file can be imported back into any tournament

## Files Modified

- `src/app.py`: Updated `load_yaml` action, added `/api/export-teams` endpoint
- `src/templates/teams.html`: Updated help modal to show new format
- `tests/test_team_import_export.py`: New comprehensive tests
- `tests/conftest.py`: Added shared `client` and `temp_data_dir` fixtures

## Testing

All new functionality is covered by tests:
- Import with team objects containing email/phone
- Export merging teams with registrations
- Backward compatibility with string-only format

Run tests:
```bash
pytest tests/test_team_import_export.py -v
```
