---
name: "cpsat-reification-patterns"
description: "Using OR-Tools CP-SAT reification to link boolean variables to conditions for soft constraints"
domain: "constraint-programming"
confidence: "low"
source: "earned"
---

## Context
OR-Tools CP-SAT solver allows soft constraints (penalties in the objective function) by creating boolean variables that detect when a condition is true. This is essential for modeling preferences that you want to discourage but not prohibit (e.g., "avoid consecutive matches, but allow them if necessary").

## Patterns

### Basic Reification: Boolean ↔ Condition
Link a boolean variable to a condition using `OnlyEnforceIf`:

```python
# Create a boolean variable
is_condition_true = model.NewBoolVar("condition_true")

# Link it to a condition (reification)
model.Add(some_variable < threshold).OnlyEnforceIf(is_condition_true)
model.Add(some_variable >= threshold).OnlyEnforceIf(is_condition_true.Not())

# Now is_condition_true = 1 iff (some_variable < threshold)
```

**Key insight:** You must add BOTH constraints — one for when the boolean is true, one for when it's false. This forces the solver to set the boolean correctly.

### Detecting "Too Close" Conditions
Common pattern: detect when two events are within a threshold:

```python
# Calculate absolute difference
diff = model.NewIntVar(-max_val, max_val, "diff")
abs_diff = model.NewIntVar(0, max_val, "abs_diff")
model.Add(diff == var1 - var2)
model.AddAbsEquality(abs_diff, diff)

# Detect if too close
is_too_close = model.NewBoolVar("too_close")
model.Add(abs_diff < threshold).OnlyEnforceIf(is_too_close)
model.Add(abs_diff >= threshold).OnlyEnforceIf(is_too_close.Not())
```

### Summing Booleans into a Penalty
Collect all detection booleans and sum them:

```python
detection_vars = []
for ... in ...:
    is_bad = model.NewBoolVar(f"bad_{i}")
    # ... link is_bad to condition ...
    detection_vars.append(is_bad)

# Sum all booleans into a penalty variable
penalty = model.NewIntVar(0, len(detection_vars), "penalty")
model.Add(penalty == sum(detection_vars))

# Add to objective
model.Minimize(primary_objective + penalty * penalty_weight)
```

### Linking to Optional Variables
When dealing with optional interval variables (e.g., match assigned to court X only if present), link through presence:

```python
# Global variable that exists unconditionally
global_var = model.NewIntVar(0, max_val, "global")

# Link to optional variables via presence
for option in options:
    present = option_present_vars[option]
    local_var = option_local_vars[option]
    # When this option is present, global_var equals the local value
    model.Add(global_var == local_var).OnlyEnforceIf(present)
```

## Anti-Patterns
- **Forgetting the negated constraint** — if you only add `model.Add(condition).OnlyEnforceIf(bool_var)`, the solver may leave `bool_var = 0` even when condition is true. Always add both the positive and negative case.
- **Creating redundant global variables** — if you need the same "global start time" for multiple pairs, create it once and reuse it. Don't create `global_start_temp_m{i}_{team}` repeatedly for the same match.
- **Penalty weight too high** — if penalty weight exceeds primary objective weight, the solver will prioritize avoiding the penalty over the main goal. Penalty weight should be significant but subordinate.

## Examples

### Real-world: Consecutive Match Detection
From `src/core/allocation.py` (tournament scheduling):

```python
# For each team, detect when two matches are within 2× match duration
threshold = 2 * (match_slots + break_slots)

is_consecutive = model.NewBoolVar(f"consecutive_{team}_m{m1}_m{m2}")

# Calculate time difference
diff = model.NewIntVar(-max_time, max_time, f"diff_{team}_m{m1}_m{m2}")
abs_diff = model.NewIntVar(0, max_time, f"abs_diff_{team}_m{m1}_m{m2}")
model.Add(diff == global_start_m1 - global_start_m2)
model.AddAbsEquality(abs_diff, diff)

# Reify: is_consecutive ↔ (abs_diff < threshold)
model.Add(abs_diff < threshold).OnlyEnforceIf(is_consecutive)
model.Add(abs_diff >= threshold).OnlyEnforceIf(is_consecutive.Not())

# Collect and sum
consecutive_detection_vars.append(is_consecutive)

# Later: add to objective
consecutive_penalty = sum(consecutive_detection_vars)
model.Minimize(makespan * W1 - min_gap * W2 + consecutive_penalty * W3)
```

**Why this works:** The solver can still schedule consecutive matches if space is tight (soft constraint), but it will avoid them when possible because doing so reduces the objective.
