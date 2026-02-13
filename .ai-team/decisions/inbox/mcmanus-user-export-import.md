### User-level export/import uses additive merge for tournaments.yaml
**By:** McManus
**Date:** 2026-02-12
**What:** `POST /api/import/user` merges the imported `tournaments.yaml` with the existing one additively — new tournament slugs are appended, existing slugs get their `name` and `created` fields updated, and tournaments not present in the ZIP are preserved. This differs from the single-tournament import which is a full replace.
**Why:** Full replace would silently delete tournaments the user has locally but didn't include in the ZIP. Additive merge is safer for a bulk operation — you can import a subset without losing data. The trade-off is that there's no "clean import" path, but that can be achieved by deleting tournaments manually first.

### User export/import endpoints added to before_request whitelist
**By:** McManus
**Date:** 2026-02-12
**What:** `api_export_user` and `api_import_user` are added to the `tournament_endpoints` guard set in `set_active_tournament()`. These routes work even when the user has no active tournament (since they operate on the user-level tournaments registry, not a specific tournament).
**Why:** Without whitelisting, users with no tournaments would be redirected to `/tournaments` before these routes could execute. The export route needs to work even with zero tournaments (returns an empty zip with just the registry), and the import route is how a user would restore tournaments.
