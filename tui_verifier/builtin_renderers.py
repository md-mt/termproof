from __future__ import annotations

from pathlib import Path
from typing import Protocol


class ScreenRenderer(Protocol):
    """Protocol for pluggable screen renderers."""

    name: str

    def render(
        self,
        text: str,
        output_path: Path,
        cols: int,
        rows: int,
    ) -> None:
        ...


class SvgRenderer:
    """SVG screen renderer (current behavior)."""

    name = "svg"

    def render(
        self,
        text: str,
        output_path: Path,
        cols: int,
        rows: int,
    ) -> None:
        from .screen import render_svg

        render_svg(text, output_path, cols, rows)
