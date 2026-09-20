from __future__ import annotations

import os
import shutil
import signal
import subprocess
import time
import wave
from datetime import datetime
from pathlib import Path

from .config import RECORDINGS_DIR, TEMP_DIR, ensure_directories


class AudioError(RuntimeError):
    pass


class PipeWireRecorder:
    def __init__(self) -> None:
        ensure_directories()
        self.process: subprocess.Popen[bytes] | None = None
        self.path: Path | None = None
        self.started_at: float | None = None

    @property
    def recording(self) -> bool:
        return self.process is not None and self.process.poll() is None

    def start(self) -> Path:
        if self.recording:
            raise AudioError("A recording is already in progress")
        executable = shutil.which("pw-record")
        if not executable:
            raise AudioError("PipeWire recorder (pw-record) is not installed")

        TEMP_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        self.path = TEMP_DIR / f"dictation-{timestamp}.wav"
        command = [
            executable,
            "--rate",
            "16000",
            "--channels",
            "1",
            "--format",
            "s16",
            "--properties",
            "media.name=Cursay Dictation media.role=Communication",
            str(self.path),
        ]
        try:
            self.process = subprocess.Popen(
                command,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                start_new_session=True,
            )
        except OSError as exc:
            raise AudioError(f"Could not start PipeWire recording: {exc}") from exc
        self.started_at = time.monotonic()
        time.sleep(0.08)
        if self.process.poll() is not None:
            details = (self.process.stderr.read() if self.process.stderr else b"").decode(
                "utf-8", errors="replace"
            )
            self.process = None
            raise AudioError(details.strip() or "PipeWire recording stopped unexpectedly")
        return self.path

    def stop(self, preserve: bool = False) -> tuple[Path, float]:
        if not self.process or not self.path:
            raise AudioError("No recording is in progress")
        process = self.process
        path = self.path
        duration = max(0.0, time.monotonic() - (self.started_at or time.monotonic()))
        self.process = None
        self.path = None
        self.started_at = None

        if process.poll() is None:
            try:
                os.killpg(process.pid, signal.SIGINT)
                process.wait(timeout=3)
            except (ProcessLookupError, subprocess.TimeoutExpired):
                process.terminate()
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=2)

        if not path.exists() or path.stat().st_size <= 44:
            details = (process.stderr.read() if process.stderr else b"").decode(
                "utf-8", errors="replace"
            )
            path.unlink(missing_ok=True)
            raise AudioError(details.strip() or "No microphone audio was captured")

        try:
            with wave.open(str(path), "rb") as stream:
                frame_count = stream.getnframes()
        except wave.Error as exc:
            path.unlink(missing_ok=True)
            raise AudioError(f"The recorded audio is invalid: {exc}") from exc
        if frame_count == 0:
            path.unlink(missing_ok=True)
            raise AudioError("The microphone recording was empty")
        path.chmod(0o600)

        if preserve:
            RECORDINGS_DIR.mkdir(parents=True, exist_ok=True)
            destination = RECORDINGS_DIR / path.name
            path.replace(destination)
            path = destination
        return path, duration

    def cancel(self) -> None:
        if self.process and self.process.poll() is None:
            try:
                os.killpg(self.process.pid, signal.SIGINT)
                self.process.wait(timeout=2)
            except (ProcessLookupError, subprocess.TimeoutExpired):
                self.process.kill()
        if self.path:
            self.path.unlink(missing_ok=True)
        self.process = None
        self.path = None
        self.started_at = None
