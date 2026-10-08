from __future__ import annotations

import io
import json
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from cursay.cloud import CloudClient, CloudError, CloudTokens, SecretServiceStore, SecureStorageUnavailable, cloud_access_error


class MemoryStore:
    def __init__(self, tokens: CloudTokens | None = None) -> None:
        self.value = tokens

    def load(self):
        return self.value

    def save(self, value):
        self.value = value

    def clear(self):
        self.value = None


class CloudTests(unittest.TestCase):
    def test_free_expired_or_inconsistent_accounts_cannot_upload_audio(self) -> None:
        client = CloudClient("https://example.test", store=MemoryStore())  # type: ignore[arg-type]
        accounts = [
            {"plan": "free", "entitlement": False, "allowance_seconds": 0, "remaining_seconds": 0},
            {"plan": "pro", "entitlement": False, "allowance_seconds": 90000, "remaining_seconds": 90000},
            {"plan": "trial", "entitlement": False, "allowance_seconds": 7200, "remaining_seconds": 7200},
            {"plan": "free", "entitlement": True, "allowance_seconds": 90000, "remaining_seconds": 90000},
            {},
        ]
        for account in accounts:
            with self.subTest(account=account), patch.object(client, "account", return_value=account), patch("cursay.cloud.transcribe") as upload:
                with self.assertRaises(CloudError) as caught:
                    client.transcribe(Path("unused.wav"), "en")
                self.assertEqual(caught.exception.status, 402)
                upload.assert_not_called()

    def test_exhausted_paid_allowance_is_not_an_upgrade_requirement(self) -> None:
        error = cloud_access_error({"plan": "pro", "entitlement": True, "allowance_seconds": 90000, "remaining_seconds": 0})
        self.assertIsNotNone(error)
        self.assertEqual(error.code, "quota_exhausted")

    def test_active_trial_and_pro_accounts_can_transcribe(self) -> None:
        tokens = CloudTokens("a", time.time() + 1000, "r", time.time() + 2000, "device")
        client = CloudClient("https://example.test", store=MemoryStore(tokens))  # type: ignore[arg-type]
        for plan in ("trial", "pro"):
            account = {"plan": plan, "entitlement": True, "allowance_seconds": 7200, "remaining_seconds": 60}
            with self.subTest(plan=plan), patch.object(client, "account", return_value=account), patch("cursay.cloud.transcribe", return_value={"text": "hello"}) as upload:
                self.assertEqual(client.transcribe(Path("fixture.wav"), "en"), {"text": "hello"})
                self.assertEqual(upload.call_args.kwargs["bearer_token"], "a")

    def test_never_falls_back_to_plaintext_when_secret_tool_is_missing(self) -> None:
        with self.assertRaises(SecureStorageUnavailable):
            SecretServiceStore(executable="/definitely/missing/secret-tool").save(CloudTokens("a", 1, "r", 2, "d"))

    def test_refresh_token_is_rotated_and_saved(self) -> None:
        store = MemoryStore(CloudTokens("old", 0, "refresh-old", time.time() + 1000, "device"))
        client = CloudClient("https://example.test", store=store)  # type: ignore[arg-type]
        response = io.BytesIO(json.dumps({
            "access_token": "new", "expires_in": 900, "refresh_token": "refresh-new", "refresh_expires_in": 2000
        }).encode())
        with patch("urllib.request.urlopen", return_value=response):
            tokens = client.tokens()
        self.assertEqual(tokens.access_token, "new")
        self.assertEqual(store.value.refresh_token, "refresh-new")

    def test_pending_device_code_is_not_an_error(self) -> None:
        client = CloudClient("https://example.test", store=MemoryStore())  # type: ignore[arg-type]
        error = CloudError("pending", status=428, code="authorization_pending")
        with patch.object(client, "_request", side_effect=error):
            self.assertIsNone(client.poll_link("code"))

    def test_sign_out_clears_tokens_even_when_revoke_fails(self) -> None:
        store = MemoryStore(CloudTokens("a", time.time() + 100, "r", time.time() + 100, "device"))
        client = CloudClient("https://example.test", store=store)  # type: ignore[arg-type]
        with patch.object(client, "_request", side_effect=CloudError("offline")):
            client.revoke_and_sign_out()
        self.assertIsNone(store.value)


if __name__ == "__main__":
    unittest.main()
