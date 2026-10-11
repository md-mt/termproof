from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from PIL import Image

from termproof.attributed import attributed_screen_from_text
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

    def test_a_control_character_takes_the_column_the_grid_gives_it(self) -> None:
        # Drawn straight from the text, each of these took a column the grid
        # never gave it (#243). The grid's own rule is the terminal one
        # (#249): "\r" and "\x08" send the cursor back over the "a" and the
        # "b" overwrites it, the rest of C0 takes a cell of its own — so the
        # image is the image of "b" for the two cursor controls and the
        # image of the three-cell grid for the others, not, as it was while
        # the grid dropped them, the image of "ab".
        with tempfile.TemporaryDirectory() as tmp:
            for cols in (2, 80):
                plain = self._png(Path(tmp), "ab", cols=cols)
                overwritten = self._png(Path(tmp), "b", cols=cols)
                for control in ("\r", "\x08"):
                    with self.subTest(control=control, cols=cols):
                        self.assertEqual(
                            overwritten, self._png(Path(tmp), f"a{control}b", cols=cols)
                        )
                for control in ("\x07", "\x0b", "\x0c", "\x1c", "\x1d", "\x1e", "\x1b", "\x7f"):
                    text = f"a{control}b"
                    grid = attributed_screen_from_text(text, columns=cols, rows=24)
                    with self.subTest(control=control, cols=cols):
                        self.assertEqual(
                            self._png(Path(tmp), "\n".join(grid.text_lines()), cols=cols),
                            self._png(Path(tmp), text, cols=cols),
                        )
                        if cols == 80:
                            self.assertNotEqual(plain, self._png(Path(tmp), text, cols=cols))

    def test_the_image_is_the_image_of_the_grid_text(self) -> None:
        # "\r" sends the cursor back over the "a", so two columns hold just
        # "b". Every other separator here takes the second column itself and
        # the "b" falls past the edge: the C0 controls since #249, and
        # "\x85", "\u2028" and "\u2029", which are not C0 controls, all along.
        separators = (
            "\r", "\x07", "\x0b", "\x0c", "\x1c", "\x1d", "\x1e", "\x85", "\u2028", "\u2029",
        )  # fmt: skip
        held = {
            2: ["b"] + [f"a{control}" for control in separators[1:]],
            80: None,
        }
        with tempfile.TemporaryDirectory() as tmp:
            for cols in (2, 80):
                for position, separator in enumerate(separators):
                    text = f"a{separator}b"
                    with self.subTest(separator=separator, cols=cols):
                        grid = attributed_screen_from_text(text, columns=cols, rows=24)
                        expected = held[cols]
                        if expected is not None:
                            self.assertEqual([expected[position]], grid.text_lines())
                        self.assertEqual(
                            self._png(Path(tmp), "\n".join(grid.text_lines()), cols=cols),
                            self._png(Path(tmp), text, cols=cols),
                        )

    def test_a_tab_is_drawn_as_the_blanks_up_to_its_stop(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(
                self._png(Path(tmp), "a" + " " * 7 + "b"),
                self._png(Path(tmp), "a\tb"),
            )

    def test_a_row_ends_at_the_column_count_in_cells(self) -> None:
        # Three double-width glyphs are six cells: four columns hold two of them.
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(
                self._png(Path(tmp), "\u65e5\u672c", cols=4),
                self._png(Path(tmp), "\u65e5\u672c\u8a9e", cols=4),
            )
            self.assertNotEqual(
                self._png(Path(tmp), "\u65e5\u672c", cols=6),
                self._png(Path(tmp), "\u65e5\u672c\u8a9e", cols=6),
            )

    def _png(self, directory: Path, text: str, rows: int = 24, cols: int = 80) -> bytes:
        path = directory / "screen.png"
        PngRenderer().render(text, path, cols=cols, rows=rows)
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
