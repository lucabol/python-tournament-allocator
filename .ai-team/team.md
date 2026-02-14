# Team Roster

> Python Flask tournament scheduling and management web application.

## Coordinator

| Name | Role | Notes |
|------|------|-------|
| Squad | Coordinator | Routes work, enforces handoffs and reviewer gates. Does not generate domain artifacts. |

## Members

| Name | Role | Charter | Status |
|------|------|---------|--------|
| Verbal | Lead | `.ai-team/agents/verbal/charter.md` | ✅ Active |
| McManus | Backend Dev | `.ai-team/agents/mcmanus/charter.md` | ✅ Active |
| Fenster | Frontend Dev | `.ai-team/agents/fenster/charter.md` | ✅ Active |
| Hockney | Tester | `.ai-team/agents/hockney/charter.md` | ✅ Active |
| Keaton | Azure Deployment | `.ai-team/agents/keaton/charter.md` | ✅ Active |
| Scribe | Session Logger | `.ai-team/agents/scribe/charter.md` | 📋 Silent |
| Ralph | Work Monitor | — | 🔄 Monitor |


## Coding Agent

<!-- copilot-auto-assign: true -->

| Name | Role | Charter | Status |
|------|------|---------|--------|
| @copilot | Coding Agent | — | 🤖 Coding Agent |

### Capabilities

**🟢 Good fit — auto-route when enabled:**
- Bug fixes with clear reproduction steps
- Test coverage (adding missing tests, fixing flaky tests)
- Lint/format fixes and code style cleanup
- Dependency updates and version bumps
- Small isolated features with clear specs
- Boilerplate/scaffolding generation
- Documentation fixes and README updates

**🟡 Needs review — route to @copilot but flag for squad member PR review:**
- Medium features with clear specs and acceptance criteria
- Refactoring with existing test coverage
- API endpoint additions following established patterns
- Migration scripts with well-defined schemas

**🔴 Not suitable — route to squad member instead:**
- Architecture decisions and system design
- Multi-system integration requiring coordination
- Ambiguous requirements needing clarification
- Security-critical changes (auth, encryption, access control)
- Performance-critical paths requiring benchmarking
- Changes requiring cross-team discussion

## Project Context

- **Owner:** Luca Bolognese (lucabol@microsoft.com)
- **Stack:** Python 3.11+, Flask, Jinja2, pandas, numpy, OR-Tools CP-SAT, PyYAML, pytest
- **Description:** Tournament scheduling app with pool play, single/double elimination brackets, court allocation, and match result tracking.
- **Created:** 2026-02-11

## Issue Source

| Field | Value |
|-------|-------|
| **Repository** | lucabol/python-tournament-allocator |
| **Connected** | 2026-02-13 |
| **Filters** | all open |
