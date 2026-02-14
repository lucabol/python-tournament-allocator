# Work Routing

How to decide who handles what.

## Routing Table

| Work Type | Route To | Examples |
|-----------|----------|----------|
| Architecture, data models, core logic design | Verbal | Multi-tournament data structure, migration strategy, API design |
| Flask routes, API endpoints, persistence, scheduling | McManus | CRUD endpoints, YAML/CSV I/O, AllocationManager changes |
| Jinja2 templates, CSS, HTML, UI components | Fenster | Tournament selector UI, template refactoring, responsive layout |
| Code review | Verbal | Review PRs, check quality, suggest improvements |
| Testing | Hockney | Write tests, find edge cases, verify fixes |
| Azure deployment, CI/CD, infrastructure | Keaton | App Service config, GitHub Actions, deployment scripts, monitoring |
| Scope & priorities | Verbal | What to build next, trade-offs, decisions |
| Session logging | Scribe | Automatic — never needs routing |

## Rules

1. **Eager by default** — spawn all agents who could usefully start work, including anticipatory downstream work.
2. **Scribe always runs** after substantial work, always as `mode: "background"`. Never blocks.
3. **Quick facts → coordinator answers directly.** Don't spawn an agent for "what port does the server run on?"
4. **When two agents could handle it**, pick the one whose domain is the primary concern.
5. **"Team, ..." → fan-out.** Spawn all relevant agents in parallel as `mode: "background"`.
6. **Anticipate downstream work.** If a feature is being built, spawn the tester to write test cases from requirements simultaneously.
