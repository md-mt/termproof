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

import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from PIL import Image

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
    AttributedCell,
    AttributedScreen,
    SvgStyle,
)
from termproof.builtin_renderers import PngRenderer
from termproof.cast_video import RsvgFfmpegBackend
from termproof.config import (
    RASTER_MIN_HEIGHT,
    RASTER_MIN_WIDTH,
    PngRenderConfig,
    SvgRenderConfig,
)
from termproof.rsvg import RsvgPngRenderer


class _OneCellReplay:
    """Minimal replay: every snapshot is a one-cell screen of what was fed."""

    def __init__(self, columns: int, rows: int) -> None:
        self.columns = columns
        self.rows = rows
        self.text = ""

    def feed(self, data: str) -> None:
        self.text += data

    def snapshot(self) -> AttributedScreen:
        return AttributedScreen(rows=((AttributedCell(text=self.text or " "),),))


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

        ``columns``/``rows`` are the only exception, and not a drift risk: they
        are the grid being rendered, passed to ``style()`` per call rather than
        configured.
        """
        style = SvgRenderConfig().style(80, 24)
        unreachable = {"columns", "rows"}
        overridden = SvgRenderConfig(
            char_width=7.5,
            line_height=15.0,
            padding=3,
            font_size=9,
            font_family="Fake Mono, monospace",
            fg="#111111",
            bg="#222222",
            min_width=11,
            min_height=13,
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

    def test_neither_vector_path_floors_a_small_canvas(self) -> None:
        """The floors used to bind on one path and not the other, invisibly.

        ``SvgRenderConfig.style`` set ``min_width: 320, min_height: 160`` while
        ``SvgStyle``'s own defaults were zero, so the two agreed at 120x40 —
        where nothing binds — and disagreed the moment anyone rendered a small
        screen. Both are floorless now.
        """
        self.assertEqual(3 * 10 + 20, SvgRenderConfig().style(3, 2).width)
        self.assertEqual(2 * 22 + 20, SvgRenderConfig().style(3, 2).height)
        self.assertEqual(SvgStyle(columns=3, rows=2).width, SvgRenderConfig().style(3, 2).width)

    def test_an_explicit_floor_is_configurable_on_the_vector_path(self) -> None:
        """Which is also what makes the CHANGELOG's pin-the-old-output recipe exact."""
        pinned = SvgRenderConfig(min_width=320, min_height=160).style(3, 2)
        self.assertEqual(320, pinned.width)
        self.assertEqual(160, pinned.height)
        self.assertEqual(pinned, replace(SvgStyle(columns=3, rows=2), min_width=320, min_height=160))


class RasterFloorTest(unittest.TestCase):
    """Every path that turns the markup into pixels keeps the 320x160 floor.

    The vector path dropped its floor because a viewer scales an SVG. That
    argument does not reach a rasteriser: ``rsvg-convert`` invoked with no
    ``-w``/``-h``/``-z`` renders at intrinsic size, so the PNG's pixel
    dimensions *are* the SVG's ``width``/``height`` attributes and a small grid
    becomes a postage stamp. Three renderers rasterise; all three are floored.
    """

    SMALL = (20, 4)

    def test_raster_style_floors_where_style_does_not(self) -> None:
        cols, rows = self.SMALL
        config = SvgRenderConfig()
        self.assertEqual((220, 108), (config.style(cols, rows).width, config.style(cols, rows).height))
        raster = config.raster_style(cols, rows)
        self.assertEqual((RASTER_MIN_WIDTH, RASTER_MIN_HEIGHT), (raster.width, raster.height))

    def test_raster_style_is_style_above_the_floor(self) -> None:
        """The floor is a lower bound, not a resize: it must not bind at 120x40."""
        self.assertEqual(
            SvgRenderConfig().style(120, 40),
            replace(SvgRenderConfig().raster_style(120, 40), min_width=0, min_height=0),
        )
        self.assertEqual(1220, SvgRenderConfig().raster_style(120, 40).width)
        self.assertEqual(900, SvgRenderConfig().raster_style(120, 40).height)

    def test_a_configured_floor_above_the_raster_one_still_wins(self) -> None:
        raster = SvgRenderConfig(min_width=800, min_height=600).raster_style(*self.SMALL)
        self.assertEqual((800, 600), (raster.width, raster.height))

    def test_png_rsvg_rasterises_a_small_grid_at_the_floor(self) -> None:
        """Pinned through the markup that actually reaches ``rsvg-convert``."""
        captured: list[str] = []

        def capture(executable: str, args: list[str], timeout: int) -> None:
            svg_path = Path(args[-1])
            captured.append(svg_path.read_text(encoding="utf-8"))
            Path(args[args.index("--output") + 1]).write_bytes(b"png")

        with tempfile.TemporaryDirectory() as tmp:
            RsvgPngRenderer(rsvg_path="/bin/true", runner=capture).render(
                "hi", Path(tmp) / "small.png", *self.SMALL
            )
        self.assertIn(f'width="{RASTER_MIN_WIDTH}"', captured[0])
        self.assertIn(f'height="{RASTER_MIN_HEIGHT}"', captured[0])

    def test_pil_png_rasterises_a_small_grid_at_the_floor(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            output = Path(tmp) / "small.png"
            PngRenderer().render("hi", output, *self.SMALL)
            with Image.open(output) as image:
                self.assertEqual((RASTER_MIN_WIDTH, RASTER_MIN_HEIGHT), image.size)

    def test_the_video_backend_rasterises_frames_at_the_floor(self) -> None:
        """A tiny cast must not become a tiny video; frames go through rsvg too.

        Driven through the real backend with a fake rasteriser, reading the
        frame markup on its way to ``rsvg-convert``.
        """
        frames: list[str] = []

        def capture(executable: str, args: list[str], timeout: int) -> None:
            if "--output" not in args:
                return
            output = Path(args[args.index("--output") + 1])
            if output.suffix == ".png":
                frames.append(Path(args[-1]).read_text(encoding="utf-8"))
                output.write_bytes(b"\x89PNG")

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cast = root / "tiny.cast"
            cast.write_text(
                json.dumps({"version": 2, "width": 20, "height": 4})
                + "\n"
                + json.dumps([0.0, "o", "hi"])
                + "\n",
                encoding="utf-8",
            )
            RsvgFfmpegBackend(
                rsvg_path="/fake/rsvg-convert",
                ffmpeg_path="/fake/ffmpeg",
                runner=capture,
                replay_factory=_OneCellReplay,
            ).render(cast, root / "out.mp4", 4)

        self.assertTrue(frames, "the backend rasterised no frames")
        for markup in frames:
            self.assertIn(f'width="{RASTER_MIN_WIDTH}"', markup)
            self.assertIn(f'height="{RASTER_MIN_HEIGHT}"', markup)


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
        """Absence, not just ordering — and that is a deliberate trade-off.

        Appending the four off-Linux names *after* the Linux ones would satisfy
        every correctness argument above and would give a macOS or Windows
        reader SF Mono or Consolas instead of the browser's generic
        ``monospace``. It is refused for one reason: Rust's ``FONT_STACK`` is
        the same literal string, and the two implementations emitting
        byte-identical SVG for the same input is a property this project
        asserts. Changing the stack means changing both, which is a separate
        change. Until then the cost is real and named: off-Linux viewers get
        generic monospace.
        """
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
