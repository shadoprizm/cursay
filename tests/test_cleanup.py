from __future__ import annotations

import unittest

from cursay.cleanup import clean_transcript


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


if __name__ == "__main__":
    unittest.main()
