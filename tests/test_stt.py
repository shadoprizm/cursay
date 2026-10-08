from __future__ import annotations

import io
import json
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

from cursay.stt import TranscriptionError, transcribe


class _Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()


class TranscriptionClientTests(unittest.TestCase):
    def test_cloud_headers_and_multipart_contract(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            audio = Path(directory) / "recording.wav"
            audio.write_bytes(b"RIFF-test-audio")
            response = _Response(json.dumps({"text": "hello", "polish_grant": "grant"}).encode())
            with patch("urllib.request.urlopen", return_value=response) as request:
                result = transcribe(
                    audio,
                    "https://cursay.example/api/v1/audio/transcriptions",
                    "cursay-cloud",
                    bearer_token="access-token",
                    idempotency_key="recording-id",
                )
            sent = request.call_args.args[0]
            self.assertEqual(sent.get_header("Authorization"), "Bearer access-token")
            self.assertEqual(sent.get_header("Idempotency-key"), "recording-id")
            self.assertIn(b'name="file"; filename="recording.wav"', sent.data)
            self.assertEqual(result["polish_grant"], "grant")

    def test_structured_service_error_preserves_fallback_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            audio = Path(directory) / "recording.wav"
            audio.write_bytes(b"RIFF-test-audio")
            body = json.dumps({
                "error": {"code": "quota_exhausted", "message": "Allowance used", "fallback": "local"}
            }).encode()
            error = urllib.error.HTTPError("https://example.test", 429, "limit", {}, io.BytesIO(body))
            with patch("urllib.request.urlopen", side_effect=error):
                with self.assertRaises(TranscriptionError) as raised:
                    transcribe(audio, "https://example.test", "cursay-cloud")
            self.assertEqual(raised.exception.status, 429)
            self.assertEqual(raised.exception.code, "quota_exhausted")
            self.assertEqual(raised.exception.fallback, "local")


if __name__ == "__main__":
    unittest.main()
