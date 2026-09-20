<p align="center">
  <img src="assets/cursay.svg" width="128" height="128" alt="Cursay logo">
</p>

<h1 align="center">Cursay</h1>

<p align="center"><strong>Speak. Your words appear at the cursor.</strong></p>

<p align="center">
  Free, open-source, system-wide dictation for Ubuntu.<br>
  Local by default. No subscription. No Remote Desktop permission.
</p>

<p align="center">
  <a href="https://github.com/shadoprizm/cursay/actions/workflows/test.yml"><img alt="Tests" src="https://github.com/shadoprizm/cursay/actions/workflows/test.yml/badge.svg"></a>
  <a href="LICENSE"><img alt="MIT License" src="https://img.shields.io/badge/license-MIT-5bd6ae.svg"></a>
  <img alt="Ubuntu" src="https://img.shields.io/badge/Ubuntu-GNOME%20%2B%20Wayland-E95420?logo=ubuntu&logoColor=white">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.12%2B-3776AB?logo=python&logoColor=white">
</p>

---

Cursay turns your voice into text in the application you are already using. Hold the global shortcut, dictate for as long as you need, and release. Cursay transcribes the recording, cleans the text, verifies the clipboard, and pastes it at your cursor.

It is built for people who want a free, Linux-native Wispr Flow-style workflow without sending every thought through a subscription service.

## The whole interaction

1. Focus any text field.
2. Hold **Ctrl + Space**.
3. Speak naturally—even with pauses.
4. Release the keys.
5. Your dictation appears at the cursor.

Silence does not end the recording. Releasing the shortcut does.

## Why Cursay

- **System-wide:** dictate into browsers, chat apps, editors, terminals, and documents.
- **Local by default:** faster-whisper runs on your machine after a one-time model download.
- **Private history:** searchable transcripts stay in your Linux account.
- **Strict push-to-talk:** recording follows the key press instead of guessing when you finished speaking.
- **Safe automatic paste:** Cursay confirms that the clipboard contains the new transcript before sending `Ctrl+V`.
- **Wayland-native shortcut:** uses the Global Shortcuts portal instead of a keylogger.
- **No Remote Desktop access:** paste is performed through a private keyboard-only `uinput` device.
- **Useful cleanup:** professional, casual, code, and raw modes; optional filler-word removal.
- **Backend-friendly:** use the included local service or another OpenAI-compatible transcription endpoint.

## Install on Ubuntu

```bash
git clone https://github.com/shadoprizm/cursay.git
cd cursay
./install.sh
```

The installer is per-user. It places the application in `~/.local/opt/cursay`, installs user-level services, downloads `wl-clipboard` and `ydotool` from Ubuntu without installing them system-wide, and prepares the local Whisper runtime.

If GTK or the Python desktop bindings are missing, the installer will print the exact Ubuntu command needed. The local `base.en` model is roughly 150 MB and is downloaded once.

After installation, open **Cursay** from the app launcher. Ubuntu will show one Global Shortcut permission dialog. Approve the suggested shortcut or choose another one.

If the installer reports that `/dev/uinput` is protected, enable automatic paste with the included one-time system rule:

```bash
./scripts/enable-autopaste.sh
```

Ubuntu will request administrator authentication to install that narrow rule. Without it, transcription and clipboard copy still work; only the final automatic `Ctrl+V` is unavailable.

### Installer options

```bash
./install.sh --no-start       # install without starting Cursay
./install.sh --skip-model     # download Whisper on first local dictation
./install.sh --skip-backend   # use an existing compatible STT endpoint
```

## What happens to your data

| Data | Default location | Policy |
|---|---|---|
| Settings | `~/.config/cursay/config.json` | Private to your user |
| Dictation history | `~/.local/share/cursay/history.db` | Stored locally |
| Whisper model | `~/.local/share/cursay/models/` | Downloaded once |
| Temporary audio | `~/.cache/cursay/recordings/` | Deleted after transcription |
| Preserved audio | `~/.local/share/cursay/recordings/` | Only when explicitly enabled |

Existing Local Flow settings and history are copied automatically the first time Cursay runs. The original data is left untouched as a recovery copy.

## How it works

```text
Global shortcut
      ↓
PipeWire microphone capture
      ↓
Local faster-whisper (or your compatible endpoint)
      ↓
Meaning-preserving text cleanup
      ↓
Wayland clipboard write + read-back verification
      ↓
Private keyboard-only Ctrl+V
```

The shortcut portal can observe only Cursay's approved shortcut. The paste device is launched with mouse support disabled and sends only the four key events needed for `Ctrl+V`.

## Transcription choices

The included backend uses `faster-whisper` with the English `base.en` model on CPU. To use a different model or language, edit the Cursay STT user service or the settings file.

Cursay can also call an OpenAI-compatible `/v1/audio/transcriptions` endpoint. Set `stt_endpoint` and `stt_model` in `~/.config/cursay/config.json`. When you choose a remote endpoint, audio is governed by that provider's privacy policy; the included backend remains entirely local after its model is downloaded.

## Diagnostics

```bash
~/.local/opt/cursay/bin/cursay --check
~/.local/opt/cursay/bin/cursay --record-test
systemctl --user status cursay.service cursay-input.service cursay-stt.service
journalctl --user -u cursay.service -n 100 --no-pager
```

### Shortcut does nothing

Open Cursay, go to **Settings → Change shortcut**, and approve the shortcut in Ubuntu's dialog. The application must be installed before the portal can associate the permission with Cursay.

### Text is copied but not pasted

Run `./scripts/enable-autopaste.sh`, then check `systemctl --user status cursay-input.service`. Cursay will never paste an older clipboard value: if clipboard verification fails, it stops after copying the new text.

### A Remote Desktop dialog appears

Cursay does not use the Remote Desktop portal. An old experimental Local Flow process may still be running; reinstalling Cursay disables and archives those old user services.

## Development

The desktop application intentionally relies mostly on Ubuntu's system Python packages. Run the tests with:

```bash
/usr/bin/python3 -m unittest discover -s tests -v
/usr/bin/python3 bin/cursay --smoke-test
```

The local STT service has its own small dependency set in `backend/requirements.txt`.

Contributions are welcome. Read [CONTRIBUTING.md](CONTRIBUTING.md) before opening a pull request, and use [SECURITY.md](SECURITY.md) for vulnerability reports.

## Uninstall

```bash
./uninstall.sh
```

Uninstalling preserves settings and dictation history. The script prints the data directory if you also want to erase it manually.

## License

Cursay is available under the [MIT License](LICENSE).
