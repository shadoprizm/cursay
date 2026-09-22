from __future__ import annotations

import io
import json
import unittest
import urllib.error
from unittest.mock import patch

from cursay.cleanup import PolishError, clean_transcript, polish_transcript, should_polish


class CleanupTests(unittest.TestCase):
    def test_professional_removes_clear_fillers(self) -> None:
        text, meta = clean_transcript("um, send the report to Jordan by five", "professional", True)
        self.assertEqual(text, "Send the report to Jordan by five.")
        self.assertEqual([value.lower() for value in meta["fillers_removed"]], ["um"])

    def test_raw_is_untouched_except_outer_space(self) -> None:
        text, meta = clean_transcript("  uh keep this exactly  ", "raw", True)
        self.assertEqual(text, "uh keep this exactly")
        self.assertEqual(meta["fillers_removed"], [])

    def test_code_converts_spoken_symbols(self) -> None:
        text, _ = clean_transcript("print open paren hello close paren new line", "code", False)
        self.assertEqual(text, "print(hello)\n")

    def test_smart_polish_is_limited_to_prose_modes(self) -> None:
        self.assertTrue(should_polish("professional", True))
        self.assertTrue(should_polish("casual", True))
        self.assertTrue(should_polish("prompt", True))
        self.assertFalse(should_polish("code", True))
        self.assertFalse(should_polish("raw", True))
        self.assertFalse(should_polish("professional", False))

    def test_polish_uses_distinct_style_instruction(self) -> None:
        response = io.BytesIO(
            json.dumps({"choices": [{"message": {"content": "Edited text."}}]}).encode("utf-8")
        )
        with patch("urllib.request.urlopen", return_value=response) as urlopen:
            result = polish_transcript("original", "casual", "http://localhost/v1/chat/completions", "model")

        self.assertEqual(result, "Edited text.")
        request = urlopen.call_args.args[0]
        payload = json.loads(request.data)
        self.assertIn("friendly conversational prose", payload["messages"][1]["content"])
        self.assertEqual(payload["messages"][0]["role"], "system")

    def test_prompt_mode_requests_an_adaptive_ready_to_use_prompt(self) -> None:
        response = io.BytesIO(
            json.dumps({"choices": [{"message": {"content": "Create three concise names."}}]}).encode("utf-8")
        )
        with patch("urllib.request.urlopen", return_value=response) as urlopen:
            result = polish_transcript(
                "I need three short product names",
                "prompt",
                "http://localhost/v1/chat/completions",
                "model",
            )

        self.assertEqual(result, "Create three concise names.")
        request = urlopen.call_args.args[0]
        prompt = json.loads(request.data)["messages"][1]["content"]
        self.assertIn("ready-to-use AI prompt", prompt)
        self.assertIn("For a simple request, use one concise paragraph", prompt)
        self.assertIn("Do not add a role, requirement, constraint, example, fact, or output format", prompt)

    def test_polish_does_not_rewrite_raw_or_code(self) -> None:
        with patch("urllib.request.urlopen") as urlopen:
            self.assertEqual(
                polish_transcript("leave me alone", "raw", "http://localhost/v1/chat/completions", "model"),
                "leave me alone",
            )
            self.assertEqual(
                polish_transcript("print(value)", "code", "http://localhost/v1/chat/completions", "model"),
                "print(value)",
            )
        urlopen.assert_not_called()

    def test_polish_failure_is_visible_to_the_caller(self) -> None:
        with patch("urllib.request.urlopen", side_effect=urllib.error.URLError("offline")):
            with self.assertRaisesRegex(PolishError, "basic cleanup"):
                polish_transcript("original", "professional", "http://localhost/v1/chat/completions", "model")


if __name__ == "__main__":
    unittest.main()
