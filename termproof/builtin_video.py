from __future__ import annotations

from pathlib import Path

from .protocols import VideoBackend as VideoBackend


class AggFfmpegBackend:
    """agg + ffmpeg video backend (current behavior)."""

    name = "agg_ffmpeg"
    # Distinguishes the built-in backend from caller-supplied custom
    # VideoBackend plugins: the built-in path is gated on host tools
    # (agg/ffmpeg), while custom plugin dispatch remains ungated.
    builtin = True

    def render(
        self,
        cast_path: Path,
        output_path: Path,
        fps: int,
    ) -> None:
        from .evidence import render_mp4

        render_mp4(cast_path, output_path, fps)
