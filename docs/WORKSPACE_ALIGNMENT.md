# Cursay workspace alignment — October 12, 2026

## Sources of truth

| Component | Canonical source | Role |
|---|---|---|
| Mac, Ubuntu, Windows, local speech helpers | [shadoprizm/cursay](https://github.com/shadoprizm/cursay), main | Native capture, local history/WPM, cloud linking, opt-in future-capture Memory sync |
| Website and managed account/Memory APIs | Separate private cloud repository | Browser workspace, account consent, saved thoughts, Ask Cursay, reviews, projects, analysis credits, confirmed vocabulary |

Separate repositories are intentional. Native clients use the same account API and consent/epoch contract.
They do not independently run the browser learning system. WPM is calculated from each device's local
history; this change does not upload usage statistics or create cross-device WPM totals.

## Audit findings

- GitHub native main was `3cfe061`, including Memory PRs #4/#5 and the Mac hotkey, cloud-access, and latency fixes.
- The ASTRA project folder `/home/shadoprizm/Documents/ChatGPT/Wispr Sync Clone` was on `codex/cost-insights` at `b697d47`, 15 commits behind. The first WPM implementation was made against this stale checkout.
- ASTRA's installed app was already Ubuntu 1.3.0, from the explicit Ubuntu preview release.
- The Mac's canonical folder `/Users/jratelle/Coding Projects/Cursay` was on current native main at `3cfe061`, but `/Applications/Cursay.app` was still 1.2.1 build 4.
- Default Mac and Windows bundle/project version values still said 1.2.1. These are corrected and now checked against the Python/native release version.
- The newest inspected cloud checkout is `/Users/jratelle/.codex/worktrees/cursay-release-cloud`, commit `e0a030a`. Its tree is clean and committed, but authentication to its private remote fails. No cloud source was copied into the public repository or overwritten.
- The inspected production configuration snapshot, dated October 11, contains no enabled Memory or paid top-up flag. The current release record states that production stored Memory is disabled pending owner verification of retention and disclosure.

## Reconciliation

WPM is integrated against current native main for all three platforms, using one shared test fixture for
weighted averages, missing durations, calendar windows and daylight saving time. Mac and Ubuntu expose
a Memory page linking to the account learning workspace; Windows exposes it from Insights and Settings.
Consent, private capture, app exclusions, deletion replay protection, and the future-only sync boundary stay in place.

Mac and Ubuntu owner builds include a source revision visible in the sidebar. Match that revision with
GitHub when diagnosing a missing feature. A current checkout alone does not mean the installed app is current.
The stable update channel remains 1.2.1 until a normal signed/public release is completed.

## Verification before updating owners

- Ubuntu: 91 unit tests, Python lint, shell syntax, isolated GTK startup passed before version-parity checks were added.
- Mac: 30 Swift tests passed with full Xcode; the release executable compiled.
- Windows: 6 portable tests passed; cross-compilation succeeded with no warnings or errors.
- Windows physical microphone, DPAPI, paste and installer acceptance still require a Windows machine.

## Remaining managed-service work

Stored Memory remains disabled until the storage-readiness/owner verification gates in
[release status](RELEASE_STATUS.md) and the private cloud recovery runbook are satisfied. Account consent
and future-capture sync must then be enabled explicitly by the owner. Existing history is never enrolled automatically.
Restoring private repository authentication is also required before its remote can be proven aligned with
the committed deployed source. Local/private backups must be retained in the meantime.
