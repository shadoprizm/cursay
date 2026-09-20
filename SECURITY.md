# Security policy

## Reporting a vulnerability

Please do not open a public issue for a vulnerability that could expose microphone audio, transcript history, clipboard contents, or arbitrary input control.

Use GitHub's private vulnerability reporting feature for this repository. Include the affected version, Ubuntu release, reproduction steps, and the smallest safe diagnostic excerpt possible. Do not attach real dictations, recordings, credentials, or personal clipboard data.

## Security boundaries

Cursay is designed around narrow desktop permissions:

- Microphone capture is performed through PipeWire.
- The portal receives only the user-approved shortcut.
- Automatic paste uses a private `ydotoold` socket with mouse support disabled.
- A narrowly scoped udev rule grants the active local desktop user access to `/dev/uinput`; it does not make the device world-writable.
- Clipboard contents are read back and compared before `Ctrl+V` is sent.
- Audio is deleted after transcription unless retention is explicitly enabled.

A custom remote transcription or polishing endpoint is outside Cursay's local privacy boundary.
