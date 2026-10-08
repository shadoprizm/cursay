# Security policy

## Reporting a vulnerability

Please do not open a public issue for a vulnerability that could expose microphone audio, transcript history, clipboard contents, or arbitrary input control.

Use GitHub's private vulnerability reporting feature for this repository. Include the affected version, operating system, reproduction steps, and the smallest safe diagnostic excerpt possible. Do not attach real dictations, recordings, credentials, or personal clipboard data.

## Security boundaries

Cursay is designed around narrow desktop permissions:

- Microphone capture is performed through PipeWire.
- The portal receives only the user-approved shortcut.
- Automatic paste uses a private `ydotoold` socket with mouse support disabled.
- A narrowly scoped udev rule grants the active local desktop user access to `/dev/uinput`; it does not make the device world-writable.
- Clipboard contents are read back and compared before `Ctrl+V` is sent.
- Audio is deleted after transcription unless retention is explicitly enabled.
- On Windows, the shortcut uses `RegisterHotKey` and release-state polling rather than a global keyboard hook.
- The bundled Windows speech service listens only on the loopback interface, and automatic paste verifies the clipboard before sending `Ctrl+V`.
- Ubuntu Pro credentials are stored only through GNOME Secret Service; macOS Pro credentials use a This-Device-Only Keychain item. Neither client falls back to plaintext token storage.
- Managed API credentials remain server-side. Desktop access and refresh tokens are opaque, stored hashed in Neon, rotated on refresh, and invalidated by device revocation.
- Cloud transcription and polishing request per-call zero data retention through Vercel AI Gateway. Routing must fail rather than use a provider that cannot satisfy that setting.
- Cursay Cloud stores metadata needed for entitlement, quota, reliability, and cost accounting. It does not store microphone audio, transcripts, polished text, or prompts in Neon, Vercel Blob, analytics, or application logs.
- Stripe signature-verified webhooks—not checkout redirects—are the authority for paid access. Quota reservation and the three-request account limit are enforced against a locked database row.

A custom remote transcription or polishing endpoint is outside Cursay's local privacy boundary. The managed service's current processors and policies are listed at [cursay.com/subprocessors](https://cursay.com/subprocessors) and [cursay.com/privacy](https://cursay.com/privacy).
