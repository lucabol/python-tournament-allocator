# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Fixed
- Hide "Up Next" section on Live page when tournament is finished (champion crowned)

### Removed
- Print page — replaced by the Insta page for tournament sharing

### Added
- QR code on dashboard — scan to open the Live page; replaces the old text link on the Pools page
- Hamburger menu on mobile — navbar collapses into a slide-out menu on small screens (≤768px)
- Dark mode toggle — 🌙/☀️ button in navbar switches between light and dark themes, persisted in localStorage
- Clear/undo match results — ✕ button on completed matches in the Tracking page to remove a result
- Insta page now includes bracket results (Gold/Silver brackets) and awards section
- Insta page — Instagram-friendly tournament summary card with vibrant gradient design, champions, pool standings, and awards; optimized for phone screenshots
- Test button on Awards page to autofill 5 beach volleyball awards (MVP, Best Blocker, Best Defender, Best Server, Spirit Award)
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
