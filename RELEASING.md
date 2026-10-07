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

   Windows changes must also pass the Windows workflow. Its artifact contains the x64 installer and checksum.

   Changes under `macos/` must also pass the macOS workflow, which runs the Swift tests and assembles the app bundle on a GitHub-hosted Mac.

   Changes under `website/` must pass `npm test`, `npm run typecheck`, `npm run build`, `npm run models:validate`, and a non-sensitive `npm run models:smoke -- <fixture.wav>`. Apply all Neon migrations to staging before deploying a protected Vercel preview.

5. Test a fresh install and an upgrade on supported Ubuntu releases. Exercise local transcription,
   Smart Polish success and fallback, automatic paste, and `./install.sh --skip-backend`.
6. In Stripe test mode, exercise new trial, successful renewal, failed payment plus 72-hour grace, cancel-at-period-end, full refund, duplicate webhook, and out-of-order webhook cases. Confirm checkout redirects alone never grant an entitlement.
7. Link Ubuntu and macOS devices to staging and verify access-token refresh, revocation, three-device enforcement, the 120-minute trial cap, the 1,500-minute monthly window, concurrent reservation limits, and local fallback.

## Required release secrets

The macOS tag job requires `MACOS_CERTIFICATE_P12_BASE64`, `MACOS_CERTIFICATE_PASSWORD`, `MACOS_KEYCHAIN_PASSWORD`, `MACOS_CODESIGN_IDENTITY`, `SPARKLE_PRIVATE_KEY`, `SPARKLE_PUBLIC_KEY`, `APPLE_ID`, `APPLE_APP_SPECIFIC_PASSWORD`, and `APPLE_TEAM_ID` in GitHub Actions.

Production Vercel must have the Clerk, Neon, Stripe, AI Gateway, fixed Stripe price, portal configuration, webhook-signing, model ID, and token-signing variables described by `website/.env.example`. Store secrets as Vercel secrets, not repository variables. The production Vercel plan must support per-request Gateway ZDR.

## Publish

After the release commit is merged and CI is green:

```bash
version=1.2.1
git switch main
git pull --ff-only
git tag -s "v${version}" -m "Cursay ${version}"
git push origin "v${version}"
git archive --format=tar.gz --prefix="cursay-${version}/" \
  --output="cursay-${version}.tar.gz" "v${version}"
sha256sum "cursay-${version}.tar.gz" > "cursay-${version}.tar.gz.sha256"
gh release view "v${version}" >/dev/null 2>&1 || \
  gh release create "v${version}" \
    --title "Cursay ${version}" \
    --notes-file <(sed -n "/^## ${version} /,/^## /p" CHANGELOG.md | sed '$d')
gh release upload "v${version}" \
  "cursay-${version}.tar.gz" \
  "cursay-${version}.tar.gz.sha256" \
  "Cursay-${version}-windows-x64-setup.exe" \
  "Cursay-${version}-windows-x64-setup.exe.sha256" \
  --clobber
```

Download the `cursay-windows-x64` workflow artifact before running `gh release create`, and copy its two files into the working directory. The macOS tag job creates or augments this release with the notarized DMG, signed ZIP/appcast, and checksums. Confirm that the release page shows all platform packages, each checksum matches, the DMG passes Gatekeeper on a clean Mac, and Sparkle can discover the release.

Promote the tested Vercel build only after checking the production webhook endpoint and fixed Stripe price IDs. Public Pro launch additionally requires live-mode Stripe credentials/prices/webhook, an owned production Clerk instance, the configured Vercel Pro ZDR entitlement, and successful signed Ubuntu/macOS smoke tests.
