"""PNG screenshots by rasterizing the attributed SVG with ``rsvg-convert``.

The Pillow renderer draws text itself, so it has no colour, no bold and no
per-cell alignment. This one renders the same SVG the ``svg`` renderer emits
and hands it to a rasterizer, which means the PNG and the SVG cannot drift.

Every external call goes through a :data:`ToolRunner`, so a host with its own
subprocess policy can supply one without reimplementing the renderer, and tests
can supply a fake.

Needs ``rsvg-convert`` on PATH (``librsvg`` on most distributions). Where that
is not available, ``builtin_renderers.PngRenderer`` still works.
"""

from __future__ import annotations

import shutil
import subprocess
import tempfile
from collections.abc import Callable
from pathlib import Path

from .attributed import AttributedScreen, attributed_screen_from_ansi_text, screen_svg
from .config import EvidenceConfig, SvgRenderConfig

#: ``(executable, args, timeout_seconds) -> None``, raising on failure.
ToolRunner = Callable[[str, list[str], int], None]

DEFAULT_TIMEOUT_SECONDS = 30
RSVG_CONVERT = "rsvg-convert"


def run_tool(executable: str, args: list[str], timeout: int) -> None:
    """Run *executable*, raising ``CalledProcessError`` on a non-zero exit."""
    result = subprocess.run(
        [executable, *args],
        capture_output=True,
        text=True,
        # Rasterizers emit non-UTF-8 bytes on stderr often enough that decoding
        # the diagnostic must not become the failure being diagnosed.
        errors="replace",
        timeout=timeout,
        check=False,
    )
    if result.returncode != 0:
        raise subprocess.CalledProcessError(
            result.returncode,
            [executable, *args],
            output=result.stdout,
            stderr=result.stderr,
        )


class RsvgPngRenderer:
    """Render a screen to PNG via the attributed SVG and ``rsvg-convert``."""

    name = "png_rsvg"
    extension = "png"

    def __init__(
        self,
        config: SvgRenderConfig | None = None,
        *,
        rsvg_path: str | None = None,
        runner: ToolRunner = run_tool,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self.config = config or SvgRenderConfig()
        self.rsvg_path = rsvg_path
        self.runner = runner
        self.timeout_seconds = timeout_seconds

    @classmethod
    def from_config(cls, evidence: EvidenceConfig) -> RsvgPngRenderer:
        return cls(evidence.svg)

    def resolve_rsvg(self) -> str:
        """Locate ``rsvg-convert``, preferring an explicitly configured path."""
        if self.rsvg_path is not None:
            return self.rsvg_path
        resolved = shutil.which(RSVG_CONVERT)
        if resolved is None:
            raise RuntimeError(
                f"{RSVG_CONVERT} is required by the {self.name!r} renderer but was not found on PATH. "
                "Install librsvg, or use the 'png' renderer."
            )
        return resolved

    def render(self, text: str, output_path: Path, cols: int, rows: int) -> None:
        self.render_attributed(
            attributed_screen_from_ansi_text(text, columns=cols, rows=rows),
            output_path,
            cols,
            rows,
        )

    def render_attributed(
        self,
        screen: AttributedScreen,
        output_path: Path,
        cols: int,
        rows: int,
    ) -> None:
        """Rasterize an already-attributed grid, keeping every attribute.

        ``raster_style`` rather than ``style``: ``rsvg-convert`` is invoked with
        no ``-w``/``-h``/``-z``, so it rasterises at intrinsic size and the PNG's
        pixel dimensions are the SVG's ``width``/``height``. The canvas floor the
        vector path does not want is exactly the floor this one does.
        """
        executable = self.resolve_rsvg()
        output_path.parent.mkdir(parents=True, exist_ok=True)
        markup = screen_svg(screen, self.config.raster_style(cols, rows))
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".svg",
            prefix="termproof-",
            encoding="utf-8",
            delete=False,
        ) as svg_file:
            svg_file.write(markup)
            svg_path = svg_file.name
        try:
            self.runner(
                executable,
                ["--output", str(output_path), svg_path],
                self.timeout_seconds,
            )
        finally:
            Path(svg_path).unlink(missing_ok=True)


__all__ = ["DEFAULT_TIMEOUT_SECONDS", "RSVG_CONVERT", "RsvgPngRenderer", "ToolRunner", "run_tool"]
