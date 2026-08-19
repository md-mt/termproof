"""Attributed terminal screen model and colour SVG renderer.

A plain-text screen loses everything a terminal uses to convey state: colour,
bold, reverse video. This module keeps a per-cell grid so a screenshot looks
like what the operator saw, and so two screens that differ only in colour
compare as different.

Which artifacts get that: ``final.svg`` and the ``attributed_rsvg`` video, both
built from a grid, and per-step screenshots whenever the session behind the step
could supply one — see :attr:`~termproof.models.StepResult.screen_attributed`.
A session backend that reports no grid still renders its step screenshots from
the flattened text, in monochrome, and so does the PNG renderer, which has no
``render_attributed``. Dim is carried by :func:`attributed_screen_from_ansi_text`
but not by :func:`attributed_screen_from_pyte`, because pyte models no dim
attribute. See ``docs/evidence-quality.md``.

Depends on the standard library alone; :func:`attributed_screen_from_pyte`
reads a ``pyte.Screen`` structurally rather than importing it.
"""

from __future__ import annotations

import functools
import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass
from typing import Any
from xml.sax.saxutils import escape

DEFAULT_COLUMNS = 120
DEFAULT_ROWS = 40
DEFAULT_CELL_W = 10.0
DEFAULT_CELL_H = 22.0
DEFAULT_FONT_PX = 16
DEFAULT_PADDING = 10
FONT_STACK = "Noto Sans Mono, Liberation Mono, monospace"
DEFAULT_FG = "#e6edf3"
DEFAULT_BG = "#0b0f14"

_HEX_COLOR = re.compile(r"^[0-9a-fA-F]{6}$")
_ANSI_PARAMS = re.compile(r"[;:]")
_COLORS = {
    "black": "#0b0f14",
    "red": "#ff7b72",
    "green": "#7ee787",
    "brown": "#d29922",
    "blue": "#79c0ff",
    "magenta": "#d2a8ff",
    "cyan": "#56d4dd",
    "white": "#e6edf3",
    "brightblack": "#6e7681",
    "brightred": "#ffa198",
    "brightgreen": "#aff5b4",
    "brightbrown": "#f2cc60",
    "brightblue": "#a5d6ff",
    "brightmagenta": "#d2a8ff",
    "brightcyan": "#79c0ff",
    "brightwhite": "#ffffff",
}
_ANSI_FG = {
    30: "black",
    31: "red",
    32: "green",
    33: "brown",
    34: "blue",
    35: "magenta",
    36: "cyan",
    37: "white",
    90: "brightblack",
    91: "brightred",
    92: "brightgreen",
    93: "brightbrown",
    94: "brightblue",
    95: "brightmagenta",
    96: "brightcyan",
    97: "brightwhite",
}
_ANSI_BG = {
    40: "black",
    41: "red",
    42: "green",
    43: "brown",
    44: "blue",
    45: "magenta",
    46: "cyan",
    47: "white",
    100: "brightblack",
    101: "brightred",
    102: "brightgreen",
    103: "brightbrown",
    104: "brightblue",
    105: "brightmagenta",
    106: "brightcyan",
    107: "brightwhite",
}
_STYLE_ON = {
    1: "bold",
    2: "dim",
    3: "italic",
    4: "underline",
    7: "reverse",
    9: "strikethrough",
}
_STYLE_OFF = {
    23: "italic",
    24: "underline",
    27: "reverse",
    29: "strikethrough",
}
_XTERM_256_BASE = [
    "000000",
    "cd0000",
    "00cd00",
    "cdcd00",
    "0000ee",
    "cd00cd",
    "00cdcd",
    "e5e5e5",
    "7f7f7f",
    "ff0000",
    "00ff00",
    "ffff00",
    "5c5cff",
    "ff00ff",
    "00ffff",
    "ffffff",
]


@functools.lru_cache(maxsize=1)
def _xterm_256_colors() -> list[str]:
    colors = list(_XTERM_256_BASE)
    for red in (0x00, 0x5F, 0x87, 0xAF, 0xD7, 0xFF):
        for green in (0x00, 0x5F, 0x87, 0xAF, 0xD7, 0xFF):
            for blue in (0x00, 0x5F, 0x87, 0xAF, 0xD7, 0xFF):
                colors.append(f"{red:02x}{green:02x}{blue:02x}")
    for index in range(24):
        value = 8 + index * 10
        colors.append(f"{value:02x}{value:02x}{value:02x}")
    return colors


@dataclass
class _AnsiAttrs:
    fg: str = "default"
    bg: str = "default"
    bold: bool = False
    dim: bool = False
    italic: bool = False
    underline: bool = False
    strikethrough: bool = False
    reverse: bool = False

    def reset(self) -> None:
        self.fg = "default"
        self.bg = "default"
        self.bold = False
        self.dim = False
        self.italic = False
        self.underline = False
        self.strikethrough = False
        self.reverse = False

    def cell(self, text: str, width: int = 1) -> AttributedCell:
        return AttributedCell(
            text=text,
            fg=self.fg,
            bg=self.bg,
            bold=self.bold,
            dim=self.dim,
            italic=self.italic,
            underline=self.underline,
            strikethrough=self.strikethrough,
            reverse=self.reverse,
            width=width,
        )


@dataclass(frozen=True)
class AttributedCell:
    """One terminal cell with its display attributes.

    ``width`` is 0 for the placeholder that follows a double-width glyph, so
    the grid stays rectangular without the glyph being counted twice.
    """

    text: str = " "
    fg: str = "default"
    bg: str = "default"
    bold: bool = False
    dim: bool = False
    italic: bool = False
    underline: bool = False
    strikethrough: bool = False
    reverse: bool = False
    width: int = 1

    def fingerprint_payload(self) -> tuple[Any, ...]:
        """Everything that makes this cell look the way it does."""
        return (
            self.text,
            self.fg,
            self.bg,
            self.bold,
            self.dim,
            self.italic,
            self.underline,
            self.strikethrough,
            self.reverse,
            self.width,
        )


class _CellPool:
    """Shares one object between the cells of a grid that compare equal.

    A terminal screen is mostly repetition: blank cells, runs of one colour.
    Cells are frozen and carry no identity, so one object can stand in for every
    cell equal to it. On a 100x32 screen this takes the grid from ~528 KB to
    ~36 KB, which is the difference between a grid per step being affordable for
    a whole run and not — see ``StepScreenMemoryTest``.

    The pool lives for one grid build and is then dropped. A process-wide cache
    would share more, but it would also grow without a bound anyone owns.
    """

    __slots__ = ("_cells",)

    def __init__(self) -> None:
        self._cells: dict[AttributedCell, AttributedCell] = {}

    def intern(self, cell: AttributedCell) -> AttributedCell:
        return self._cells.setdefault(cell, cell)


@dataclass(frozen=True)
class AttributedScreen:
    """A rectangular terminal grid plus cursor metadata."""

    rows: tuple[tuple[AttributedCell, ...], ...]
    cursor_row: int = 0
    cursor_column: int = 0
    cursor_hidden: bool = False

    @property
    def row_count(self) -> int:
        return len(self.rows)

    @property
    def column_count(self) -> int:
        return max((len(row) for row in self.rows), default=0)

    def text_lines(self, trim_right: bool = False) -> list[str]:
        lines = []
        for row in self.rows:
            line = "".join(cell.text for cell in row if cell.width > 0)
            lines.append(line.rstrip() if trim_right else line)
        return lines

    def to_text(self, trim_right: bool = False) -> str:
        return "\n".join(self.text_lines(trim_right=trim_right))

    def render_fingerprint(self) -> str:
        """Digest of every cell's appearance, for screenshot dedup.

        Two screens with identical text but different colour hash differently,
        which plain-text comparison cannot express.
        """
        payload = [[cell.fingerprint_payload() for cell in row] for row in self.rows]
        encoded = json.dumps(payload, separators=(",", ":"))
        return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class SvgStyle:
    """Geometry and palette for :func:`screen_svg`."""

    columns: int = DEFAULT_COLUMNS
    rows: int = DEFAULT_ROWS
    cell_w: float = DEFAULT_CELL_W
    cell_h: float = DEFAULT_CELL_H
    font_px: int = DEFAULT_FONT_PX
    padding: int = DEFAULT_PADDING
    font_family: str = FONT_STACK
    fg: str = DEFAULT_FG
    bg: str = DEFAULT_BG
    # Floors for a very small grid, so a two-line screen is not a sliver.
    min_width: int = 0
    min_height: int = 0

    @property
    def width(self) -> int:
        return max(self.min_width, int(self.columns * self.cell_w) + 2 * self.padding)

    @property
    def height(self) -> int:
        return max(self.min_height, int(self.rows * self.cell_h) + 2 * self.padding)


def attributed_screen_from_lines(
    lines: list[str],
    *,
    columns: int = DEFAULT_COLUMNS,
    rows: int = DEFAULT_ROWS,
) -> AttributedScreen:
    """Build an unstyled grid from already-split plain text."""
    pool = _CellPool()
    screen_rows = []
    for line in lines[:rows]:
        printable = [ch for ch in line if not _is_control(ch)]
        screen_rows.append(
            tuple(pool.intern(AttributedCell(text=ch)) for ch in printable[:columns])
        )
    return AttributedScreen(rows=tuple(screen_rows))


def attributed_screen_from_text(
    screen_text: str,
    *,
    columns: int = DEFAULT_COLUMNS,
    rows: int = DEFAULT_ROWS,
) -> AttributedScreen:
    """Build an unstyled grid from plain text."""
    return attributed_screen_from_lines(
        screen_text.splitlines(),
        columns=columns,
        rows=rows,
    )


def attributed_screen_from_pyte(screen: Any) -> AttributedScreen:
    """Read a ``pyte.Screen``'s buffer, attributes included.

    Duck-typed so this module does not depend on pyte.
    """
    pool = _CellPool()
    rows = []
    for y in range(screen.lines):
        line = screen.buffer[y]
        rows.append(
            tuple(
                pool.intern(_cell_from_pyte_char(line[x])) for x in range(screen.columns)
            )
        )
    cursor = screen.cursor
    return AttributedScreen(
        rows=tuple(rows),
        cursor_row=cursor.y,
        cursor_column=cursor.x,
        cursor_hidden=cursor.hidden,
    )


def attributed_screen_from_ansi_text(
    ansi_text: str,
    *,
    columns: int = DEFAULT_COLUMNS,
    rows: int = DEFAULT_ROWS,
) -> AttributedScreen:
    """Build a grid from text that still carries SGR escape sequences.

    Text with no escapes yields the same grid as
    :func:`attributed_screen_from_text`, so this is safe to use as the default
    path for screens of unknown provenance.
    """
    pool = _CellPool()
    screen_rows = []
    attrs = _AnsiAttrs()
    lines = ansi_text.split("\n")
    if lines and lines[-1] == "":
        lines.pop()
    for line in lines[:rows]:
        screen_rows.append(
            tuple(_cells_from_ansi_line(line.rstrip("\r"), attrs, columns, pool))
        )
    return AttributedScreen(rows=tuple(screen_rows))


def screen_svg(screen: AttributedScreen, style: SvgStyle | None = None) -> str:
    """Render *screen* as SVG, one ``<text>`` per cell.

    Positioning each glyph at ``x = col * cell_w`` makes column alignment
    structural rather than dependent on whichever font the viewer resolves.
    """
    style = style or SvgStyle()
    backgrounds = []
    glyphs = []
    baseline = style.cell_h * 0.72
    for r, row in enumerate(screen.rows[: style.rows]):
        for c, cell in enumerate(row[: style.columns]):
            if cell.width == 0:
                continue
            fg, bg = cell_colors(cell, style)
            x = style.padding + c * style.cell_w
            y = style.padding + r * style.cell_h
            if bg != style.bg:
                backgrounds.append(
                    f'<rect x="{x:.1f}" y="{y:.1f}" '
                    f'width="{style.cell_w * max(cell.width, 1):.1f}" '
                    f'height="{style.cell_h:.1f}" fill="{bg}"/>'
                )
            if cell.text == " ":
                continue
            glyphs.append(_glyph_svg(cell, x, y + baseline, fg))
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{style.width}" '
        f'height="{style.height}" viewBox="0 0 {style.width} {style.height}">'
        f'<rect width="100%" height="100%" fill="{style.bg}"/>'
        + "".join(backgrounds)
        + f'<g font-family="{style.font_family}" font-size="{style.font_px}" xml:space="preserve">'
        + "".join(glyphs)
        + "</g></svg>"
    )


def cell_colors(cell: AttributedCell, style: SvgStyle | None = None) -> tuple[str, str]:
    """Resolve *cell* to concrete ``(foreground, background)`` CSS colours."""
    style = style or SvgStyle()
    fg = _css_color(cell.fg, style.fg)
    bg = _css_color(cell.bg, style.bg)
    if cell.reverse:
        fg, bg = bg, fg
    return fg, bg


def _cell_from_pyte_char(char: Any) -> AttributedCell:
    # `dim` is deliberately absent. pyte 0.8.2's Char models
    # (data, fg, bg, bold, italics, underscore, strikethrough, reverse, blink)
    # and has no dim/faint field, so SGR 2 is consumed by the emulator and never
    # reaches here. Reading it back would need SGR 2 modelled in the emulator
    # layer. `attributed_screen_from_ansi_text` does carry dim, because it parses
    # the escapes itself. Pinned by `test_dim_does_not_survive_the_cast_replay_path`.
    text = getattr(char, "data", " ")
    return AttributedCell(
        text=text,
        fg=getattr(char, "fg", "default"),
        bg=getattr(char, "bg", "default"),
        bold=bool(getattr(char, "bold", False)),
        italic=bool(getattr(char, "italics", False)),
        underline=bool(getattr(char, "underscore", False)),
        strikethrough=bool(getattr(char, "strikethrough", False)),
        reverse=bool(getattr(char, "reverse", False)),
        width=_cell_width(text),
    )


def _cells_from_ansi_line(
    line: str,
    attrs: _AnsiAttrs,
    columns: int,
    pool: _CellPool,
) -> list[AttributedCell]:
    cells: list[AttributedCell] = []
    index = 0
    while index < len(line) and len(cells) < columns:
        if line[index] == "\x1b":
            next_index = _consume_ansi_sequence(line, index, attrs)
            if next_index != index:
                index = next_index
                continue
        ch = line[index]
        if ch == "\t":
            _append_tab(cells, attrs, columns, pool)
        elif _is_control(ch):
            # A terminal acts on these rather than displaying them, and a raw
            # control byte in the output makes the SVG invalid XML — which a
            # rasterizer reports by writing a 0-byte image, not by failing.
            pass
        elif unicodedata.combining(ch) and cells:
            previous = cells[-1]
            cells[-1] = pool.intern(
                AttributedCell(
                    text=unicodedata.normalize("NFC", previous.text + ch),
                    fg=previous.fg,
                    bg=previous.bg,
                    bold=previous.bold,
                    dim=previous.dim,
                    italic=previous.italic,
                    underline=previous.underline,
                    strikethrough=previous.strikethrough,
                    reverse=previous.reverse,
                    width=previous.width,
                )
            )
        else:
            width = _cell_width(ch)
            cells.append(pool.intern(attrs.cell(ch, width=width)))
            if width == 2 and len(cells) < columns:
                cells.append(pool.intern(attrs.cell("", width=0)))
        index += 1
    return cells


def _consume_ansi_sequence(line: str, index: int, attrs: _AnsiAttrs) -> int:
    if line[index + 1 : index + 2] != "[":
        # ESC at the end of the line, or introducing something that is not CSI.
        # Drop the ESC and let the next character be read normally.
        return index + 1
    end = index + 2
    while end < len(line) and not line[end].isalpha():
        end += 1
    if end >= len(line):
        # A CSI whose final byte never arrived — the capture was cut mid
        # sequence. A terminal is still waiting for the terminator and displays
        # nothing, so the parameter bytes are consumed rather than emitted as
        # glyphs. Emitting them would put `[31` in the middle of a screenshot.
        return len(line)
    command = line[end]
    if command == "m":
        _apply_sgr(_parse_sgr_params(line[index + 2 : end]), attrs)
    return end + 1


def _parse_sgr_params(params: str) -> list[int]:
    if params == "":
        return [0]
    parsed = []
    for part in _ANSI_PARAMS.split(params):
        if part == "":
            continue
        try:
            parsed.append(int(part))
        except ValueError:
            pass
    return parsed or [0]


def _apply_sgr(params: list[int], attrs: _AnsiAttrs) -> None:
    index = 0
    while index < len(params):
        code = params[index]
        if code in _ANSI_FG:
            attrs.fg = _ANSI_FG[code]
        elif code in _ANSI_BG:
            attrs.bg = _ANSI_BG[code]
        elif code in (38, 48):
            index = _apply_extended_color(params, index, attrs)
        else:
            _apply_basic_sgr(code, attrs)
        index += 1


def _apply_basic_sgr(code: int, attrs: _AnsiAttrs) -> None:
    if code == 0:
        attrs.reset()
    elif code == 22:
        attrs.bold = False
        attrs.dim = False
    elif code == 39:
        attrs.fg = "default"
    elif code == 49:
        attrs.bg = "default"
    elif code in _STYLE_ON:
        setattr(attrs, _STYLE_ON[code], True)
    elif code in _STYLE_OFF:
        setattr(attrs, _STYLE_OFF[code], False)


def _apply_extended_color(params: list[int], index: int, attrs: _AnsiAttrs) -> int:
    if index + 1 >= len(params):
        return index
    target = "fg" if params[index] == 38 else "bg"
    mode = params[index + 1]
    if mode == 5 and index + 2 < len(params):
        setattr(attrs, target, _xterm_256_color(params[index + 2]))
        return index + 2
    if mode == 2 and index + 4 < len(params):
        red, green, blue = (min(255, max(0, value)) for value in params[index + 2 : index + 5])
        setattr(attrs, target, f"{red:02x}{green:02x}{blue:02x}")
        return index + 4
    # Truncated sequence: not enough sub-parameters for the declared mode.
    # Consume the rest of the params so the mode indicator itself isn't
    # reinterpreted as a fresh top-level SGR code by the caller's loop.
    return len(params) - 1


def _append_tab(
    cells: list[AttributedCell],
    attrs: _AnsiAttrs,
    columns: int,
    pool: _CellPool,
) -> None:
    target = min(((len(cells) // 8) + 1) * 8, columns)
    blank = pool.intern(attrs.cell(" "))
    while len(cells) < target:
        cells.append(blank)


def _xterm_256_color(index: int) -> str:
    colors = _xterm_256_colors()
    if 0 <= index < len(colors):
        return colors[index]
    return "default"


def _is_control(ch: str) -> bool:
    """True for C0 controls and DEL, which no terminal cell can hold."""
    return ch < " " or ch == "\x7f"


def _cell_width(text: str) -> int:
    if text == "":
        return 0
    if unicodedata.east_asian_width(text[0]) in ("F", "W"):
        return 2
    return 1


def _css_color(value: str, default: str) -> str:
    if value == "default":
        return default
    lowered = value.lower()
    if lowered in _COLORS:
        return _COLORS[lowered]
    if _HEX_COLOR.match(value):
        return f"#{lowered}"
    return default


def _glyph_svg(cell: AttributedCell, x: float, y: float, fg: str) -> str:
    attrs = [f'x="{x:.1f}"', f'y="{y:.1f}"', f'fill="{fg}"']
    if cell.bold:
        attrs.append('font-weight="700"')
    if cell.italic:
        attrs.append('font-style="italic"')
    decorations = []
    if cell.underline:
        decorations.append("underline")
    if cell.strikethrough:
        decorations.append("line-through")
    if decorations:
        attrs.append(f'text-decoration="{" ".join(decorations)}"')
    if cell.dim:
        attrs.append('opacity="0.65"')
    # Belt and braces: the grid builders drop control characters, but a cell can
    # also be constructed by hand, and one stray byte invalidates the document.
    text = "".join(ch for ch in cell.text if not _is_control(ch))
    return f"<text {' '.join(attrs)}>{escape(text)}</text>"


__all__ = [
    "AttributedCell",
    "AttributedScreen",
    "SvgStyle",
    "attributed_screen_from_ansi_text",
    "attributed_screen_from_lines",
    "attributed_screen_from_pyte",
    "attributed_screen_from_text",
    "cell_colors",
    "screen_svg",
]
