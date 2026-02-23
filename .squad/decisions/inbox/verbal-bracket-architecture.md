# Bracket Display vs Schedule Display: Architectural Root Cause Analysis

**By:** Verbal (Lead)  
**Date:** 2026-02-20  
**Status:** Analysis — no code changes  
**Requested by:** Luca Bolognese  

---

## Problem Statement

The Bracket tab and the Schedule/Live tabs repeatedly show different matches for the same tournament bracket. This has been "fixed" multiple times but keeps recurring. This document traces the root cause to a fundamental architectural flaw: **two independent code paths generate bracket data, and a third code path tries to reconcile them via heuristic key-mapping**.

---

## 1. Data Flow Map

### Path A: Bracket Tab Display (dbracket.html)

```
dbracket() route (app.py:4211)
  → generate_double_bracket_with_results(pools, standings, bracket_results)
    → seeds teams from pools/standings
    → builds winners_bracket, losers_bracket round by round
    → looks up results using DUAL-FORMAT: bracket_results.get(match_code) or bracket_results.get(match_key)
    → advances winners/losers dynamically based on results found
  → renders dbracket.html with live bracket_data
```

**Key identity format used:** `match_code` like `W1-M1`, `L2-M1`, `GF`, `BR`

### Path B: Schedule Tab Display (schedule.html)

```
schedule() route POST (app.py:2884)
  → generate_bracket_execution_order(pools, None, prefix="", phase_name="Bracket")
    → calls generate_double_elimination_bracket(pools, None)  ← NOTE: standings=None at generation time
    → flattens all bracket matches into execution order list
    → each match carries match_code like W1-M1, L1-M1, etc.
  → schedules matches onto courts with times
  → saves to schedule.yaml via save_schedule()

schedule() route GET (app.py:3114)
  → load_schedule()  ← reads schedule.yaml (frozen at generation time)
  → enrich_schedule_with_results(schedule_data, results, pools, standings)
    → builds resolved_teams lookup from bracket_results
    → derives match_code from bracket_type + round + match_number via heuristic
    → resolves placeholders like "#1 Pool A" → actual team names
    → resolves "Winner W1-M1" → actual winner from results
    → matches bracket results to schedule matches by: match_code → match_key → team-pair fallback
  → renders schedule.html
```

### Path C: Result Saving (dbracket.html → save_bracket_result API)

```
JavaScript saveBracketResult() (dbracket.html:1051)
  → reads from DOM: team1, team2, round, matchNumber, bracketType, matchCode
  → POST /api/results/bracket

save_bracket_result() (app.py:3960)
  → match_key = f"{bracket_type}_{round_name}_{match_number}"
    e.g. "winners_Winners Quarterfinal_1"
  → saves to results['bracket'][match_key] with fields:
    { match_code: "W1-M1", bracket_type: "winners", round: "Winners Quarterfinal", match_number: 1, ... }
```

### Path D: Random Result Generation (app.py:2394)

```
api_generate_random_bracket_results()
  → calls generate_double_bracket_with_results() in a loop
  → saves results with keys like:
    "winners_{round_name}_{match_number}" → e.g. "winners_Winners Quarterfinal_1"
    "losers_{round_name}_{match_number}"  → e.g. "losers_Losers Round 1_1"
    "grand_final_Grand Final_1"
    "bracket_reset_Bracket Reset_1"
  → also stores match_code field inside the result dict
```

---

## 2. The Three Identifier Formats

There are THREE different identifier formats used across the system:

| Format | Example | Where Created | Where Used for Lookup |
|--------|---------|---------------|----------------------|
| **match_code** | `W1-M1`, `L2-M1`, `GF`, `BR` | `_generate_winners_bracket()`, `_generate_losers_bracket()` | Schedule enrichment, bracket display (dual-format), template `data-match-code` |
| **match_key** | `winners_Winners Quarterfinal_1` | `save_bracket_result()`, random result generator | Primary key in `results.yaml` bracket dict |
| **round_name internal** | `Winners Quarterfinal_1`, `Losers Round 1_1` | `generate_double_bracket_with_results()` internal tracking | Internal winner/loser advancement tracking only |

### The Core Mismatch

- **Results are stored** under `match_key` format: `winners_Winners Quarterfinal_1`
- **Schedule matches** carry `match_code` format: `W1-M1`
- **The enrichment function** must translate between these two formats

The translation happens in `derive_match_code()` (app.py:707-734) which attempts to reconstruct `match_code` from the stored `bracket_type`, `round`, and `match_number`. This is fragile because:

1. It depends on `round_indices` — a mapping built by iterating results and counting unique round names per bracket_type. If results arrive in a different order, the indices could differ.
2. The round name `"Winners Quarterfinal"` maps to round index `1` only if it's the first unique round seen for `bracket_type="winners"`. But the actual round index depends on bracket size (an 8-team bracket has 3 winners rounds, a 4-team has 2).
3. The `derive_match_code()` function is a **heuristic reconstruction** — it doesn't have access to the actual bracket structure.

---

## 3. Root Cause: Two Independent Bracket Generators

### The Fundamental Problem

The system has **two completely separate code paths** that generate bracket structures:

1. **`generate_double_elimination_bracket()`** → used by `generate_bracket_execution_order()` → used by schedule generation  
2. **`generate_double_bracket_with_results()`** → used by bracket tab display  

These two functions:
- Both call `seed_teams_from_pools()` independently
- Both call `_generate_bracket_order()` independently  
- Both build winners/losers brackets from scratch
- Function #1 uses `standings=None` at schedule generation time (pools haven't been played yet)
- Function #2 uses actual `standings` from pool results

**When standings change the seeding**, the bracket matchups change, but the schedule was frozen at generation time with placeholder seedings. The enrichment function then tries to paper over this gap.

### Why Previous Fixes Keep Breaking

Each "fix" has added more translation/mapping complexity:

1. First, results were stored only by `match_key` (`winners_Winners Quarterfinal_1`). Schedule couldn't find them.
2. Fix: Added `match_code` field to stored results. But `enrich_schedule_with_results()` didn't look it up.
3. Fix: Added `derive_match_code()` to reconstruct `match_code` from stored fields. But it gets indices wrong for some bracket sizes.
4. Fix: Added dual-format lookup (`bracket_results.get(match_code) or bracket_results.get(match_key)`). But the bracket display and schedule may disagree on which match is `W1-M1` vs `W1-M2`.
5. Fix: Added team-pair fallback matching. But if bracket tab shows Team A vs Team B in W1-M1 and schedule shows Team A vs Team B in W1-M2 (different match ordering), the result gets attached to the wrong match.

**The mapping layer grows ever more complex but can never fully reconcile two independently-generated bracket structures.**

---

## 4. Secondary Issues

### 4a. Schedule Frozen at Generation Time

When the schedule is generated (POST to `/schedule`), bracket matches use `standings=None` because pool play hasn't happened yet. Placeholders like `#1 Pool A` are used. The schedule is saved to `schedule.yaml` with these placeholders.

Later, when displaying, `enrich_schedule_with_results()` resolves these placeholders. But the *match pairings* (which seeds play which) were determined at generation time. If the bracket tab regenerates with actual standings and gets different pairings, the two views diverge.

### 4b. Round Name Instability

Round names like `"Winners Quarterfinal"`, `"Winners Semifinal"` depend on bracket size. The `get_winners_round_name()` function maps team count to name. If the number of advancing teams changes (e.g., user edits pool configuration), the round names change, breaking all stored `match_key` lookups.

### 4c. Grand Final/Bracket Reset Placeholder Text Mismatch

- Schedule stores: `teams: ['Winners Bracket Champion', 'Losers Bracket Champion']`
- Bracket display generates: `teams: (actual_winner_name, actual_loser_name)` or `('Winners Bracket Champion', 'Losers Bracket Champion')`
- Enrichment function hardcodes fallback searches: `for code in ['W3-M1', 'W2-M1', 'W1-M1']` — this only works for specific bracket sizes.

---

## 5. Proposed Simplification

### Single Source of Truth Architecture

**Principle:** There should be ONE bracket generation call whose output is used by ALL consumers.

#### Option A: Store the Bracket in schedule.yaml (Recommended)

1. When schedule is generated, call `generate_double_elimination_bracket(pools, None)` ONCE
2. Store the complete bracket structure (all rounds, match_codes, team slots) in `schedule.yaml` alongside the time-slot schedule
3. The bracket tab reads from this same stored structure instead of regenerating
4. `generate_double_bracket_with_results()` operates on the STORED bracket, not a freshly generated one
5. Results are stored using `match_code` as the primary key (e.g., `W1-M1`, not `winners_Winners Quarterfinal_1`)
6. Enrichment becomes a simple dict lookup: `results.get(match['match_code'])`

#### Key Changes

| Current | Proposed |
|---------|----------|
| `match_key = f"{bracket_type}_{round_name}_{match_number}"` | `match_key = match_code` (e.g., `W1-M1`) |
| `save_bracket_result()` generates match_key from round name | `save_bracket_result()` uses `match_code` directly |
| `enrich_schedule_with_results()` has 50+ lines of key translation | Direct `results[match_code]` lookup |
| `derive_match_code()` heuristic reconstruction | Not needed — match_code is the stored key |
| Bracket tab calls `generate_double_bracket_with_results()` from scratch | Bracket tab reads stored bracket + overlays results |
| Two generators can produce different match orderings | One stored bracket — display is derived, not regenerated |

#### Migration Path

1. Change `save_bracket_result()` to use `match_code` as primary key in `results.yaml`
2. Keep backward-compatible dual-format lookup for existing stored results
3. Change `dbracket()` route to load stored bracket structure from `schedule.yaml`
4. Simplify `enrich_schedule_with_results()` to direct match_code lookup
5. Remove `derive_match_code()` and related mapping logic

---

## 6. Test Gap Analysis

### Why Tests Don't Catch This

The existing tests (`test_schedule_bracket_consistency.py`, `test_bracket_consistency.py`) test:
- ✅ That `generate_double_elimination_bracket()` and `generate_double_bracket_with_results()` produce the same first-round pairings
- ✅ That match_codes are unique and correctly prefixed
- ✅ That placeholders use correct format

**What they DON'T test:**
- ❌ **The full round-trip**: save result on bracket tab → load schedule → enrich → verify same match shows result
- ❌ **The key translation**: save result with `match_key` format → verify `derive_match_code()` correctly reconstructs `match_code`
- ❌ **The enrichment for non-first-round matches**: losers bracket, grand final, bracket reset result resolution
- ❌ **The standings divergence**: generate schedule with `standings=None` → generate bracket display with actual `standings` → verify they agree on team positions
- ❌ **End-to-end with actual Flask app**: POST schedule generation → save result via API → GET schedule → verify bracket match shows result

### Tests That Would Catch This

```python
class TestBracketScheduleRoundTrip:
    """Integration test: result saved on bracket tab appears correctly on schedule tab."""
    
    def test_bracket_result_appears_in_schedule(self, client, sample_pools):
        """
        1. Generate schedule (creates schedule.yaml with bracket matches)
        2. Generate pool results to establish standings
        3. Save a bracket result via /api/results/bracket
        4. Load schedule and enrich with results
        5. Verify the bracket match in schedule shows the result
        """
        # ... setup ...
        
        # Save result using bracket tab's format
        result = client.post('/api/results/bracket', json={
            'team1': 'A1', 'team2': 'B2',
            'round': 'Winners Quarterfinal',
            'match_number': 1,
            'bracket_type': 'winners',
            'match_code': 'W1-M1',
            'sets': [[21, 15]]
        })
        
        # Load and enrich schedule
        schedule_data, _ = load_schedule()
        enriched = enrich_schedule_with_results(schedule_data, load_results(), pools, standings)
        
        # Find the W1-M1 match in schedule
        bracket_match = find_match_by_code(enriched, 'W1-M1')
        
        # CRITICAL ASSERTION: schedule shows the same result
        assert bracket_match['result']['winner'] == 'A1'
        assert bracket_match['result']['completed'] == True
    
    def test_all_bracket_match_codes_consistent(self, sample_pools, standings):
        """
        Verify that EVERY match_code produced by generate_bracket_execution_order
        also exists in generate_double_bracket_with_results output.
        """
        schedule_matches = generate_bracket_execution_order(pools, standings)
        display_bracket = generate_double_bracket_with_results(pools, standings, {})
        
        schedule_codes = {m['match_code'] for m in schedule_matches}
        display_codes = set()
        for matches in display_bracket['winners_bracket'].values():
            display_codes.update(m['match_code'] for m in matches)
        for matches in display_bracket['losers_bracket'].values():
            display_codes.update(m['match_code'] for m in matches)
        if display_bracket['grand_final']:
            display_codes.add(display_bracket['grand_final']['match_code'])
        if display_bracket['bracket_reset']:
            display_codes.add(display_bracket['bracket_reset']['match_code'])
        
        assert schedule_codes == display_codes, \
            f"Match code mismatch:\n  Schedule only: {schedule_codes - display_codes}\n  Display only: {display_codes - schedule_codes}"
```

### Root Test Design Principle

The missing test category is: **"save a result using the identifier system the bracket tab uses, then verify the schedule tab can find it using its own identifier system."** This is the exact seam where the bug lives, and no current test crosses it.

---

## 7. Summary

| Issue | Severity | Fix Complexity |
|-------|----------|----------------|
| Two independent bracket generators | 🔴 Critical — root cause | Medium — unify to one stored bracket |
| Three identifier formats for same match | 🔴 Critical — enables recurring bugs | Low — standardize on match_code |
| `derive_match_code()` heuristic | 🟡 High — fragile translation | Eliminated by fixing above |
| No round-trip integration test | 🟡 High — bugs slip through | Low — add 2-3 integration tests |
| Schedule frozen with standings=None | 🟠 Medium — by design but causes divergence | Addressed by stored bracket approach |

**The recurring nature of this bug is not due to insufficient fixes — it's due to a fundamentally split architecture. Each fix adds more mapping complexity, creating new edge cases. The solution is to eliminate the split: one bracket, one identifier, one source of truth.**
