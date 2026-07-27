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
