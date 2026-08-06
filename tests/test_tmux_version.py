from __future__ import annotations

import shutil
import subprocess
import unittest


@unittest.skipUnless(shutil.which("tmux"), "tmux not installed")
class TmuxVersionTest(unittest.TestCase):
    def test_tmux_version_exits_zero(self) -> None:
        result = subprocess.run(
            ["tmux", "-V"],
            capture_output=True,
        )
        self.assertEqual(result.returncode, 0)
        output = (result.stdout + result.stderr).decode()
        self.assertRegex(output, r"tmux \d+\.\d+")
