# Verbal — History

## Learnings

### 2026-02-20: Bracket Display vs Schedule Mismatch — Root Cause

- The recurring bracket/schedule mismatch bug stems from a fundamental architectural split: two independent bracket generators (`generate_double_elimination_bracket` for schedule, `generate_double_bracket_with_results` for bracket tab) producing data independently, connected only by a fragile heuristic key-translation layer in `enrich_schedule_with_results()`.
- There are THREE identifier formats for the same match: `match_code` (e.g., `W1-M1`), `match_key` (e.g., `winners_Winners Quarterfinal_1`), and internal round tracking keys. Results are stored under `match_key` but looked up by `match_code`, requiring reconstruction via `derive_match_code()`.
- Every previous fix added more mapping complexity (dual-format lookup, team-pair fallback, hardcoded bracket-size-specific code paths) instead of addressing the split. This is why the bug recurs — each new mapping introduces new edge cases.
- The test suite covers individual bracket generators well but has NO round-trip integration test that saves a result via the bracket tab's key format and verifies the schedule tab's enrichment can find it. This is the exact seam where the bug lives.
- **Recommended fix:** Unify to a single stored bracket structure in `schedule.yaml`, standardize on `match_code` as the sole identifier, and add end-to-end round-trip tests. Full analysis in `.squad/decisions/inbox/verbal-bracket-architecture.md`.
