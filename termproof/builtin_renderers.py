from __future__ import annotations

import html
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from .config import EvidenceConfig, PngRenderConfig, SvgRenderConfig
from .protocols import ScreenRenderer as ScreenRenderer


class SvgRenderer:
    """SVG screen renderer."""

    name = "svg"
    extension = "svg"

    def __init__(self, config: SvgRenderConfig | None = None) -> None:
        self.config = config or SvgRenderConfig()

    @classmethod
    def from_config(cls, evidence: EvidenceConfig) -> SvgRenderer:
        return cls(evidence.svg)

    def render(
        self,
        text: str,
        output_path: Path,
        cols: int,
        rows: int,
    ) -> None:
        config = self.config
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


class PngRenderer:
    name = "png"
    extension = "png"

    def __init__(self, config: PngRenderConfig | None = None) -> None:
        self.config = config or PngRenderConfig()

    @classmethod
    def from_config(cls, evidence: EvidenceConfig) -> PngRenderer:
        return cls(evidence.png)

    def _font(self) -> ImageFont.ImageFont | ImageFont.FreeTypeFont:
        if self.config.font_path is None:
            return ImageFont.load_default()
        return ImageFont.truetype(
            self.config.font_path,
            self.config.font_size * self.config.scale,
        )

    def render(
        self,
        text: str,
        output_path: Path,
        cols: int,
        rows: int,
    ) -> None:
        config = self.config
        scale = config.scale
        font = self._font()
        bbox = font.getbbox("M")
        char_width = max(9 * scale, bbox[2] - bbox[0])
        line_height = max(18 * scale, bbox[3] - bbox[1] + 6 * scale)
        padding = config.padding * scale
        width = max(320 * scale, cols * char_width + padding * 2)
        height = max(160 * scale, rows * line_height + padding * 2)
        image = Image.new("RGB", (int(width), int(height)), config.bg)
        draw = ImageDraw.Draw(image)

        for index, line in enumerate(text.splitlines()[:rows] or [""]):
            y = padding + line_height * index
            draw.text((padding, y), line[:cols], font=font, fill=config.fg)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        image.save(output_path, format="PNG")
