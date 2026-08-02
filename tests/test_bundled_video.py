from __future__ import annotations

import tempfile
import unittest
import warnings
from pathlib import Path
from unittest.mock import MagicMock, patch

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
        """Video must be omitted gracefully when the built-in agg is unavailable."""
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run"
            self._write_cast(run_dir)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                artifacts = evidence.render_artifacts(run_dir, render_video=True, video_fps=60)
            self.assertNotIn("video", artifacts)

    @patch("termproof.evidence.resolve_agg", return_value=None)
    def test_render_artifacts_warns_when_video_requested_without_tools(self, resolve_agg) -> None:
        """An explicit --video request must not be silently dropped."""
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run"
            self._write_cast(run_dir)
            with self.assertWarns(UserWarning) as caught:
                artifacts = evidence.render_artifacts(run_dir, render_video=True, video_fps=60)

        message = str(caught.warning)
        self.assertIn("agg", message)
        self.assertIn("--video", message)
        self.assertIn("skipping video", message)
        self.assertNotIn("video", artifacts)

    @patch("termproof.evidence.resolve_agg", return_value=None)
    def test_render_artifacts_no_warning_when_video_not_requested(self, resolve_agg) -> None:
        """No warning should be emitted when video was not requested."""
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run"
            self._write_cast(run_dir)
            with warnings.catch_warnings():
                warnings.simplefilter("error")
                artifacts = evidence.render_artifacts(run_dir, render_video=False, video_fps=60)
            self.assertNotIn("video", artifacts)

    # -- adversarial plugin-boundary regression tests -----------------------

    @patch("termproof.evidence._resolve_ffmpeg", return_value=None)
    @patch("termproof.evidence.resolve_agg", return_value=None)
    def test_custom_backend_runs_when_agg_and_ffmpeg_unavailable(
        self, resolve_agg, resolve_ffmpeg
    ) -> None:
        """A caller-supplied VideoBackend must run even when no host video tools exist."""
        backend = MagicMock()
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run"
            self._write_cast(run_dir)
            with warnings.catch_warnings():
                warnings.simplefilter("error")  # custom path must stay quiet
                artifacts = evidence.render_artifacts(
                    run_dir, render_video=True, video_fps=60, video_backend=backend
                )
        backend.render.assert_called_once()
        self.assertIn("video", artifacts)

    @patch("termproof.evidence._resolve_ffmpeg", return_value=None)
    @patch("termproof.evidence.resolve_agg", return_value="/wheel/agg")
    def test_custom_backend_runs_when_ffmpeg_unavailable_but_agg_present(
        self, resolve_agg, resolve_ffmpeg
    ) -> None:
        """A supplied backend must not be skipped merely because ffmpeg is absent."""
        backend = MagicMock()
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run"
            self._write_cast(run_dir)
            with warnings.catch_warnings():
                warnings.simplefilter("error")
                artifacts = evidence.render_artifacts(
                    run_dir, render_video=True, video_fps=60, video_backend=backend
                )
        backend.render.assert_called_once()
        self.assertIn("video", artifacts)

    # -- built-in backend distinction regression tests -----------------------

    @patch("termproof.evidence._resolve_ffmpeg", return_value=None)
    @patch("termproof.evidence.resolve_agg", return_value=None)
    def test_builtin_backend_warns_and_omits_when_tools_missing(
        self, resolve_agg, resolve_ffmpeg
    ) -> None:
        """The built-in agg_ffmpeg backend must warn + omit when tools are absent.

        Unlike a caller-supplied custom plugin, the built-in backend cannot
        satisfy a --video request on a host without agg/ffmpeg; it must not
        record a nonexistent video artifact.
        """
        from termproof.builtin_video import AggFfmpegBackend

        backend = AggFfmpegBackend()
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run"
            self._write_cast(run_dir)
            with self.assertWarns(UserWarning) as caught:
                artifacts = evidence.render_artifacts(
                    run_dir, render_video=True, video_fps=60, video_backend=backend
                )
        self.assertNotIn("video", artifacts)
        message = str(caught.warning)
        self.assertIn("agg", message)
        self.assertIn("--video", message)

    @patch("termproof.evidence.find_ffmpeg", return_value="ffmpeg")
    @patch("termproof.evidence.subprocess.run")
    @patch("termproof.evidence.resolve_agg", return_value="/wheel/agg")
    def test_builtin_backend_renders_when_tools_present(
        self, resolve_agg, subprocess_run, find_ffmpeg
    ) -> None:
        """The built-in agg_ffmpeg backend still records video when tools exist."""
        from termproof.builtin_video import AggFfmpegBackend

        backend = AggFfmpegBackend()
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run"
            self._write_cast(run_dir)
            artifacts = evidence.render_artifacts(
                run_dir, render_video=True, video_fps=60, video_backend=backend
            )
        self.assertIn("video", artifacts)
        self.assertTrue(subprocess_run.called)

    # -- helper unit tests --------------------------------------------------

    @patch("termproof.evidence._resolve_ffmpeg", return_value=None)
    @patch("termproof.evidence.resolve_agg", return_value=None)
    def test_missing_video_tools_reports_agg_and_ffmpeg(self, resolve_agg, resolve_ffmpeg) -> None:
        self.assertEqual(evidence._missing_video_tools(), ["agg", "ffmpeg"])

    @patch("termproof.evidence._resolve_ffmpeg", return_value="/usr/bin/ffmpeg")
    @patch("termproof.evidence.resolve_agg", return_value="/wheel/agg")
    def test_missing_video_tools_empty_when_all_present(self, resolve_agg, resolve_ffmpeg) -> None:
        self.assertEqual(evidence._missing_video_tools(), [])

    @patch("termproof.evidence.find_ffmpeg", side_effect=RuntimeError("no ffmpeg"))
    def test_resolve_ffmpeg_returns_none_when_find_raises(self, find_ffmpeg) -> None:
        self.assertIsNone(evidence._resolve_ffmpeg())

    @patch("termproof.evidence.find_ffmpeg", return_value="/usr/bin/ffmpeg")
    def test_resolve_ffmpeg_returns_path(self, find_ffmpeg) -> None:
        self.assertEqual(evidence._resolve_ffmpeg(), "/usr/bin/ffmpeg")


if __name__ == "__main__":
    unittest.main()
