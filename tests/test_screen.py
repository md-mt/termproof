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
