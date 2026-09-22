from __future__ import annotations

import unittest
import urllib.error
from unittest import mock

from cursay.updates import (
    NoReleaseAvailable,
    UpdateError,
    fetch_latest_release,
    is_newer_version,
    release_from_payload,
)


class UpdateTests(unittest.TestCase):
    def test_version_comparison_handles_different_component_counts(self) -> None:
        self.assertTrue(is_newer_version("1.3.0", "1.2.0"))
        self.assertTrue(is_newer_version("2.0", "1.9.9"))
        self.assertFalse(is_newer_version("1.2", "1.2.0"))
        self.assertFalse(is_newer_version("1.1.9", "1.2.0"))

    def test_release_payload_selects_versioned_archive_and_checksum(self) -> None:
        payload = {
            "tag_name": "v1.3.0",
            "html_url": "https://github.com/shadoprizm/cursay/releases/tag/v1.3.0",
            "assets": [
                {
                    "name": "cursay-1.3.0.tar.gz",
                    "browser_download_url": "https://github.com/example/archive",
                },
                {
                    "name": "cursay-1.3.0.tar.gz.sha256",
                    "browser_download_url": "https://github.com/example/checksum",
                },
                {"name": "unrelated.txt", "browser_download_url": "https://github.com/example/other"},
            ],
        }

        release = release_from_payload(payload)

        self.assertEqual(release.version, "1.3.0")
        self.assertEqual(release.archive_url, "https://github.com/example/archive")
        self.assertEqual(release.checksum_url, "https://github.com/example/checksum")
        self.assertTrue(release.can_install)

    def test_release_without_assets_can_still_link_to_release_page(self) -> None:
        release = release_from_payload(
            {
                "tag_name": "v1.3.0",
                "html_url": "https://github.com/shadoprizm/cursay/releases/tag/v1.3.0",
                "assets": [],
            }
        )
        self.assertFalse(release.can_install)

    def test_invalid_release_version_is_rejected(self) -> None:
        with self.assertRaises(UpdateError):
            release_from_payload(
                {
                    "tag_name": "latest",
                    "html_url": "https://github.com/shadoprizm/cursay/releases/latest",
                }
            )

    @mock.patch("urllib.request.urlopen")
    def test_missing_github_release_has_a_clear_state(self, urlopen: mock.Mock) -> None:
        urlopen.side_effect = urllib.error.HTTPError("https://example.test", 404, "Not Found", {}, None)

        with self.assertRaisesRegex(NoReleaseAvailable, "No published Cursay update"):
            fetch_latest_release()


if __name__ == "__main__":
    unittest.main()
