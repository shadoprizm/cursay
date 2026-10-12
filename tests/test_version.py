from __future__ import annotations

import tomllib
import plistlib
import xml.etree.ElementTree as ET
import unittest
from pathlib import Path

from cursay import __version__


class VersionTests(unittest.TestCase):
    def test_native_bundle_versions_match_runtime(self) -> None:
        root = Path(__file__).resolve().parents[1]
        with (root / "macos/Resources/Info.plist").open("rb") as source:
            self.assertEqual(plistlib.load(source)["CFBundleShortVersionString"], __version__)
        windows = ET.parse(root / "windows/src/Cursay.Windows/Cursay.Windows.csproj")
        self.assertEqual(windows.findtext("./PropertyGroup/Version"), __version__)
        installer = (root / "windows/installer/Cursay.iss").read_text()
        self.assertIn(f'#define MyAppVersion "{__version__}"', installer)

    def test_runtime_and_package_versions_match(self) -> None:
        project_file = Path(__file__).resolve().parents[1] / "pyproject.toml"
        package_version = tomllib.loads(project_file.read_text(encoding="utf-8"))["project"]["version"]
        self.assertEqual(__version__, package_version)

    def test_release_version(self) -> None:
        self.assertEqual(__version__, "1.3.0")

    def test_backend_version_matches_runtime(self) -> None:
        backend_file = Path(__file__).resolve().parents[1] / "backend" / "server.py"
        self.assertIn(f'version="{__version__}"', backend_file.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
