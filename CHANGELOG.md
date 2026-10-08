# Changelog

All notable user-facing changes to Cursay are documented here.

## Unreleased

### Fixed

- Require an active Pro entitlement and available cloud allowance before marking managed cloud ready or uploading audio; show an upgrade action for free accounts and explain local fallback.
- Handle Option + Space directly with existing Accessibility access, including either key-release order and recovery after sleep or an event-handler timeout.
- Keep Cursay in the window title on every page.
- Correct spoken-code bracket cleanup on current macOS regular-expression engines.

### Added

- Added optional Cursay Pro accounts with managed cloud transcription, Smart Polish, monthly usage reporting, browser-based device linking, secure token rotation, device revocation, and local fallback on Ubuntu and macOS.
- Added the Next.js account website and metadata-only cloud API backed by Clerk, Stripe, Neon, and Vercel AI Gateway with per-request zero data retention.
- Added subscription trials, fixed monthly/annual checkout, Customer Portal access, signature-verified webhook entitlements, monthly quotas, concurrency limits, and one-use polish grants.
- Added macOS Prompt mode and Smart Polish parity, Keychain-backed Pro linking, Sparkle 2 updates, and Developer ID signing/notarization/DMG release automation.
- Added a self-contained macOS Local Whisper helper that starts on demand, exits with the app, and stores models in Application Support.
- Added macOS transcription-cost insights, appearance selection, configurable global shortcuts, and actionable connection diagnostics.
- Added a native Windows 10/11 x64 app with Ctrl + Space push-to-talk, microphone capture, safe automatic paste, searchable local history, insights, settings, and notification-area controls.
- Added a self-contained Windows installer containing the local faster-whisper service, plus SHA-256 checksum generation.
- Added Windows build and test automation.

## 1.2.1 - 2026-09-22

### Added

- Added a fully pinned, hash-verified lockfile for the bundled transcription backend.

### Changed

- The installer now enforces the locked backend dependency set.
- Linked the canonical [Cursay website](https://cursay.com/) from the README and GitHub repository homepage.

## 1.2.0 - 2026-09-22

### Added

- Added a native macOS developer preview with push-to-talk dictation, automatic paste, local history, and a menu-bar controller.
- Added Prompt writing mode for turning spoken intent into a ready-to-paste AI prompt.
- Added an Ubuntu in-app updater that verifies versioned release archives against their published SHA-256 checksums.
- Added optional Smart Polish rewriting with distinct Professional and Casual styles.
- Added visible fallback messaging when Smart Polish is unavailable.
- Added local transcription-cost insights with provider/model breakdowns.
- Added support for exact provider-reported request costs when compatible endpoints return them.
- Added duration-based xAI REST speech-to-text estimates using its published rate.

### Changed

- Clarified that Code and Raw modes never use Smart Polish.
- Improved the Dictate screen's explanation of each writing mode.
- Databases are migrated automatically to store optional provider-reported costs.
- Installing with `--skip-backend` now removes a previously enabled bundled STT service.

## 1.1.0 - 2026-09-20

### Added

- Added system, light, and dark appearance options.

### Fixed

- Improved long-running recording behavior and audio-process cleanup.

## 1.0.0 - 2026-09-20

- Initial public release of Cursay for Ubuntu GNOME on Wayland.
