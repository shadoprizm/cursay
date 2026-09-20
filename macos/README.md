# Cursay for Mac

This is the native macOS companion to the Ubuntu Cursay app. It uses SwiftUI, AppKit, AVFoundation, and the existing OpenAI-compatible Cursay transcription API.

## Included in the first native build

- Menu-bar app and full dashboard
- Global **Ctrl + Space** push-to-talk shortcut with a **Ctrl + Option + Space** fallback when macOS reserves the preferred shortcut
- Native 16 kHz mono microphone recording
- Automatic copy and optional paste into the previously active app
- Professional, casual, code, and raw cleanup modes
- Searchable private history and local insights
- Configurable transcription endpoint, model, and language
- Optional audio retention and launch at login

## Build on your Mac

Requirements: macOS 13 or newer and Xcode 15 or newer.

```bash
cd macos
./scripts/build-app.sh
open dist/Cursay.app
```

The script runs the Swift tests, builds a release binary, assembles `Cursay.app`, and applies a local ad-hoc signature.

On first launch, macOS will ask for microphone access. Automatic paste also needs Cursay enabled in **System Settings → Privacy & Security → Accessibility**. Cursay copies the result even when Accessibility access is unavailable.

## Transcription service

The default endpoint is:

```text
http://127.0.0.1:8765/v1/audio/transcriptions
```

It matches the Python backend in this repository. To run that private local service in a Terminal window:

```bash
cd /path/to/cursay
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r backend/requirements.txt
python -m uvicorn server:app --app-dir backend --host 127.0.0.1 --port 8765
```

The first transcription downloads the configured Whisper model. Leave the service running while using this first Mac build. You can instead change the endpoint in Cursay Settings to another compatible service; audio is then governed by that service's privacy policy. The health check expects `/health` at the service root.

## Distribution

The local build is intentionally ad-hoc signed. Sharing it with other Macs requires an Apple Developer ID certificate, hardened-runtime signing, and Apple notarization. The source does not enable the App Sandbox because global paste automation depends on Accessibility permission.
