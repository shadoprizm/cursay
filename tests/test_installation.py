from __future__ import annotations

import subprocess
import unittest
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]


class InstallationTests(unittest.TestCase):
    def test_shell_scripts_have_valid_syntax(self) -> None:
        scripts = [
            PROJECT_DIR / "install.sh",
            PROJECT_DIR / "uninstall.sh",
            *sorted((PROJECT_DIR / "scripts").glob("*.sh")),
        ]
        result = subprocess.run(
            ["bash", "-n", *(str(path) for path in scripts)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_skip_backend_removes_an_existing_stt_unit(self) -> None:
        installer = (PROJECT_DIR / "install.sh").read_text(encoding="utf-8")
        skip_backend_block = installer.split('if [ "$install_backend" = false ]; then', 1)[1].split("fi", 1)[0]
        self.assertIn("systemctl --user disable cursay-stt.service", skip_backend_block)
        self.assertIn('rm -f -- "$systemd_dir/cursay-stt.service"', skip_backend_block)

    def test_backend_install_uses_the_hash_locked_dependency_set(self) -> None:
        installer = (PROJECT_DIR / "install.sh").read_text(encoding="utf-8")
        lock = (PROJECT_DIR / "backend" / "requirements.lock").read_text(encoding="utf-8")
        direct_requirements = [
            line.strip()
            for line in (PROJECT_DIR / "backend" / "requirements.txt").read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]

        self.assertIn("--require-hashes", installer)
        self.assertIn('backend/requirements.lock', installer)
        for requirement in direct_requirements:
            self.assertIn(f"{requirement} \\", lock)
        self.assertNotIn(">=", lock)


if __name__ == "__main__":
    unittest.main()
