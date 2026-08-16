from __future__ import annotations

import json
from pathlib import Path

import pyte

from .attributed import AttributedScreen, attributed_screen_from_pyte
from .config import SvgRenderConfig


def replay_cast(cast_path: Path) -> tuple[str, int, int]:
    with cast_path.open(encoding="utf-8") as file:
        header = json.loads(file.readline())
        cols = int(header.get("width", 100))
        rows = int(header.get("height", 30))
        screen = pyte.Screen(cols, rows)
        stream = pyte.Stream(screen)
        for line in file:
            event = json.loads(line)
            if len(event) >= 3 and event[1] == "o":
                stream.feed(event[2])
    return screen_text(screen), cols, rows


def replay_cast_attributed(cast_path: Path) -> tuple[AttributedScreen, int, int]:
    """Replay a cast and return the final screen with its attributes intact.

    The text-only :func:`replay_cast` discards colour, which is most of what a
    TUI uses to say what state it is in.
    """
    with cast_path.open(encoding="utf-8") as file:
        header = json.loads(file.readline())
        cols = int(header.get("width", 100))
        rows = int(header.get("height", 30))
        screen = pyte.Screen(cols, rows)
        stream = pyte.Stream(screen)
        for line in file:
            event = json.loads(line)
            if len(event) >= 3 and event[1] == "o":
                stream.feed(event[2])
    return screen_attributed(screen), cols, rows


def screen_text(screen: pyte.Screen) -> str:
    lines = [line.rstrip() for line in screen.display]
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines)


def screen_attributed(screen: pyte.Screen) -> AttributedScreen:
    """Read *screen* as an attributed grid, colour and styles included."""
    return attributed_screen_from_pyte(screen)


def render_svg(
    text: str,
    output_path: Path,
    cols: int,
    rows: int,
    config: SvgRenderConfig | None = None,
) -> None:
    """Render a screen to SVG.

    Thin wrapper over :class:`~termproof.builtin_renderers.SvgRenderer`. There
    is one renderer behind both entry points, not two copies to keep in step.
    """
    from .builtin_renderers import SvgRenderer

    SvgRenderer(config).render(text, output_path, cols, rows)
