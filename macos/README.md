# Cursay for Mac

This is the native macOS companion to the Ubuntu Cursay app. It uses SwiftUI, AppKit, AVFoundation, Keychain, and the same local/custom/cloud service contracts as Ubuntu. The tagged-release workflow produces a Developer ID-signed, notarized, stapled distribution.

## Included in the first native build

- Menu-bar app and full dashboard
- Configurable global push-to-talk shortcut with a conflict-safe fallback
- Native 16 kHz mono microphone recording
- Automatic copy and optional paste into the previously active app
- Professional, casual, prompt, code, and raw cleanup modes
- Searchable private history, local cost insights, and system/light/dark appearance options
- Local Whisper, optional Cursay Cloud, and configurable custom transcription
- Smart Polish, Pro usage reporting, secure browser linking, device revocation, and local fallback
- Optional audio retention and launch at login
- Sparkle 2 update checks with an EdDSA-signed appcast

## Build on your Mac

Requirements: macOS 13 or newer, Xcode 15 or newer, and Python 3.10 or newer. Release automation uses Python 3.12.

```bash
cd macos
./scripts/build-app.sh
open dist/Cursay.app
```

The script runs the Swift tests, builds the native app and a self-contained faster-whisper helper, and assembles `Cursay.app`. It uses an installed Apple Development signing identity when available so macOS can retain Accessibility consent across local rebuilds. When that identity is unavailable, the local ad-hoc fallback embeds a stable Cursay designated requirement instead of using a one-build code hash.

On first launch, macOS will ask for microphone access. Automatic paste also needs Cursay enabled in **System Settings → Privacy & Security → Accessibility**. Cursay copies the result even when Accessibility access is unavailable.

Option + Space uses a keyboard event handler with the same existing Accessibility access, rather than relying on Carbon hotkey delivery. It consumes only that exact shortcut, stops when either key is released, and restores the handler after sleep or an event timeout. Other shortcut choices use Carbon and do not require Accessibility for recording.

## Transcription service

The default endpoint is:

```text
http://127.0.0.1:8765/v1/audio/transcriptions
```

It matches the Python backend in this repository. The app starts the bundled helper automatically when Local Whisper is selected and stops it when the app exits. The first local transcription downloads the configured Whisper model to `~/Library/Application Support/Cursay/Models`. You can instead choose Cursay Cloud or a compatible Custom service in Settings; custom audio is governed by that service's privacy policy. The custom health check expects `/health` at the service root.

Selecting Cursay Cloud opens the browser-based device linking flow. Access and refresh tokens are kept only in a This-Device-Only Keychain item. Cloud failure, quota exhaustion, and subscription failure retain the recording long enough to try Local Whisper when fallback is enabled.

## Signed distribution

The source does not enable the App Sandbox because global paste automation depends on Accessibility permission. Release builds do use the hardened runtime and the minimum audio-input entitlement.

For a local release build, set `CURSAY_VERSION`, `CURSAY_BUILD_NUMBER`, `CURSAY_CODESIGN_IDENTITY`, `CURSAY_SPARKLE_PUBLIC_KEY`, and either an `APPLE_NOTARY_KEYCHAIN_PROFILE` or the three Apple notary credential variables, then run:

```bash
./scripts/release-dmg.sh
SPARKLE_PRIVATE_KEY_FILE=/secure/path/to/eddsa-private-key ./scripts/generate-appcast.sh
```

The release script notarizes and staples both the app and signed DMG, validates Gatekeeper, and emits SHA-256 files. GitHub Actions performs the same flow for `v*` tags and uploads the DMG, ZIP, checksums, and signed `appcast.xml` to the matching GitHub Release.
