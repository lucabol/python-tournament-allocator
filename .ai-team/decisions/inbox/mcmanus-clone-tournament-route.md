### 2026-02-13: Clone tournament uses shutil.copytree for full directory copy
**By:** McManus
**What:** `POST /api/tournaments/clone` copies the entire source tournament directory (all YAML, CSV, logos, awards, etc.) to a new slug directory using `shutil.copytree()`, then patches `tournament_name` in the cloned `constraints.yaml`. Added `api_clone_tournament` to the `before_request` endpoint whitelist.
**Why:** `copytree` is the simplest way to get a true clone — no need to maintain a list of which files to copy. Any new file types added to tournaments in the future will automatically be included in clones. The `constraints.yaml` patch ensures the cloned tournament shows its own name in the UI rather than the source's name.
