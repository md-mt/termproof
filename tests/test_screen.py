from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from xml.etree import ElementTree

from termproof.cast import CastRecorder
from termproof.screen import render_svg, replay_cast, replay_cast_attributed


class ScreenTest(unittest.TestCase):
    def test_replay_cast_reads_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cast_path = Path(tmp) / "session.cast"
            with CastRecorder(cast_path, 80, 24, ["demo"]) as recorder:
                recorder.output("hello\r\nworld")
            text, cols, rows = replay_cast(cast_path)
            self.assertEqual(80, cols)
            self.assertEqual(24, rows)
            self.assertIn("hello", text)
            self.assertIn("world", text)

    def test_replay_cast_attributed_keeps_colour(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cast_path = Path(tmp) / "session.cast"
            with CastRecorder(cast_path, 80, 24, ["demo"]) as recorder:
                recorder.output("\x1b[31mred\x1b[0m")
            screen, cols, rows = replay_cast_attributed(cast_path)
            self.assertEqual((80, 24), (cols, rows))
            self.assertTrue(screen.to_text().startswith("red"))
            self.assertEqual("red", screen.rows[0][0].fg)
            self.assertEqual("default", screen.rows[0][3].fg)

    def test_dim_does_not_survive_the_cast_replay_path(self) -> None:
        """Known limitation, pinned so the claim cannot quietly come back.

        pyte 0.8.2's ``Char`` has no ``dim``/``faint`` field -- its attributes
        are (data, fg, bg, bold, italics, underscore, strikethrough, reverse,
        blink) -- so SGR 2 is consumed by the emulator and never reaches
        ``_cell_from_pyte_char``. This is the path `final.svg` and the
        `attributed_rsvg` video use, so dim is lost on both, and the SVG carries
        no ``opacity``. Supporting it means modelling SGR 2 in the emulator
        layer, not in this package. See docs/evidence-quality.md.
        """
        with tempfile.TemporaryDirectory() as tmp:
            cast_path = Path(tmp) / "session.cast"
            with CastRecorder(cast_path, 80, 24, ["demo"]) as recorder:
                recorder.output("\x1b[2mdim\x1b[0m \x1b[1mbold\x1b[0m")
            screen, cols, rows = replay_cast_attributed(cast_path)
            self.assertFalse(screen.rows[0][0].dim, "pyte gained a dim field; carry it through")
            # Not a blanket failure of the path: bold from the same cast survives.
            self.assertTrue(screen.rows[0][4].bold)

            svg_path = Path(tmp) / "final.svg"
            from termproof.builtin_renderers import SvgRenderer

            SvgRenderer().render_attributed(screen, svg_path, cols, rows)
            self.assertNotIn("opacity", svg_path.read_text(encoding="utf-8"))

    def test_dim_does_survive_when_the_grid_is_built_from_sgr_text(self) -> None:
        """The limitation is pyte's, not the model's.

        Bounding it from the other side keeps the pin honest: a grid parsed
        straight from SGR text carries dim and renders it.
        """
        with tempfile.TemporaryDirectory() as tmp:
            svg_path = Path(tmp) / "screen.svg"
            render_svg("\x1b[2mdim", svg_path, 80, 24)
            self.assertIn('opacity="0.65"', svg_path.read_text(encoding="utf-8"))

    def test_render_svg_writes_terminal_screenshot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            svg_path = Path(tmp) / "final.svg"
            render_svg("hello <tui>", svg_path, 80, 24)
            svg = svg_path.read_text(encoding="utf-8")
            self.assertIn("<svg", svg)
            # One <text> per cell, so the escaped glyph appears on its own rather
            # than inside a whole-line run.
            self.assertIn(">&lt;<", svg)
            self.assertEqual(10, svg.count("<text "))
            ElementTree.fromstring(svg)

    def test_render_svg_carries_ansi_colour_through(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            svg_path = Path(tmp) / "final.svg"
            render_svg("\x1b[31mred", svg_path, 80, 24)
            self.assertIn('fill="#ff7b72"', svg_path.read_text(encoding="utf-8"))
