from __future__ import annotations

import json
import mimetypes
import secrets
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any


class TranscriptionError(RuntimeError):
    pass


def _multipart(fields: dict[str, str], path: Path) -> tuple[bytes, str]:
    boundary = f"----Cursay{secrets.token_hex(16)}"
    chunks: list[bytes] = []
    for name, value in fields.items():
        chunks.extend(
            [
                f"--{boundary}\r\n".encode(),
                f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode(),
                str(value).encode("utf-8"),
                b"\r\n",
            ]
        )
    mime = mimetypes.guess_type(path.name)[0] or "audio/wav"
    chunks.extend(
        [
            f"--{boundary}\r\n".encode(),
            f'Content-Disposition: form-data; name="file"; filename="{path.name}"\r\n'.encode(),
            f"Content-Type: {mime}\r\n\r\n".encode(),
            path.read_bytes(),
            b"\r\n",
            f"--{boundary}--\r\n".encode(),
        ]
    )
    return b"".join(chunks), boundary


def transcribe(
    path: Path,
    endpoint: str,
    model: str,
    language: str = "en",
    timeout: float = 150.0,
) -> dict[str, Any]:
    if not path.is_file():
        raise TranscriptionError(f"Audio file does not exist: {path}")
    fields = {"model": model, "response_format": "json"}
    if language and language.lower() != "auto":
        fields["language"] = language
    body, boundary = _multipart(fields, path)
    request = urllib.request.Request(
        endpoint,
        data=body,
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            result = json.load(response)
    except urllib.error.HTTPError as exc:
        message = exc.read().decode("utf-8", errors="replace")[:500]
        raise TranscriptionError(f"Speech service returned HTTP {exc.code}: {message}") from exc
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
        raise TranscriptionError(f"Speech service is unavailable: {exc}") from exc

    if not isinstance(result, dict) or not isinstance(result.get("text"), str):
        raise TranscriptionError("Speech service returned an invalid response")
    return result


def health(endpoint: str, timeout: float = 3.0) -> dict[str, Any]:
    base = endpoint.rsplit("/v1/", 1)[0]
    try:
        with urllib.request.urlopen(f"{base}/health", timeout=timeout) as response:
            value = json.load(response)
        return value if isinstance(value, dict) else {"status": "invalid"}
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError):
        return {"status": "unavailable"}
