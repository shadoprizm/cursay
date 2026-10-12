from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from cursay.build_info import build_label, capture_build_info, read_build_info, runtime_digest


class BuildInfoTests(unittest.TestCase):
    def git(self, root: Path, *args: str) -> str:
        return subprocess.check_output(["git", "-C", str(root), *args], text=True, stderr=subprocess.DEVNULL).strip()

    def test_clean_and_edited_source_have_distinct_build_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "cursay").mkdir()
            code = root / "cursay/app.py"
            code.write_text("original source")
            self.git(root, "init")
            self.git(root, "add", "cursay/app.py")
            self.git(root, "-c", "user.name=Build Test", "-c", "user.email=build@example.invalid", "commit", "-m", "Fixture")
            clean = capture_build_info(root)
            self.assertEqual(clean["source_revision"], self.git(root, "rev-parse", "HEAD"))
            self.assertFalse(clean["source_dirty"])
            self.assertNotIn("local changes", build_label(clean))
            code.write_text("edited source")
            edited = capture_build_info(root)
            self.assertTrue(edited["source_dirty"])
            self.assertNotEqual(edited["source_digest"], clean["source_digest"])
            self.assertIn("local changes", build_label(edited))
            self.assertIn(edited["source_digest"][:8], build_label(edited))
            self.git(root, "add", "cursay/app.py")
            self.git(root, "-c", "user.name=Build Test", "-c", "user.email=build@example.invalid", "commit", "-m", "Edit")
            (root / "cursay/new.py").write_text("untracked source")
            self.assertTrue(capture_build_info(root)["source_dirty"])

    def test_source_archives_receive_fingerprint_without_claiming_a_commit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "cursay").mkdir()
            (root / "cursay/app.py").write_text("source")
            info = capture_build_info(root)
            self.assertEqual(info["source_revision"], "")
            self.assertIsNone(info["source_dirty"])
            self.assertIn("unversioned", build_label(info))
            (root / "cursay/build-info.json").write_text(json.dumps(info))
            (root / "cursay/__pycache__").mkdir()
            (root / "cursay/__pycache__/app.pyc").write_bytes(b"compiled")
            self.assertEqual(runtime_digest(root), info["source_digest"])

    def test_legacy_and_malformed_metadata_load_without_breaking_startup(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "build-info.json"
            self.assertEqual(read_build_info(path), {})
            for contents in ("bad json", "null", "[]"):
                path.write_text(contents)
                self.assertEqual(read_build_info(path), {})
            path.write_text('{"source_revision": "abcdef0123"}')
            self.assertEqual(build_label(read_build_info(path)), "Build abcdef0")


if __name__ == "__main__":
    unittest.main()
