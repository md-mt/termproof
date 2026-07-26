from __future__ import annotations

from pathlib import Path
from typing import Protocol


class VideoBackend(Protocol):
    """Protocol for pluggable video renderers."""

    name: str

    def render(
        self,
        cast_path: Path,
        output_path: Path,
        fps: int,
    ) -> None:
        ...


class AggFfmpegBackend:
    """agg + ffmpeg video backend (current behavior)."""

    name = "agg_ffmpeg"

    def render(
        self,
        cast_path: Path,
        output_path: Path,
        fps: int,
    ) -> None:
        from .evidence import render_mp4

        render_mp4(cast_path, output_path, fps)
