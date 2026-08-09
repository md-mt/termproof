from __future__ import annotations

import html
import json
from pathlib import Path

import pyte

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


def screen_text(screen: pyte.Screen) -> str:
    lines = [line.rstrip() for line in screen.display]
    while lines and not lines[-1]:
        lines.pop()
    return "\n".join(lines)


def render_svg(
    text: str,
    output_path: Path,
    cols: int,
    rows: int,
    config: SvgRenderConfig | None = None,
) -> None:
    """Render a screen to SVG.

    Deliberately duplicates ``builtin_renderers.SvgRenderer``; the two must be
    kept in step until the duplicate is removed in a separate structural change.
    """
    config = config or SvgRenderConfig()
    width = max(320, cols * config.char_width + config.padding * 2)
    height = max(160, rows * config.line_height + config.padding * 2)
    visible_lines = text.splitlines()[:rows] or [""]
    output_path.parent.mkdir(parents=True, exist_ok=True)

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        f'<rect width="100%" height="100%" fill="{config.bg}"/>',
        f'<style>text{{font:{config.font_size}px {config.font_family};fill:{config.fg};white-space:pre}}</style>',
    ]
    for index, line in enumerate(visible_lines):
        y = config.padding + config.line_height * (index + 1)
        parts.append(f'<text x="{config.padding}" y="{y}">{html.escape(line)}</text>')
    parts.append("</svg>")
    output_path.write_text("\n".join(parts) + "\n", encoding="utf-8")
