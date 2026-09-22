# Changelog

All notable user-facing changes to Cursay are documented here.

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
