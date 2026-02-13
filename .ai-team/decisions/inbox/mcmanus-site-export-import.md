### 2026-02-12: Site-wide export/import uses full replace strategy
**By:** McManus
**What:** `POST /api/import/site` does a full replace of `users/`, `users.yaml`, and `.secret_key` in DATA_DIR before extracting the ZIP. After import, the Flask session is cleared and the user is redirected to the login page. This differs from user-level import which does additive merge.
**Why:** Site export/import is for platform migration — you want an exact copy of the source site, not a merge. Full replace is the only thing that makes sense when you're moving the entire platform. Clearing the session forces re-login because user credentials and secret key may have changed. The 50MB size limit (vs 10MB for user imports) accounts for multi-user data.
