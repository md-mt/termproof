"""One definition of the SVG geometry defaults, pinned field by field.

``SvgStyle`` and ``SvgRenderConfig`` both describe the geometry of a rendered
screen, and for one release they disagreed in every single field: cell 9x20
against 10.0x22.0, 14px font against 16px, 18px padding against 10px, a
``#101418`` page against ``#0b0f14``, and a macOS/Windows font stack against a
Linux one. Nothing failed. A consumer moving from ``screen_svg(screen,
SvgStyle())`` to a configured renderer — the natural move, and the one the API
shape invites — silently resized, re-padded and re-coloured every image it had
ever produced.

These tests are the thing that fails next time instead of somebody's artifacts.
"""

from __future__ import annotations

import unittest
from dataclasses import replace

from termproof.attributed import (
    DEFAULT_BG,
    DEFAULT_CELL_H,
    DEFAULT_CELL_W,
    DEFAULT_COLUMNS,
    DEFAULT_FG,
    DEFAULT_FONT_PX,
    DEFAULT_PADDING,
    DEFAULT_ROWS,
    FONT_STACK,
    SvgStyle,
)
from termproof.config import PngRenderConfig, SvgRenderConfig


class CanonicalConstantsTest(unittest.TestCase):
    """The literal values, so moving one is a deliberate act with a diff."""

    def test_each_constant_is_pinned(self) -> None:
        self.assertEqual(120, DEFAULT_COLUMNS)
        self.assertEqual(40, DEFAULT_ROWS)
        self.assertEqual(10.0, DEFAULT_CELL_W)
        self.assertEqual(22.0, DEFAULT_CELL_H)
        self.assertEqual(16, DEFAULT_FONT_PX)
        self.assertEqual(10, DEFAULT_PADDING)
        self.assertEqual("Noto Sans Mono, Liberation Mono, monospace", FONT_STACK)
        self.assertEqual("#e6edf3", DEFAULT_FG)
        self.assertEqual("#0b0f14", DEFAULT_BG)

    def test_svg_style_takes_every_default_from_a_constant(self) -> None:
        style = SvgStyle()
        self.assertEqual(DEFAULT_COLUMNS, style.columns)
        self.assertEqual(DEFAULT_ROWS, style.rows)
        self.assertEqual(DEFAULT_CELL_W, style.cell_w)
        self.assertEqual(DEFAULT_CELL_H, style.cell_h)
        self.assertEqual(DEFAULT_FONT_PX, style.font_px)
        self.assertEqual(DEFAULT_PADDING, style.padding)
        self.assertEqual(FONT_STACK, style.font_family)
        self.assertEqual(DEFAULT_FG, style.fg)
        self.assertEqual(DEFAULT_BG, style.bg)
        self.assertEqual(0, style.min_width)
        self.assertEqual(0, style.min_height)

    def test_svg_render_config_takes_every_default_from_the_same_constant(self) -> None:
        config = SvgRenderConfig()
        self.assertEqual(DEFAULT_CELL_W, config.char_width)
        self.assertEqual(DEFAULT_CELL_H, config.line_height)
        self.assertEqual(DEFAULT_FONT_PX, config.font_size)
        self.assertEqual(DEFAULT_PADDING, config.padding)
        self.assertEqual(FONT_STACK, config.font_family)
        self.assertEqual(DEFAULT_FG, config.fg)
        self.assertEqual(DEFAULT_BG, config.bg)

    def test_the_png_page_is_the_same_colour_as_the_svg_one(self) -> None:
        """Two formats of one screenshot must not disagree about the terminal."""
        png = PngRenderConfig()
        self.assertEqual(DEFAULT_FG, png.fg)
        self.assertEqual(DEFAULT_BG, png.bg)


class NoDriftBetweenTheTwoTypesTest(unittest.TestCase):
    """The assertion the missing test would have caught the original bug with."""

    def test_an_unconfigured_render_config_reproduces_the_canonical_style(self) -> None:
        for cols, rows in ((DEFAULT_COLUMNS, DEFAULT_ROWS), (80, 24), (3, 2)):
            with self.subTest(cols=cols, rows=rows):
                self.assertEqual(
                    SvgStyle(columns=cols, rows=rows),
                    SvgRenderConfig().style(cols, rows),
                )

    def test_every_style_field_is_reachable_from_the_render_config(self) -> None:
        """A knob only one of the two has is a knob that can drift silently.

        ``min_width``/``min_height`` are the deliberate exception: they are an
        opt-in floor no TermProof renderer sets, so ``SvgRenderConfig`` has no
        YAML key for them and leaves them at zero.
        """
        style = SvgRenderConfig().style(80, 24)
        unreachable = {"columns", "rows", "min_width", "min_height"}
        overridden = SvgRenderConfig(
            char_width=7.5,
            line_height=15.0,
            padding=3,
            font_size=9,
            font_family="Fake Mono, monospace",
            fg="#111111",
            bg="#222222",
        ).style(80, 24)
        for field_name in vars(style):
            if field_name in unreachable:
                continue
            with self.subTest(field=field_name):
                self.assertNotEqual(
                    getattr(style, field_name),
                    getattr(overridden, field_name),
                    f"{field_name} cannot be configured through SvgRenderConfig",
                )


class CanvasGeometryTest(unittest.TestCase):
    def test_the_canvas_is_exactly_the_grid_plus_padding(self) -> None:
        style = SvgRenderConfig().style(120, 40)
        self.assertEqual(120 * 10 + 2 * 10, style.width)
        self.assertEqual(40 * 22 + 2 * 10, style.height)

    def test_neither_path_floors_a_small_canvas(self) -> None:
        """The floors used to bind on one path and not the other, invisibly.

        ``SvgRenderConfig.style`` set ``min_width: 320, min_height: 160`` while
        ``SvgStyle``'s own defaults were zero, so the two agreed at 120x40 —
        where nothing binds — and disagreed the moment anyone rendered a small
        screen. Both are floorless now.
        """
        self.assertEqual(3 * 10 + 20, SvgRenderConfig().style(3, 2).width)
        self.assertEqual(2 * 22 + 20, SvgRenderConfig().style(3, 2).height)
        self.assertEqual(SvgStyle(columns=3, rows=2).width, SvgRenderConfig().style(3, 2).width)

    def test_an_explicit_floor_still_works_for_a_caller_that_wants_one(self) -> None:
        floored = replace(SvgStyle(columns=3, rows=2), min_width=320, min_height=160)
        self.assertEqual(320, floored.width)
        self.assertEqual(160, floored.height)


class FontStackTest(unittest.TestCase):
    """CI renders on Linux, and a proportional fallback breaks the column grid.

    ``screen_svg`` places one ``<text>`` per cell at ``x = column * cell_w``, so
    a substituted glyph cannot shift its neighbours — but a proportional face
    still overflows its cell and overlaps the next one. ``Menlo`` in particular
    resolves to proportional DejaVu Sans on some stock images.
    """

    LINUX_FONTS = ("Noto Sans Mono", "Liberation Mono")

    def _families(self, stack: str) -> list[str]:
        return [part.strip() for part in stack.split(",")]

    def test_the_canonical_stack_names_linux_fonts_before_the_generic_fallback(self) -> None:
        families = self._families(FONT_STACK)
        self.assertEqual("monospace", families[-1])
        for font in self.LINUX_FONTS:
            with self.subTest(font=font):
                self.assertIn(font, families)
                self.assertLess(families.index(font), families.index("monospace"))

    def test_the_stack_names_nothing_that_only_exists_off_linux(self) -> None:
        families = set(self._families(FONT_STACK))
        for font in ("ui-monospace", "SFMono-Regular", "Menlo", "Consolas"):
            with self.subTest(font=font):
                self.assertNotIn(font, families)

    def test_both_types_ship_that_stack(self) -> None:
        self.assertEqual(FONT_STACK, SvgStyle().font_family)
        self.assertEqual(FONT_STACK, SvgRenderConfig().font_family)
        self.assertEqual(FONT_STACK, SvgRenderConfig().style(80, 24).font_family)


if __name__ == "__main__":
    unittest.main()
