# Cursay for Windows

Cursay's native Windows app provides system-wide push-to-talk dictation on Windows 10 version 1809 or newer and Windows 11.

## Install a release build

Run `Cursay-<version>-windows-x64-setup.exe`. The installer is per-user by default and does not request administrator access. Cursay starts in the notification area and reserves **Ctrl + Space** for push-to-talk.

The first local dictation downloads the English `base.en` Whisper model (about 150 MB). Settings, history, models, and any recordings you explicitly preserve are stored under `%LOCALAPPDATA%\Cursay`.

Windows asks for microphone access when Cursay records for the first time. If recording is blocked, enable **Microphone access** and **Let desktop apps access your microphone** under **Settings → Privacy & security → Microphone**.

## Build from source

Requirements:

- Windows 10 or 11, x64
- .NET 8 SDK
- Python 3.12 x64
- Inno Setup 6

From PowerShell at the repository root:

```powershell
.\windows\scripts\build.ps1
```

The script runs the .NET tests, publishes a self-contained app, packages the local faster-whisper backend, builds the installer, and writes a SHA-256 checksum under `windows\artifacts`.

For a quick app-only development build:

```powershell
.\windows\scripts\build.ps1 -SkipBackend -SkipInstaller
```

The local backend listens only on `127.0.0.1:8765`. A different OpenAI-compatible transcription endpoint can be selected in Cursay Settings.

## Release limitations

- The release is currently x64-only.
- The installer and app are unsigned until a Windows code-signing certificate is configured; Windows SmartScreen may show a warning on downloaded builds.
- Ctrl + Space must be available as a system-wide shortcut.
- Cursay cannot paste into an elevated application when Cursay itself is running without elevation; the transcript remains on the clipboard in that case.
