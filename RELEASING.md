# Releasing Cursay

Releases are built from a clean `main` checkout after CI passes.

## Prepare

1. Update the version in `pyproject.toml`, `cursay/__init__.py`, `backend/server.py`, and
   `tests/test_version.py`.
2. Add the release notes to `CHANGELOG.md`.
3. If backend dependencies changed, regenerate `backend/requirements.lock` using the command in
   `CONTRIBUTING.md`.
4. Run the release checks:

   ```bash
   ruff check cursay backend tests
   bash -n install.sh uninstall.sh scripts/*.sh
   /usr/bin/python3 -m unittest discover -s tests -v
   xvfb-run -a /usr/bin/python3 bin/cursay --smoke-test
   git diff --check
   ```

   Changes under `macos/` must also pass the macOS workflow, which runs the Swift tests and assembles the app bundle on a GitHub-hosted Mac.

5. Test a fresh install and an upgrade on supported Ubuntu releases. Exercise local transcription,
   Smart Polish success and fallback, automatic paste, and `./install.sh --skip-backend`.

## Publish

After the release commit is merged and CI is green:

```bash
version=1.2.0
git switch main
git pull --ff-only
git tag -s "v${version}" -m "Cursay ${version}"
git push origin "v${version}"
git archive --format=tar.gz --prefix="cursay-${version}/" \
  --output="cursay-${version}.tar.gz" "v${version}"
sha256sum "cursay-${version}.tar.gz" > "cursay-${version}.tar.gz.sha256"
gh release create "v${version}" \
  "cursay-${version}.tar.gz" \
  "cursay-${version}.tar.gz.sha256" \
  --title "Cursay ${version}" \
  --notes-file <(sed -n "/^## ${version} /,/^## /p" CHANGELOG.md | sed '$d')
```

Confirm that the release page shows both artifacts and that the checksum matches the downloaded archive.
