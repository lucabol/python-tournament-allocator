# External Knowledge Resources

## Recommended Documentation to Add to AI Context

This document identifies external documentation that would enhance AI assistance for this codebase. Consider adding these URLs to your MCP fetch configuration or downloading key pages for context.

---

## Core Dependencies

### OR-Tools CP-SAT Solver
**Why**: Central to the scheduling algorithm implementation.

| Resource | URL | Priority |
|----------|-----|----------|
| CP-SAT Primer | https://developers.google.com/optimization/cp/cp_solver | High |
| Interval Variables Guide | https://developers.google.com/optimization/scheduling/job_shop | High |
| Python Reference | https://or-tools.github.io/docs/python/ortools/sat/python/cp_model.html | Medium |
| Scheduling with CP-SAT | https://developers.google.com/optimization/scheduling | High |

**Key Concepts**:
- `CpModel`, `CpSolver`
- `NewIntVar`, `NewBoolVar`, `NewIntervalVar`, `NewOptionalIntervalVar`
- `AddNoOverlap`, `Add`, `OnlyEnforceIf`
- `Minimize`, `Maximize`
- Solver status codes: `OPTIMAL`, `FEASIBLE`, `INFEASIBLE`

### Flask
**Why**: Web framework for the entire application.

| Resource | URL | Priority |
|----------|-----|----------|
| Flask Quickstart | https://flask.palletsprojects.com/en/3.0.x/quickstart/ | Medium |
| Request Handling | https://flask.palletsprojects.com/en/3.0.x/api/#flask.Request | Medium |
| Jinja2 Templates | https://jinja.palletsprojects.com/en/3.1.x/templates/ | Medium |

### PyYAML
**Why**: Used for all configuration and data persistence.

| Resource | URL | Priority |
|----------|-----|----------|
| PyYAML Documentation | https://pyyaml.org/wiki/PyYAMLDocumentation | Low |
| Safe Loading | https://github.com/yaml/pyyaml/wiki/PyYAML-yaml.load(input)-Deprecation | Low |

### pytest
**Why**: Test framework for all unit and integration tests.

| Resource | URL | Priority |
|----------|-----|----------|
| pytest Fixtures | https://docs.pytest.org/en/stable/explanation/fixtures.html | Medium |
| Parametrization | https://docs.pytest.org/en/stable/how-to/parametrize.html | Low |

---

## Domain Knowledge

### Tournament Bracket Formats
**Why**: Understanding bracket structures helps with elimination.py and double_elimination.py.

| Resource | URL | Priority |
|----------|-----|----------|
| Single Elimination | https://en.wikipedia.org/wiki/Single-elimination_tournament | Medium |
| Double Elimination | https://en.wikipedia.org/wiki/Double-elimination_tournament | High |
| Bracket Seeding | https://en.wikipedia.org/wiki/Seed_(sports) | Medium |

**Key Concepts**:
- Bye assignments for non-power-of-2 brackets
- Winners bracket vs Losers bracket flow
- Grand Final and bracket reset scenarios
- Pool play to bracket transitions

### Sports Scheduling Theory
**Why**: Theoretical background for constraint-based scheduling.

| Resource | URL | Priority |
|----------|-----|----------|
| Round-robin Tournament | https://en.wikipedia.org/wiki/Round-robin_tournament | Low |
| Sports Scheduling | https://en.wikipedia.org/wiki/Sports_scheduling | Low |

---

## Deployment

### Azure App Service (Python)
**Why**: Target deployment platform.

| Resource | URL | Priority |
|----------|-----|----------|
| Python on App Service | https://docs.microsoft.com/en-us/azure/app-service/quickstart-python | Medium |
| Gunicorn Configuration | https://docs.gunicorn.org/en/stable/configure.html | Low |
| Azure CLI Reference | https://docs.microsoft.com/en-us/cli/azure/webapp | Low |

---

## Suggested MCP Configuration

```json
{
  "mcpServers": {
    "fetch": {
      "command": "npx",
      "args": ["-y", "@anthropic/mcp-fetch"]
    }
  }
}
```

With fetch MCP enabled, you can request:
- `mcp_fetch_fetch` for any of the above URLs when working on related features
- Especially useful for OR-Tools CP-SAT documentation when modifying scheduling constraints

---

## Local Documentation to Create

Consider creating these additional internal docs:

1. **ARCHITECTURE.md** - High-level system architecture diagram
2. **DATA_FORMATS.md** - Detailed schema for all YAML/CSV files
3. **ALGORITHM_NOTES.md** - Explanation of CP-SAT model design decisions
4. **DEPLOYMENT.md** - Step-by-step Azure deployment guide
