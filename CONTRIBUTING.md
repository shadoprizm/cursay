# Contributing to Cursay

Thanks for helping make dictation on Linux better.

## Before opening an issue

- Search existing issues.
- Run `~/.local/opt/cursay/bin/cursay --check`.
- Include your Ubuntu version, desktop environment, session type, and whether transcription, clipboard copy, or automatic paste failed.
- Never include dictated text, audio, API keys, or other private data in logs or screenshots.

## Development setup

Cursay targets Ubuntu GNOME on Wayland and uses GTK 4, Libadwaita, PipeWire, the Global Shortcuts portal, `wl-clipboard`, and `ydotool`.

```bash
git clone https://github.com/shadoprizm/cursay.git
cd cursay
/usr/bin/python3 -m unittest discover -s tests -v
/usr/bin/python3 bin/cursay --smoke-test
```

Use `./install.sh --skip-model` to test the installed desktop integration without downloading a model immediately.

## Pull requests

- Keep changes focused and explain the user-visible behavior.
- Add or update tests for logic changes.
- Preserve the fail-closed clipboard check: Cursay must never paste text until it has read back the exact new transcript.
- Do not replace the Global Shortcuts portal with global keyboard capture.
- Do not introduce Remote Desktop, screen-capture, or pointer-control permissions for automatic paste.
- Confirm that long dictations wrap without expanding the application window.

By contributing, you agree that your work will be released under the MIT License.
