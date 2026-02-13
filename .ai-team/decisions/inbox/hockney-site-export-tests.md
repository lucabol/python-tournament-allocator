### Site export/import test pattern: admin login helper
**By:** Hockney
**Date:** 2026-02-12
**What:** `TestSiteExportImport._login_as_admin()` is the canonical pattern for tests that need admin privileges. It adds admin to `users.yaml`, creates the admin user directory tree, writes `.secret_key` to `DATA_DIR`, and switches the client session to `'admin'`. Future admin-only endpoint tests should reuse this pattern rather than inventing their own setup.
**Why:** The existing `client` fixture always logs in as `testuser`. Admin-gated endpoints need a repeatable way to escalate. Centralizing in one helper avoids duplication and makes it easy to update if the admin detection logic changes (e.g., if `is_admin()` evolves beyond a simple username check).
