from __future__ import annotations

import unittest
import warnings
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
    @staticmethod
    def _write_cast(run_dir: Path) -> None:
        run_dir.mkdir()
        # Create a minimal cast file so replay_cast doesn't crash.
        (run_dir / "session.cast").write_text(
            '{"version":2,"width":100,"height":30}\n'
            '[0.1,"o","hello\\n"]\n',
            encoding="utf-8",
        )

    @patch("termproof.evidence.resolve_agg", return_value=None)
    def test_render_artifacts_omits_video_when_no_agg(self, resolve_agg) -> None:
        """Video must be omitted gracefully when no agg is available."""
        from termproof.evidence import render_artifacts
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run"
            self._write_cast(run_dir)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                artifacts = render_artifacts(run_dir, render_video=True, video_fps=60)
            self.assertNotIn("video", artifacts)

    @patch("termproof.evidence.resolve_agg", return_value=None)
    def test_render_artifacts_warns_when_video_requested_without_tools(self, resolve_agg) -> None:
        """An explicit --video request must not be silently dropped."""
        from termproof.evidence import render_artifacts
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run"
            self._write_cast(run_dir)
            with self.assertWarns(UserWarning) as caught:
                artifacts = render_artifacts(run_dir, render_video=True, video_fps=60)

        message = str(caught.warning)
        self.assertIn("agg", message)
        self.assertIn("--video", message)
        self.assertIn("skipping video", message)
        self.assertNotIn("video", artifacts)

    @patch("termproof.evidence.resolve_agg", return_value=None)
    def test_render_artifacts_no_warning_when_video_not_requested(self, resolve_agg) -> None:
        """No warning should be emitted when video was not requested."""
        from termproof.evidence import render_artifacts
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run"
            self._write_cast(run_dir)
            with warnings.catch_warnings():
                warnings.simplefilter("error")
                artifacts = render_artifacts(run_dir, render_video=False, video_fps=60)
            self.assertNotIn("video", artifacts)


if __name__ == "__main__":
    unittest.main()
