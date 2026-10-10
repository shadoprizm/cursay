# Cursay Memory release candidate

Prepared 2026-10-10. Implemented in isolated cloud and desktop worktrees on `codex/cursay-memory`. **Not deployed, migrated, installed, or publicly released.** Ordinary dictation and the existing production site remain the running service.

## What this candidate provides

- Authenticated `/app`: browser microphone capture, current-tab audio retry/discard, editable transcript and copy, optional Smart Polish, private capture, saved thoughts, search, source links, Ask Cursay, daily/weekly reviews, projects/goals, explicit vocabulary corrections, reviewable suggestions, export, pause, and forget.
- Browser STT shares account quotas, without creating a desktop device. Clerk sessions require same-origin mutations. Desktop Memory uses the existing account-bound device tokens.
- Mac, Ubuntu, and Windows: separate opt-in future-capture sync, account/consent-bound outboxes, tombstones before uploads, private capture excluding local history/audio/Memory, app exclusions, and cached user-approved vocabulary for Local Whisper. Mac and Ubuntu can also apply confirmed vocabulary through opted-in Cloud Smart Polish. Raw and Code modes do not receive vocabulary hints.
- Windows: managed cloud account linking, DPAPI-protected credentials and outbox, refresh, revocation, paid/quota preflight, and local fallback.
- Luna (`openai/gpt-6-luna`) organizes account text through Gateway ZDR requests. Speech and Smart Polish keep their current providers. ID-only durable workflows do not return text or model output into workflow history. Late inference cannot restore an edited/deleted source or a forgotten consent epoch.
- Each analysis reserves a conservative cost allowance before contacting the model. The included provider-cost budget is $2 USD per account per UTC calendar month. At the limit, analysis pauses; save/search/export/delete continue. Failed or abandoned requests retain the reserved charge because actual upstream cost is uncertain. There are no automatic overages.
- Questions respect opt-out, a three-per-day maximum, and a 30-minute cooldown. Suggested actions and vocabulary wait for user review. Nothing sends messages or acts in another service.

## Deliberate boundaries

The first version retrieves up to 30 relevant captures for a question or review, with a bounded prompt. It does not train a new model or fine-tune Luna. Original and edited capture text are preserved separately until deletion. Audio is never saved to Memory. Browser retries temporarily retain audio only in the current tab.

Past desktop history is never imported automatically. A separately consented historical-import preview, scheduled unattended reviews, embeddings, and richer longitudinal summaries are not in this candidate. Desktop insights, search, projects, and confirmations are managed in the browser workspace; native clients capture and sync. Ubuntu app exclusions fail closed when active-app identity is unavailable, including GNOME Wayland. This can make all captures private when an exclusion list is configured. Existing unpublished Astra focus/paste work was preserved and not incorporated without reconciliation.

## Evidence recorded

- Cloud: PostgreSQL-compatible in-memory migrations and privacy/ownership/race/budget tests; normal service tests; TypeScript and production Next build.
- Mac: app compilation and 28 Swift tests with the installed Xcode toolchain. No application replacement, Keychain mutation, microphone recording, or update publication.
- Ubuntu: full unit suite in an isolated `/tmp` validation directory on Astra; existing checkout and installed runtime untouched. Python lint passes.
- Windows: app build succeeds with no warnings/errors; four existing portable tests pass on the Mac's .NET 10 runtime using explicit major-version roll-forward. Native Windows DPAPI, microphone, linking and paste acceptance, installer execution, and Windows CI are still required.
- Luna: a real synthetic-capture Gateway call returned valid structured output and valid source IDs in 5.687 seconds; 494 input and 213 output tokens, estimated $0.0001559. This is one integration smoke, not a quality benchmark.
- Browser visual/interaction checks use an explicitly labelled local synthetic fixture. They verify controls and the actual AudioWorklet/PCM path using generated audio. Physical microphone permission and authenticated cloud persistence are separate staging acceptance checks.
- Latest production source was discovered during work: SEO commit `1c569da11f06d8aee8ab7849e5992a1d4b5ce5ad`, deployment `dpl_63xSoFqKjaEd8E7pzG5jtk5dEeS2`. Its guides, metadata, redirects and Search Console work were merged into this candidate. Recheck again before promotion.

## Concrete next release steps

1. Obtain the local ASTRA policy gateway's exact `ASTRA_RED_AUTHORIZATION` for staging database creation/migration and deployment. `/Users/jratelle/AGENTS.md` classifies databases and public exposure as RED. This session has no policy-gateway tool or supplied marker. Code and local/isolated tests are prepared before requesting this final authorization.
2. Recheck all repository/worktree owners and current production deployment. The private cloud Git remote rejected authentication on the Mac and Astra; preserve this limitation, reconcile its latest remote before any push, and do not replace another worker's source. Current verified production source is available locally.
3. Provision isolated staging credentials and database. Apply all migrations there, including `0004_memory.sql`; never use production credentials for integration tests. Validate empty/new accounts, existing accounts, web actor quota accounting, and access expiry. Migration is additive; do not drop old tables.
4. Build/deploy a protected Vercel staging candidate. Set `CURSAY_MEMORY_ENABLED=1` only in staging. Check workflow runtime authorization and retries, actual Clerk consent, real capture/save/reload/search, source-linked answers, confirmed vocabulary, pause/forget/edit during inference, offline tombstones, account switching, budget exhaustion, and every supported native client. Confirm provider errors and platform logs contain no transcript/prompt/output.
5. Verify Neon backup/history retention and the deletion restoration procedure before enabling customers. Record the actual maximum residual backup period in the public privacy policy. Database backups are not considered immediately purged by a normal live deletion.
6. Confirm a backup restore cannot resurrect forgotten accounts/captures: export current consent epochs and content-free deletion markers to a separately retained private deletion ledger before any restore; restore into an isolated branch; apply the ledger to clear deleted text/projects/items/jobs and retain only valid current source revisions/epochs; verify the restored candidate against the ledger; only then reconnect clients. An older database backup must never become its own deletion authority. Fail closed if the independent ledger is unavailable. Test this procedure with synthetic data. No backups or deletion ledger have been provisioned in this session.
7. Stage the exact production build with `vercel deploy --prod --skip-domain`, verify it under authenticated protection, and promote that tested deployment only after the above gates pass. Keep the recorded previous deployment for rollback. The new browser STT routes require the nullable web actor migration even if Memory is disabled.
8. Run the established macOS/Windows release workflows and Ubuntu fresh/upgrade acceptance. Preserve unrelated Astra unpublished work; do not install over it. Publish signed/notarized platform artifacts through the normal release process after CI and acceptance.

## Rollback

Before rollout, deleting these new branches/worktrees does not alter the live service. After rollout, set `CURSAY_MEMORY_ENABLED=0` to stop new Memory processing, then restore the prior Vercel deployment if necessary. Keep additive tables, deletion epochs/tombstones, and cost metadata; never roll back the database to an older state that restores deleted content. Unlinking a native client clears credentials and its Memory outbox; original local history has a separate deletion control. Preserve signed prior native installers for an app rollback.
