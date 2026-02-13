---
name: "pytest-slow-marker"
description: "Using pytest markers to create fast/slow test subsets for developer productivity"
domain: "testing"
confidence: "low"
source: "earned"
---

## Context
Large test suites often have a few tests that dominate total runtime (solver timeouts, integration tests with external services, large data sets). Developers making small changes (CSS tweaks, copy edits) shouldn't wait minutes for unrelated slow tests.

## Patterns

### Marker-Based Test Subsetting
1. Register a `slow` marker in `pytest.ini` (or `pyproject.toml`):
   ```ini
   [pytest]
   markers =
       slow: marks tests as slow (deselect with '-m "not slow"')
   ```

2. Mark only genuinely slow tests (> ~2s). Don't over-mark — if a test runs under 1 second, it's not slow:
   ```python
   @pytest.mark.slow
   class TestExpensiveOperation:
       """Tests that invoke solver/optimizer with timeout."""
       ...
   ```

3. Document the two run modes where developers will see it (conftest.py docstring, README, or CI config):
   ```
   pytest tests/                 - full suite
   pytest tests/ -m "not slow"  - fast subset for small changes
   ```

### Identifying Slow Tests
Run `pytest --durations=0` to see all test durations sorted slowest-first. Look for tests that are 10x+ slower than the median. Common culprits:
- Constraint solvers / optimizers with timeouts
- Network calls or external service integration
- Large data generation or file I/O
- Sleep-based timing tests

## Anti-Patterns
- **Marking too many tests as slow** — defeats the purpose. Only mark tests that are genuinely expensive (seconds, not milliseconds).
- **Marking at method level when the whole class is slow** — prefer class-level `@pytest.mark.slow` to avoid marker drift as new methods are added.
- **Not running full suite in CI** — the fast subset is for local dev only. CI should always run `pytest tests/` (no marker filter).

## Examples

```python
# Good: class-level marker, all methods in this class use OR-Tools solver
@pytest.mark.slow
class TestLargeTournament:
    def test_large_tournament_scheduling(self, ...):
        ...
    def test_multi_day_distribution(self, ...):
        ...

# Bad: marking a test that runs in 0.3s
@pytest.mark.slow  # Don't do this — 0.3s is fast
def test_some_quick_check(self):
    ...
```
