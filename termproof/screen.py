from __future__ import annotations

import html
import json
from pathlib import Path

import pyte


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


def render_svg(text: str, output_path: Path, cols: int, rows: int) -> None:
    line_height = 20
    char_width = 9
    padding = 18
    width = max(320, cols * char_width + padding * 2)
    height = max(160, rows * line_height + padding * 2)
    visible_lines = text.splitlines()[:rows] or [""]
    output_path.parent.mkdir(parents=True, exist_ok=True)

    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#101418"/>',
        '<style>text{font:14px ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;fill:#e6edf3;white-space:pre}</style>',
    ]
    for index, line in enumerate(visible_lines):
        y = padding + line_height * (index + 1)
        parts.append(f'<text x="{padding}" y="{y}">{html.escape(line)}</text>')
    parts.append("</svg>")
    output_path.write_text("\n".join(parts) + "\n", encoding="utf-8")
