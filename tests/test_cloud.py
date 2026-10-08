from __future__ import annotations

import io
import json
import time
import unittest
from unittest.mock import patch

from cursay.cloud import CloudClient, CloudError, CloudTokens, SecretServiceStore, SecureStorageUnavailable


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
