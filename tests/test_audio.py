from __future__ import annotations

import unittest
from pathlib import Path

from cursay.audio import PipeWireRecorder


class AudioTests(unittest.TestCase):
    def test_record_command_uses_supported_pipewire_role_option(self) -> None:
        path = Path("/tmp/cursay-test.wav")
        command = PipeWireRecorder._record_command("/usr/bin/pw-record", path)

        self.assertEqual(command[0], "/usr/bin/pw-record")
        self.assertEqual(command[-1], str(path))
        self.assertIn("--media-role", command)
        self.assertEqual(command[command.index("--media-role") + 1], "Communication")
        self.assertNotIn("--properties", command)


if __name__ == "__main__":
    unittest.main()
