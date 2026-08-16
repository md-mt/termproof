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

    def test_the_emulator_still_exposes_no_dim_attribute(self) -> None:
        """The precondition of the dim limitation, asserted where it can fail.

        Dim is dropped on the cast-replay path because pyte models no dim/faint
        attribute, so SGR 2 is consumed by the emulator and there is nothing for
        ``_cell_from_pyte_char`` to read. That is a fact about *pyte*, and it is
        the only place a guard can bite: asserting on the resulting
        ``AttributedCell`` instead would be a tautology, because
        ``_cell_from_pyte_char`` never sets ``dim`` and the cell therefore reads
        ``False`` no matter what the emulator did.

        When pyte grows the field, this fails -- which is the signal to carry it
        through and drop the limitation from the docs, not to relax the test.
        """
        import pyte

        screen = pyte.Screen(20, 1)
        pyte.Stream(screen).feed("\x1b[2mdim\x1b[0m")
        char = screen.buffer[0][0]
        self.assertEqual("d", char.data, "sanity: the cell under test is the dim one")
        for field in ("dim", "faint"):
            self.assertFalse(
                hasattr(char, field),
                f"pyte now exposes {field!r}: carry it through _cell_from_pyte_char, "
                "update docs/evidence-quality.md and the CHANGELOG, and delete this guard",
            )

    def test_dim_does_not_reach_the_rendered_screenshot(self) -> None:
        """The user-visible consequence of the limitation above.

        Distinct from a guard: this pins what `final.svg` and the
        `attributed_rsvg` video actually contain today. It fails if dim ever
        starts rendering on this path, which is the direction we want to hear
        about; `test_the_emulator_still_exposes_no_dim_attribute` is what
        catches the silent direction.
        """
        from termproof.builtin_renderers import SvgRenderer

        with tempfile.TemporaryDirectory() as tmp:
            cast_path = Path(tmp) / "session.cast"
            with CastRecorder(cast_path, 80, 24, ["demo"]) as recorder:
                recorder.output("\x1b[2mdim\x1b[0m \x1b[1mbold\x1b[0m")
            screen, cols, rows = replay_cast_attributed(cast_path)
            # Not a blanket failure of the path: bold from the same cast survives.
            self.assertTrue(screen.rows[0][4].bold)

            svg_path = Path(tmp) / "final.svg"
            SvgRenderer().render_attributed(screen, svg_path, cols, rows)
            svg = svg_path.read_text(encoding="utf-8")
            self.assertNotIn("opacity", svg)
            self.assertIn('font-weight="700"', svg)

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
