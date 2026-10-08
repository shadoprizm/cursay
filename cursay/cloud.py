from __future__ import annotations

import json
import shutil
import socket
import subprocess
import time
import urllib.error
import urllib.request
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import APP_ID
from .stt import TranscriptionError, transcribe


class CloudError(RuntimeError):
    def __init__(self, message: str, *, status: int | None = None, code: str | None = None) -> None:
        super().__init__(message)
        self.status = status
        self.code = code


class SecureStorageUnavailable(CloudError):
    pass


def cloud_access_error(account: dict[str, Any]) -> CloudError | None:
    if (account.get("entitlement") is not True or account.get("plan") not in {"trial", "pro"}
            or int(account.get("allowance_seconds", 0)) <= 0):
        return CloudError(
            "Upgrade to Cursay Pro to use managed cloud transcription and Cloud Smart Polish.",
            status=402, code="subscription_required",
        )
    if int(account.get("remaining_seconds", 0)) <= 0:
        return CloudError(
            "Your cloud allowance is used up. Use Local Whisper or wait for your allowance to renew.",
            status=429, code="quota_exhausted",
        )
    return None


@dataclass
class CloudTokens:
    access_token: str
    access_expires_at: float
    refresh_token: str
    refresh_expires_at: float
    device_id: str


class SecretServiceStore:
    """Stores the token bundle only in GNOME Secret Service via libsecret."""

    def __init__(self, executable: str | None = None) -> None:
        self.executable = executable or shutil.which("secret-tool")

    def _command(self, *arguments: str, input_data: bytes | None = None) -> subprocess.CompletedProcess[bytes]:
        if not self.executable:
            raise SecureStorageUnavailable(
                "GNOME Secret Service is unavailable. Install libsecret-tools; Cursay will not store tokens as plaintext."
            )
        try:
            return subprocess.run(
                [self.executable, *arguments],
                input=input_data,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=10,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise SecureStorageUnavailable("GNOME Secret Service could not be reached.") from exc

    def load(self) -> CloudTokens | None:
        result = self._command("lookup", "application", APP_ID, "service", "cursay-cloud")
        if result.returncode != 0 or not result.stdout:
            return None
        try:
            value = json.loads(result.stdout.decode("utf-8"))
            return CloudTokens(
                access_token=value["access_token"],
                access_expires_at=float(value["access_expires_at"]),
                refresh_token=value["refresh_token"],
                refresh_expires_at=float(value["refresh_expires_at"]),
                device_id=value["device_id"],
            )
        except (UnicodeDecodeError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
            raise SecureStorageUnavailable("The saved Cursay Cloud credential is invalid. Sign in again.") from exc

    def save(self, tokens: CloudTokens) -> None:
        payload = json.dumps(tokens.__dict__, separators=(",", ":")).encode("utf-8")
        result = self._command(
            "store", "--label", "Cursay Cloud", "application", APP_ID, "service", "cursay-cloud",
            input_data=payload,
        )
        if result.returncode != 0:
            raise SecureStorageUnavailable("Cursay could not save tokens in GNOME Secret Service.")

    def clear(self) -> None:
        result = self._command("clear", "application", APP_ID, "service", "cursay-cloud")
        if result.returncode not in (0, 1):
            raise SecureStorageUnavailable("Cursay could not remove the saved cloud credential.")


class CloudClient:
    def __init__(self, base_url: str, store: SecretServiceStore | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.store = store or SecretServiceStore()

    def _request(
        self,
        path: str,
        *,
        method: str = "GET",
        body: dict[str, Any] | None = None,
        access_token: str | None = None,
        timeout: float = 30,
    ) -> dict[str, Any]:
        data = json.dumps(body).encode("utf-8") if body is not None else None
        headers = {"Accept": "application/json"}
        if data is not None:
            headers["Content-Type"] = "application/json"
        if access_token:
            headers["Authorization"] = f"Bearer {access_token}"
        request = urllib.request.Request(f"{self.base_url}{path}", data=data, headers=headers, method=method)
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                return json.load(response)
        except urllib.error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")[:500]
            code = None
            message = raw
            try:
                detail = json.loads(raw).get("error", {})
                code = detail.get("code")
                message = detail.get("message") or raw
            except (json.JSONDecodeError, AttributeError):
                pass
            raise CloudError(message, status=exc.code, code=code) from exc
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise CloudError(f"Cursay Cloud is unavailable: {exc}") from exc

    def begin_link(self) -> dict[str, Any]:
        return self._request(
            "/api/v1/device/authorizations",
            method="POST",
            body={"device_name": socket.gethostname() or "Ubuntu device", "platform": "ubuntu"},
        )

    def poll_link(self, device_code: str) -> CloudTokens | None:
        try:
            payload = self._request("/api/v1/device/token", method="POST", body={"device_code": device_code})
        except CloudError as exc:
            if exc.code == "authorization_pending":
                return None
            raise
        now = time.time()
        tokens = CloudTokens(
            access_token=str(payload["access_token"]),
            access_expires_at=now + float(payload["expires_in"]),
            refresh_token=str(payload["refresh_token"]),
            refresh_expires_at=now + float(payload["refresh_expires_in"]),
            device_id=str(payload["device_id"]),
        )
        self.store.save(tokens)
        return tokens

    def _refresh(self, tokens: CloudTokens) -> CloudTokens:
        if tokens.refresh_expires_at <= time.time():
            self.store.clear()
            raise CloudError("Your Cursay Cloud sign-in expired. Link this device again.", code="sign_in_expired")
        payload = self._request(
            "/api/v1/device/refresh", method="POST", body={"refresh_token": tokens.refresh_token}
        )
        now = time.time()
        updated = CloudTokens(
            access_token=str(payload["access_token"]),
            access_expires_at=now + float(payload["expires_in"]),
            refresh_token=str(payload["refresh_token"]),
            refresh_expires_at=now + float(payload["refresh_expires_in"]),
            device_id=tokens.device_id,
        )
        self.store.save(updated)
        return updated

    def tokens(self) -> CloudTokens:
        tokens = self.store.load()
        if tokens is None:
            raise CloudError("Link this device to a Cursay Pro account.", code="not_linked")
        if tokens.access_expires_at <= time.time() + 30:
            tokens = self._refresh(tokens)
        return tokens

    def account(self) -> dict[str, Any]:
        tokens = self.tokens()
        try:
            return self._request("/api/v1/account", access_token=tokens.access_token)
        except CloudError as exc:
            if exc.status != 401:
                raise
            tokens = self._refresh(tokens)
            return self._request("/api/v1/account", access_token=tokens.access_token)

    def transcribe(self, path: Path, language: str) -> dict[str, Any]:
        access_error = cloud_access_error(self.account())
        if access_error:
            raise access_error
        tokens = self.tokens()
        endpoint = f"{self.base_url}/api/v1/audio/transcriptions"
        key = str(uuid.uuid4())
        try:
            return transcribe(
                path, endpoint, "cursay-cloud", language, bearer_token=tokens.access_token, idempotency_key=key
            )
        except TranscriptionError as exc:
            if exc.status != 401:
                raise
            tokens = self._refresh(tokens)
            return transcribe(
                path, endpoint, "cursay-cloud", language, bearer_token=tokens.access_token, idempotency_key=key
            )

    def polish(self, text: str, style: str, grant: str) -> str:
        tokens = self.tokens()
        payload = self._request(
            "/api/v1/polish",
            method="POST",
            body={"cleaned_text": text, "style": style, "polish_grant": grant},
            access_token=tokens.access_token,
            timeout=90,
        )
        output = str(payload.get("text") or "").strip()
        if not output:
            raise CloudError("Smart Polish returned no text.")
        return output

    def revoke_and_sign_out(self) -> None:
        tokens = self.store.load()
        if tokens is not None:
            try:
                self._request(
                    f"/api/v1/devices/{tokens.device_id}", method="DELETE", access_token=tokens.access_token
                )
            except CloudError:
                pass
        self.store.clear()
