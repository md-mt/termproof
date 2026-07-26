from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from termproof.cast import CastRecorder
from termproof.screen import render_svg, replay_cast


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

    def test_render_svg_writes_terminal_screenshot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            svg_path = Path(tmp) / "final.svg"
            render_svg("hello <tui>", svg_path, 80, 24)
            svg = svg_path.read_text(encoding="utf-8")
            self.assertIn("<svg", svg)
            self.assertIn("hello &lt;tui&gt;", svg)
