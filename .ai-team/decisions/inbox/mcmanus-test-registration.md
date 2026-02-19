### 2026-02-19: Test button teams must be registered in registrations.yaml

**By:** McManus

**What:** The Test button (`/api/test-teams`) now creates registration records in `registrations.yaml` for all test teams, not just pool assignments in `teams.yaml`. Each test team gets a record with `status='assigned'`, `assigned_pool=pool_name`, a generated email, and a timestamp.

**Why:** Pool deletion logic expects teams to exist in `registrations.yaml` so it can unassign them. Without registration records, Test teams disappeared when their pool was deleted instead of returning to the Registered Teams section. This ensures Test teams follow the same data flow as manually registered teams.
