from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from PIL import Image

from termproof.builtin_renderers import PngRenderer
from termproof.config import VerifierConfig
from termproof.evidence import render_artifacts
from termproof.models import StepResult


class PngRendererTest(unittest.TestCase):
    def test_png_renderer_writes_png_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "final.png"
            PngRenderer().render("hello png", path, cols=80, rows=24)

            with Image.open(path) as image:
                self.assertEqual("PNG", image.format)
                self.assertGreaterEqual(image.width, 320)
                self.assertGreaterEqual(image.height, 160)

    def test_only_a_newline_starts_a_new_row(self) -> None:
        # `str.splitlines` breaks at every one of these, which drew each of them
        # as the same image as "a\nb" (#243).
        separators = ("\r", "\x0b", "\x0c", "\x1c", "\x1d", "\x1e", "\x85", "\u2028", "\u2029")
        with tempfile.TemporaryDirectory() as tmp:
            reference = self._png(Path(tmp), "a\nb")
            for separator in separators:
                with self.subTest(separator=separator):
                    self.assertNotEqual(reference, self._png(Path(tmp), f"a{separator}b"))

    def test_a_crlf_screen_draws_the_same_image_as_an_lf_one(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            reference = self._png(Path(tmp), "a\nb\n")
            self.assertEqual(reference, self._png(Path(tmp), "a\r\nb\r\n"))

    def test_rows_past_the_screen_height_are_not_drawn(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(
                self._png(Path(tmp), "a\nb", rows=2),
                self._png(Path(tmp), "a\nb\nc", rows=2),
            )
            self.assertNotEqual(
                self._png(Path(tmp), "a\nb", rows=3),
                self._png(Path(tmp), "a\nb\nc", rows=3),
            )

    def _png(self, directory: Path, text: str, rows: int = 24) -> bytes:
        path = directory / "screen.png"
        PngRenderer().render(text, path, cols=80, rows=rows)
        return path.read_bytes()

    def test_png_renderer_registered_in_builtin_config(self) -> None:
        config = VerifierConfig.builtin()
        self.assertEqual(
            "termproof.builtin_renderers:PngRenderer",
            config.screen_renderers["png"],
        )

    def test_render_artifacts_uses_renderer_extension(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            run_dir = Path(tmp) / "run"
            run_dir.mkdir()
            (run_dir / "session.cast").write_text(
                '{"version":2,"width":80,"height":24}\n'
                '[0.1,"o","hello png\\n"]\n',
                encoding="utf-8",
            )

            artifacts = render_artifacts(
                run_dir,
                render_video=False,
                steps=[StepResult("wait", True, "ok", "hello png")],
                screen_renderer=PngRenderer(),
            )

            self.assertTrue(artifacts["screenshot"].endswith("final.png"))
            self.assertTrue(Path(artifacts["screenshot"]).is_file())
            self.assertTrue((run_dir / "steps" / "01-wait.png").is_file())


if __name__ == "__main__":
    unittest.main()
