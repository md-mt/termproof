from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from termproof import evidence


class RenderMp4Tests(unittest.TestCase):
    @patch("termproof.evidence.find_ffmpeg", return_value="ffmpeg")
    @patch("termproof.evidence.subprocess.run")
    @patch("termproof.evidence.resolve_agg", return_value="/wheel/agg")
    def test_render_mp4_uses_bundled_agg_binary(self, resolve_agg, subprocess_run, find_ffmpeg) -> None:
        evidence.render_mp4(Path("input.cast"), Path("output.mp4"), fps=24)

        self.assertEqual(
            ["/wheel/agg", "--quiet", "--fps-cap", "24", "input.cast", "output.agg.gif"],
            subprocess_run.call_args_list[0].args[0],
        )


class ResolveAggFallbackTests(unittest.TestCase):
    @patch("termproof.evidence.resolve_agg", return_value=None)
    def test_render_artifacts_skips_video_when_no_agg(self, resolve_agg) -> None:
        """Video rendering should be silently skipped when no agg is available."""
        from termproof.evidence import render_artifacts
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run"
            run_dir.mkdir()
            # Create a minimal cast file so replay_cast doesn't crash
            cast_path = run_dir / "session.cast"
            cast_path.write_text(
                '{"version":2,"width":100,"height":30}\n'
                '[0.1,"o","hello\\n"]\n',
                encoding="utf-8",
            )
            artifacts = render_artifacts(run_dir, render_video=True, video_fps=60)
            self.assertNotIn("video", artifacts)


if __name__ == "__main__":
    unittest.main()
