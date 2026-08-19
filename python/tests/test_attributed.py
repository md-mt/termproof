from __future__ import annotations

import unittest
from xml.etree import ElementTree

from termproof.attributed import (
    AttributedCell,
    AttributedScreen,
    SvgStyle,
    attributed_screen_from_ansi_text,
    attributed_screen_from_pyte,
    attributed_screen_from_text,
    cell_colors,
    screen_svg,
)


class _FakeCursor:
    def __init__(self, x: int, y: int, hidden: bool) -> None:
        self.x = x
        self.y = y
        self.hidden = hidden


class _FakeChar:
    def __init__(self, data: str, **attrs: object) -> None:
        self.data = data
        self.fg = attrs.get("fg", "default")
        self.bg = attrs.get("bg", "default")
        self.bold = attrs.get("bold", False)
        self.italics = attrs.get("italics", False)
        self.underscore = attrs.get("underscore", False)
        self.strikethrough = attrs.get("strikethrough", False)
        self.reverse = attrs.get("reverse", False)


class _FakePyteScreen:
    """Minimal structural stand-in for ``pyte.Screen``."""

    def __init__(self, rows: list[list[_FakeChar]]) -> None:
        self.buffer = {y: dict(enumerate(row)) for y, row in enumerate(rows)}
        self.lines = len(rows)
        self.columns = max(len(row) for row in rows)
        self.cursor = _FakeCursor(2, 1, False)


class PlainTextTest(unittest.TestCase):
    def test_text_round_trips(self) -> None:
        screen = attributed_screen_from_text("ab\ncd")
        self.assertEqual("ab\ncd", screen.to_text())
        self.assertEqual(2, screen.row_count)
        self.assertEqual(2, screen.column_count)

    def test_trailing_whitespace_is_trimmed_on_request(self) -> None:
        screen = attributed_screen_from_text("ab   \ncd")
        self.assertEqual("ab   \ncd", screen.to_text())
        self.assertEqual("ab\ncd", screen.to_text(trim_right=True))

    def test_rows_and_columns_are_clamped(self) -> None:
        screen = attributed_screen_from_text("abcdef\nghijkl\nmnopqr", columns=3, rows=2)
        self.assertEqual(["abc", "ghi"], screen.text_lines())


class AnsiParsingTest(unittest.TestCase):
    def test_plain_text_matches_the_unstyled_grid(self) -> None:
        self.assertEqual(
            attributed_screen_from_text("hello"),
            attributed_screen_from_ansi_text("hello"),
        )

    def test_sgr_colour_is_captured_and_stripped_from_the_text(self) -> None:
        screen = attributed_screen_from_ansi_text("\x1b[31mred\x1b[0m plain")
        self.assertEqual("red plain", screen.to_text())
        self.assertEqual("red", screen.rows[0][0].fg)
        self.assertEqual("default", screen.rows[0][4].fg)

    def test_styles_toggle_on_and_off(self) -> None:
        screen = attributed_screen_from_ansi_text("\x1b[1;4mAB\x1b[24mC\x1b[22mD")
        cells = screen.rows[0]
        self.assertTrue(cells[0].bold and cells[0].underline)
        self.assertTrue(cells[2].bold)
        self.assertFalse(cells[2].underline)
        self.assertFalse(cells[3].bold)

    def test_256_colour_and_truecolour(self) -> None:
        screen = attributed_screen_from_ansi_text("\x1b[38;5;196mX\x1b[38;2;1;2;3mY")
        self.assertEqual("ff0000", screen.rows[0][0].fg)
        self.assertEqual("010203", screen.rows[0][1].fg)

    def test_a_truncated_extended_colour_does_not_leak_into_later_codes(self) -> None:
        # `38;5` with no index: the trailing `5` must not be read as SGR 5.
        screen = attributed_screen_from_ansi_text("\x1b[38;5mX")
        self.assertEqual("X", screen.to_text())
        self.assertEqual("default", screen.rows[0][0].fg)

    def test_a_sequence_cut_before_its_final_byte_emits_nothing(self) -> None:
        """A capture can end mid-sequence; the parameter bytes are not glyphs.

        `capture-pane -e` is a snapshot of a pane a program is still painting.
        Reading `\x1b[31` as ESC-then-`[31` put the parameters in the middle of
        the screenshot, which is exactly the artifact a reader would mistrust.
        """
        self.assertEqual("ok", attributed_screen_from_ansi_text("ok\x1b[31").to_text())
        self.assertEqual("ok", attributed_screen_from_ansi_text("ok\x1b[").to_text())
        self.assertEqual("ok", attributed_screen_from_ansi_text("ok\x1b").to_text())

    def test_a_complete_sequence_at_the_very_end_of_a_line_still_applies(self) -> None:
        """The truncation rule must not swallow a sequence that is intact."""
        screen = attributed_screen_from_ansi_text("\x1b[31mred\x1b[0m")
        self.assertEqual("red", screen.to_text())
        self.assertEqual("red", screen.rows[0][0].fg)

    def test_a_final_byte_that_is_not_a_letter_still_ends_the_sequence(self) -> None:
        """Scanning for `isalpha()` ended a CSI one character too late.

        ECMA-48 puts the CSI final byte at 0x40-0x7E, which is wider than the
        letters. Stopping only on a letter meant `\x1b[1~` ran on to the `a` of
        the following word and consumed it: `before\x1b[1~after` rendered as
        `beforefter`. Silent text corruption in a screenshot.
        """
        for payload in ("\x1b[1~", "\x1b[5@", "\x1b[2^", "\x1b[H", "\x1b[?25l", "\x1b[1;2H"):
            with self.subTest(payload=payload):
                text = attributed_screen_from_ansi_text(f"before{payload}after").to_text()
                self.assertEqual("beforeafter", text)

    def test_every_byte_in_the_csi_final_range_terminates(self) -> None:
        """The whole range, so the rule is the rule rather than the examples."""
        for code in range(0x40, 0x7F):
            final = chr(code)
            with self.subTest(final=final):
                text = attributed_screen_from_ansi_text(f"a\x1b[1{final}b").to_text()
                self.assertEqual("ab", text)

    def test_a_parameter_byte_does_not_terminate(self) -> None:
        """0x30-0x3F are parameters; ending there would cut a sequence short."""
        screen = attributed_screen_from_ansi_text("\x1b[38;5;196mX")
        self.assertEqual("X", screen.to_text())
        self.assertEqual("ff0000", screen.rows[0][0].fg)

    def test_a_fresh_escape_abandons_the_sequence_in_progress(self) -> None:
        """`[` is inside the final-byte range, so an aborted CSI needs handling.

        Without this, `\x1b[31\x1b[32mX` would end its first sequence on the
        second `[` and emit `32mX` as text.
        """
        screen = attributed_screen_from_ansi_text("\x1b[31\x1b[32mX")
        self.assertEqual("X", screen.to_text())
        self.assertEqual("green", screen.rows[0][0].fg)

    def test_the_repr_is_readable_rather_than_a_cell_dump(self) -> None:
        """A grid now hangs off every `StepResult`, so its repr lands in failures.

        The generated dataclass repr of a 100x32 grid is around half a megabyte.
        """
        screen = attributed_screen_from_ansi_text(
            "\r\n".join("filler" for _ in range(32)), columns=100, rows=32
        )
        text = repr(screen)
        self.assertLess(len(text), 200)
        self.assertIn("32x", text)
        self.assertIn("filler", text)

    def test_a_double_width_glyph_occupies_two_columns(self) -> None:
        screen = attributed_screen_from_ansi_text("你ok")
        cells = screen.rows[0]
        self.assertEqual(2, cells[0].width)
        self.assertEqual(0, cells[1].width)
        self.assertEqual("你ok", screen.to_text())

    def test_a_combining_mark_folds_into_the_previous_cell(self) -> None:
        screen = attributed_screen_from_ansi_text("éx")
        self.assertEqual("éx", screen.to_text())

    def test_a_tab_advances_to_the_next_eight_column_stop(self) -> None:
        screen = attributed_screen_from_ansi_text("ab\tc")
        self.assertEqual("ab      c", screen.to_text())

    def test_non_sgr_sequences_are_consumed_without_emitting_glyphs(self) -> None:
        screen = attributed_screen_from_ansi_text("\x1b[2Jclear")
        self.assertEqual("clear", screen.to_text())

    def test_control_bytes_never_reach_a_cell(self) -> None:
        self.assertEqual("ab", attributed_screen_from_ansi_text("a\x07\x00b").to_text())
        self.assertEqual("ab", attributed_screen_from_text("a\x7fb").to_text())


class PyteAdapterTest(unittest.TestCase):
    def test_attributes_are_read_off_the_buffer(self) -> None:
        screen = attributed_screen_from_pyte(
            _FakePyteScreen(
                [
                    [_FakeChar("h", fg="red", bold=True), _FakeChar("i")],
                    [_FakeChar("!", reverse=True), _FakeChar(" ")],
                ]
            )
        )
        self.assertEqual("hi\n! ", screen.to_text())
        self.assertEqual("red", screen.rows[0][0].fg)
        self.assertTrue(screen.rows[0][0].bold)
        self.assertTrue(screen.rows[1][0].reverse)
        self.assertEqual((1, 2), (screen.cursor_row, screen.cursor_column))


class FingerprintTest(unittest.TestCase):
    def test_identical_screens_agree(self) -> None:
        left = attributed_screen_from_ansi_text("\x1b[31mred")
        right = attributed_screen_from_ansi_text("\x1b[31mred")
        self.assertEqual(left.render_fingerprint(), right.render_fingerprint())

    def test_a_colour_only_change_is_a_different_fingerprint(self) -> None:
        # The whole point of fingerprinting the grid rather than the text: these
        # two screens are identical as strings.
        red = attributed_screen_from_ansi_text("\x1b[31malert")
        green = attributed_screen_from_ansi_text("\x1b[32malert")
        self.assertEqual(red.to_text(), green.to_text())
        self.assertNotEqual(red.render_fingerprint(), green.render_fingerprint())


class ColorResolutionTest(unittest.TestCase):
    def test_named_hex_and_default_colours(self) -> None:
        style = SvgStyle()
        self.assertEqual((style.fg, style.bg), cell_colors(AttributedCell(text="x"), style))
        self.assertEqual("#ff7b72", cell_colors(AttributedCell(text="x", fg="red"), style)[0])
        self.assertEqual("#abcdef", cell_colors(AttributedCell(text="x", fg="abcdef"), style)[0])

    def test_an_unknown_colour_falls_back_to_the_default(self) -> None:
        self.assertEqual(SvgStyle().fg, cell_colors(AttributedCell(text="x", fg="chartreuse"))[0])

    def test_reverse_swaps_foreground_and_background(self) -> None:
        style = SvgStyle()
        fg, bg = cell_colors(AttributedCell(text="x", reverse=True), style)
        self.assertEqual((style.bg, style.fg), (fg, bg))


class SvgTest(unittest.TestCase):
    def test_markup_is_escaped(self) -> None:
        svg = screen_svg(attributed_screen_from_text("<tui> & co"))
        self.assertIn("&lt;", svg)
        self.assertIn("&amp;", svg)
        self.assertNotIn("<text >", svg)

    def test_one_text_element_per_non_blank_cell(self) -> None:
        svg = screen_svg(attributed_screen_from_text("ab c"))
        self.assertEqual(3, svg.count("<text "))

    def test_glyphs_are_positioned_by_column_not_by_font_metrics(self) -> None:
        style = SvgStyle(cell_w=10.0, padding=10)
        svg = screen_svg(attributed_screen_from_text("ab"), style)
        self.assertIn('x="10.0"', svg)
        self.assertIn('x="20.0"', svg)

    def test_a_non_default_background_emits_a_rect(self) -> None:
        plain = screen_svg(attributed_screen_from_text("x"))
        highlighted = screen_svg(attributed_screen_from_ansi_text("\x1b[41mx"))
        self.assertNotIn("<rect x=", plain)
        self.assertIn("<rect x=", highlighted)

    def test_styles_reach_the_markup(self) -> None:
        svg = screen_svg(attributed_screen_from_ansi_text("\x1b[1;3;4;9;2mx"))
        self.assertIn('font-weight="700"', svg)
        self.assertIn('font-style="italic"', svg)
        self.assertIn("underline line-through", svg)
        self.assertIn('opacity="0.65"', svg)

    def test_canvas_is_derived_from_the_grid(self) -> None:
        style = SvgStyle(columns=80, rows=24, cell_w=10.0, cell_h=22.0, padding=10)
        self.assertEqual(820, style.width)
        self.assertEqual(548, style.height)
        self.assertIn('width="820"', screen_svg(AttributedScreen(rows=()), style))

    def test_an_empty_screen_still_renders_valid_markup(self) -> None:
        svg = screen_svg(AttributedScreen(rows=()))
        self.assertTrue(svg.startswith("<svg"))
        self.assertTrue(svg.endswith("</svg>"))

    def test_output_is_well_formed_xml(self) -> None:
        # An unescaped control byte reaching the SVG makes it invalid XML, which
        # rasterizers reject by writing a 0-byte image rather than failing loudly.
        for text in ("plain", "<tui> & 'co'", "\x1b[31mred\x1b[0m", "你好\ttabbed", "a\x07b"):
            with self.subTest(text=text):
                ElementTree.fromstring(screen_svg(attributed_screen_from_ansi_text(text)))


if __name__ == "__main__":
    unittest.main()
