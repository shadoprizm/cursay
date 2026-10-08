# Contributing to Cursay

Thanks for helping make private system-wide dictation better.

## Before opening an issue

- Search existing issues.
- Run `~/.local/opt/cursay/bin/cursay --check`.
- Include your operating system version and whether transcription, clipboard copy, or automatic paste failed.
- Never include dictated text, audio, API keys, or other private data in logs or screenshots.

## Development setup

Cursay targets Ubuntu GNOME on Wayland and uses GTK 4, Libadwaita, PipeWire, the Global Shortcuts portal, `wl-clipboard`, and `ydotool`.

```bash
git clone https://github.com/shadoprizm/cursay.git
cd cursay
ruff check cursay backend tests
bash -n install.sh uninstall.sh scripts/*.sh
/usr/bin/python3 -m unittest discover -s tests -v
xvfb-run -a /usr/bin/python3 bin/cursay --smoke-test
```

Use `./install.sh --skip-model` to test the installed desktop integration without downloading a model immediately.

The Windows app targets .NET 8 and Windows 10 version 1809 or newer. On Windows, run:

```powershell
dotnet test .\windows\Cursay.Windows.sln -c Release
.\windows\scripts\build.ps1
```

The full Windows build also requires Python 3.12 and Inno Setup 6. See [windows/README.md](windows/README.md).

The managed website/API is a separate Next.js project:

```bash
cd website
npm ci
npm test
npm run typecheck
npm run build
```

Use isolated development credentials and run `npm run db:migrate` before API tests. `npm run models:validate` checks configured Gateway model IDs; `npm run models:smoke -- /path/to/non-sensitive.wav` performs real ZDR inference and prints metadata only. Never use real dictations as fixtures or add content fields to the cloud schema/logs.

The desktop UI uses Ubuntu's system Python packages. PyPI dependencies for the bundled transcription backend are
declared in `backend/requirements.txt` and installed from the hash-verified `backend/requirements.lock`. After
changing a direct backend dependency, regenerate the lock for the supported Ubuntu/Python baseline:

```bash
uv pip compile --generate-hashes \
  --python-version 3.12 \
  --python-platform x86_64-manylinux_2_28 \
  backend/requirements.txt \
  --output-file backend/requirements.lock
```

## Pull requests

- Keep changes focused and explain the user-visible behavior.
- Add or update tests for logic changes.
- Preserve the fail-closed clipboard check: Cursay must never paste text until it has read back the exact new transcript.
- Do not replace the Global Shortcuts portal with global keyboard capture.
- On Windows, keep using `RegisterHotKey`; do not replace it with a keyboard hook.
- Do not introduce Remote Desktop, screen-capture, or pointer-control permissions for automatic paste.
- Confirm that long dictations wrap without expanding the application window.
- Keep all Stripe price selection server-side and treat signed webhooks as the sole subscription authority.
- Keep cloud persistence metadata-only; never log or persist audio, transcripts, polished text, or prompts.

By contributing, you agree that your work will be released under the MIT License.
