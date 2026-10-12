# Cursay release status — 2026-10-12 UTC

The browser workspace is live at https://cursay.com/app. Ubuntu 1.3.0 is available as an explicit [preview release](https://github.com/shadoprizm/cursay/releases/tag/ubuntu-v1.3.0), with a versioned source archive and checksum. The owner installation has been upgraded with settings, history, and unpublished terminal fixes preserved. The stable updater channel still points to 1.2.1.

## Availability

| Capability | Current state |
|---|---|
| Browser dictation, microphone meter, 20-minute limit, retained audio, WAV download and unfinished-section retry | Production workspace |
| Native future-capture Memory sync, private capture, approved vocabulary, secure linking | In native main and Ubuntu preview; off by default |
| Saved thoughts, projects, Ask Cursay, reviews and analysis credits | Implemented; production stored Memory remains disabled pending storage-readiness verification |
| Paid credit top-ups | Disabled in production; live merchant readiness remains open |
| macOS and Windows distribution | Build CI passed; signed Mac distribution and installed Windows acceptance remain separate gates |

Native source is merged through PR #5. PR #4 is also merged. The cloud source is a separate private repository; its authentication remains unavailable on the inspected machines. The release is preserved in committed isolated worktrees and a private Git bundle; no cloud remote was overwritten.

## Verification and recovery

- 78 Ubuntu tests, Python lint, shell syntax, isolated GTK widget startup, and a fresh isolated install passed. The installer bundles the Ubuntu credential helper without plaintext token fallback.
- Native Linux, Mac build and Windows build checks passed in GitHub CI. These do not establish physical microphone, paste, notarization, or Windows DPAPI acceptance.
- Cloud validation passed 72 tests, TypeScript and production build. Four optional external-database tests remain skipped.
- An encrypted metadata-only production backup was taken before additive Memory/credit migrations.
- An independent private object-store journal is required before production Memory writes. Signed immutable metadata records contain IDs, epochs and revisions, never dictated text, project names, audio or model output. Journal failure refuses the content mutation. Forget transactions are bound to the epoch recorded in the journal.
- A real Neon logical restore drill restored four fictional captures into a disconnected database. Applying the independent journal removed deleted, forgotten and stale-edited content while retaining the valid capture. Restored consent was disabled. Provider PITR itself was not exercised.
- Recovery requires a fresh externally signed checkpoint with all Memory writers stopped. Missing, stale, incomplete or corrupt authority fails closed. Recovery clears derived analyses and project metadata, rotates consent epochs, and requires fresh consent before reconnecting clients. See the private cloud recovery runbook for exact commands.

## Remaining owner and release gates

The database console requires owner email verification before the actual backup/history settings can be inspected. Stored Memory stays disabled until the maximum residual retention period is verified and disclosed. The owner must also link Ubuntu to the account and separately opt into Memory and future-capture sync. Physical recording/paste acceptance and the continuous browser endurance check remain open.

The Ubuntu installation has an independent protected rollback copy of the old app, previous app, settings, history database and service units. Application rollback must preserve journal metadata, epochs and tombstones; never restore an old database directly into a running service.
