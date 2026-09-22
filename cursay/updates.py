from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any


LATEST_RELEASE_API = "https://api.github.com/repos/shadoprizm/cursay/releases/latest"
MAX_ARCHIVE_BYTES = 250 * 1024 * 1024
MAX_CHECKSUM_BYTES = 16 * 1024
PROJECT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share")) / "cursay"
UPDATE_STATUS_FILE = DATA_DIR / "update-status.json"


class UpdateError(RuntimeError):
    """Raised when an update cannot be checked, verified, or installed."""


class NoReleaseAvailable(UpdateError):
    """Raised when the project does not have a published GitHub release yet."""


@dataclass(frozen=True)
class ReleaseInfo:
    version: str
    page_url: str
    archive_url: str | None
    checksum_url: str | None

    @property
    def can_install(self) -> bool:
        return bool(self.archive_url and self.checksum_url)


def _version_parts(version: str) -> tuple[int, ...]:
    normalized = version.removeprefix("v")
    if not re.fullmatch(r"\d+(?:\.\d+){1,3}", normalized):
        raise UpdateError(f"Unsupported release version: {version}")
    return tuple(int(part) for part in normalized.split("."))


def is_newer_version(candidate: str, current: str) -> bool:
    candidate_parts = _version_parts(candidate)
    current_parts = _version_parts(current)
    length = max(len(candidate_parts), len(current_parts))
    return candidate_parts + (0,) * (length - len(candidate_parts)) > current_parts + (0,) * (
        length - len(current_parts)
    )


def release_from_payload(payload: dict[str, Any]) -> ReleaseInfo:
    raw_tag = payload.get("tag_name")
    if not isinstance(raw_tag, str):
        raise UpdateError("The latest release did not include a version")
    version = raw_tag.removeprefix("v")
    _version_parts(version)

    page_url = payload.get("html_url")
    if not isinstance(page_url, str) or not page_url.startswith("https://"):
        raise UpdateError("The latest release did not include a valid release page")

    archive_name = f"cursay-{version}.tar.gz"
    checksum_name = f"{archive_name}.sha256"
    urls: dict[str, str] = {}
    assets = payload.get("assets", [])
    if isinstance(assets, list):
        for asset in assets:
            if not isinstance(asset, dict):
                continue
            name = asset.get("name")
            url = asset.get("browser_download_url")
            if name in (archive_name, checksum_name) and isinstance(url, str) and url.startswith("https://"):
                urls[name] = url
    return ReleaseInfo(
        version=version,
        page_url=page_url,
        archive_url=urls.get(archive_name),
        checksum_url=urls.get(checksum_name),
    )


def fetch_latest_release(timeout: float = 10) -> ReleaseInfo:
    request = urllib.request.Request(
        LATEST_RELEASE_API,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "Cursay update checker",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise NoReleaseAvailable("No published Cursay update is available yet.") from exc
        raise UpdateError(f"Could not check for updates: {exc}") from exc
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        raise UpdateError(f"Could not check for updates: {exc}") from exc
    if not isinstance(payload, dict):
        raise UpdateError("The release service returned an unexpected response")
    return release_from_payload(payload)


def launch_update(release: ReleaseInfo) -> None:
    if not release.can_install:
        raise UpdateError("This release does not include the files required for an automatic update")
    systemd_run = shutil.which("systemd-run")
    if systemd_run is None:
        raise UpdateError("Automatic updates require systemd-run")
    unit = f"cursay-update-{os.getpid()}"
    command = [
        systemd_run,
        "--user",
        "--collect",
        "--quiet",
        f"--unit={unit}",
        "--description=Cursay application update",
        sys.executable,
        str(Path(__file__).resolve()),
        "--install",
        release.version,
        release.archive_url or "",
        release.checksum_url or "",
    ]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=10, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise UpdateError(f"Could not start the updater: {exc}") from exc
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "systemd-run failed").strip()
        raise UpdateError(f"Could not start the updater: {detail}")


def _download(url: str, destination: Path, limit: int) -> None:
    request = urllib.request.Request(url, headers={"User-Agent": "Cursay updater"})
    total = 0
    try:
        with urllib.request.urlopen(request, timeout=30) as response, destination.open("wb") as output:
            while chunk := response.read(1024 * 1024):
                total += len(chunk)
                if total > limit:
                    raise UpdateError("The downloaded update was unexpectedly large")
                output.write(chunk)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise UpdateError(f"Could not download the update: {exc}") from exc


def _expected_checksum(checksum_file: Path) -> str:
    match = re.search(r"(?<![0-9a-fA-F])[0-9a-fA-F]{64}(?![0-9a-fA-F])", checksum_file.read_text())
    if match is None:
        raise UpdateError("The release checksum file is invalid")
    return match.group(0).lower()


def _write_status(success: bool, message: str) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    DATA_DIR.chmod(0o700)
    temporary = UPDATE_STATUS_FILE.with_suffix(".tmp")
    temporary.write_text(json.dumps({"success": success, "message": message}), encoding="utf-8")
    temporary.chmod(0o600)
    temporary.replace(UPDATE_STATUS_FILE)


def consume_update_status() -> tuple[bool, str] | None:
    try:
        payload = json.loads(UPDATE_STATUS_FILE.read_text(encoding="utf-8"))
        UPDATE_STATUS_FILE.unlink(missing_ok=True)
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict) or not isinstance(payload.get("message"), str):
        return None
    return bool(payload.get("success")), payload["message"]


def _start_services(include_backend: bool) -> None:
    services = ["cursay-input.service"]
    if include_backend:
        services.append("cursay-stt.service")
    services.append("cursay.service")
    subprocess.run(["systemctl", "--user", "start", *services], check=False, timeout=30)


def install_release(version: str, archive_url: str, checksum_url: str) -> None:
    _version_parts(version)
    if not archive_url.startswith("https://") or not checksum_url.startswith("https://"):
        raise UpdateError("Update downloads must use HTTPS")

    systemd_dir = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "systemd/user"
    include_backend = (systemd_dir / "cursay-stt.service").is_file()
    try:
        with tempfile.TemporaryDirectory(prefix="cursay-update-") as temporary_name:
            temporary = Path(temporary_name)
            archive = temporary / f"cursay-{version}.tar.gz"
            checksum = archive.with_suffix(archive.suffix + ".sha256")
            _download(archive_url, archive, MAX_ARCHIVE_BYTES)
            _download(checksum_url, checksum, MAX_CHECKSUM_BYTES)
            actual = hashlib.sha256(archive.read_bytes()).hexdigest()
            if actual != _expected_checksum(checksum):
                raise UpdateError("The downloaded update did not match its SHA-256 checksum")

            extracted = temporary / "extracted"
            extracted.mkdir()
            with tarfile.open(archive, "r:gz") as bundle:
                bundle.extractall(extracted, filter="data")
            installers = list(extracted.glob("*/install.sh"))
            if len(installers) != 1:
                raise UpdateError("The update archive did not contain a valid installer")
            arguments = ["bash", str(installers[0]), "--no-start"]
            if not include_backend:
                arguments.append("--skip-backend")
            result = subprocess.run(arguments, capture_output=True, text=True, timeout=1800, check=False)
            if result.returncode != 0:
                detail = (result.stderr or result.stdout or "installer failed").strip()
                raise UpdateError(f"The update installer failed: {detail[-500:]}")
        _write_status(True, f"Cursay was updated to version {version}.")
    except Exception as exc:
        message = str(exc) if isinstance(exc, UpdateError) else f"The update failed: {exc}"
        _write_status(False, message)
        raise
    finally:
        # The app exits after handing off to this transient unit. Bring the
        # installed services back even if download or verification failed.
        _start_services(include_backend)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Cursay update helper")
    parser.add_argument("--install", nargs=3, metavar=("VERSION", "ARCHIVE_URL", "CHECKSUM_URL"))
    arguments = parser.parse_args(argv)
    if arguments.install is None:
        parser.error("--install is required")
    try:
        install_release(*arguments.install)
    except Exception as exc:
        print(exc, file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
