# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Awards page — assign awards (MVP, Best Receiver, etc.) with player names and custom or sample icons; visible on the Live page for spectators
- Show Test Buttons toggle in Settings — test buttons on Teams, Courts, Pools, and Bracket pages are hidden by default and can be enabled via a checkbox
- Delete account with confirmation dialog and validation
- Admin-only site-wide export/import for platform migration
- User-level export/import for all tournaments
- Public live page for spectators at /live/<user>/<slug>
- User authentication and per-user tournament isolation

### Changed
- Rewrite README and add USER_GUIDE for end users
- Reorder deployment configuration to fix first-deploy race condition
- Separate runtime data from deploy artifacts

### Fixed
- Set active tournament after user import to fix post-delete navigation
- Tournament CRUD corner cases — guard, session sync, YAML resilience
- Preserve SECRET_KEY across deploys to prevent session logout
- Nav bar Live link points to public URL for current tournament
- Seed default tournament when new user registers
- Detect 502 in deploy.ps1 and add alternative deploy scripts
