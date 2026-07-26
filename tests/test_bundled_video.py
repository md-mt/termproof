from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from termproof import evidence


class RenderMp4Tests(unittest.TestCase):
    @patch("termproof.evidence.find_ffmpeg", return_value="ffmpeg")
    @patch("termproof.evidence.subprocess.run")
    @patch("termproof.evidence.bundled_agg_path", return_value=Path("/wheel/agg"))
    def test_render_mp4_uses_bundled_agg_binary(self, bundled_agg_path, subprocess_run, find_ffmpeg) -> None:
        evidence.render_mp4(Path("input.cast"), Path("output.mp4"), fps=24)

        self.assertEqual(
            ["/wheel/agg", "--quiet", "--fps-cap", "24", "input.cast", "output.agg.gif"],
            subprocess_run.call_args_list[0].args[0],
        )


if __name__ == "__main__":
    unittest.main()
