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
            *sorted((PROJECT_DIR / "macos" / "scripts").glob("*.sh")),
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

    def test_macos_bundle_contains_and_launches_local_backend(self) -> None:
        build_app = (PROJECT_DIR / "macos" / "scripts" / "build-app.sh").read_text(encoding="utf-8")
        app_model = (PROJECT_DIR / "macos" / "Sources" / "CursayMac" / "AppModel.swift").read_text(
            encoding="utf-8"
        )
        backend_manager = (
            PROJECT_DIR / "macos" / "Sources" / "CursayMac" / "LocalBackendManager.swift"
        ).read_text(encoding="utf-8")

        self.assertIn('build-backend.sh', build_app)
        self.assertIn('$RESOURCES_DIR/CursaySTT', build_app)
        self.assertIn("install_name_tool -add_rpath '@executable_path/../Frameworks'", build_app)
        build_backend = (PROJECT_DIR / "macos" / "scripts" / "build-backend.sh").read_text(encoding="utf-8")
        self.assertIn("--require-hashes", build_backend)
        self.assertIn("backend/requirements.lock", build_backend)
        self.assertIn('localBackend.ensureRunning', app_model)
        self.assertIn('Bundle.main.resourceURL', backend_manager)
        self.assertIn('--parent-pid', backend_manager)


if __name__ == "__main__":
    unittest.main()
