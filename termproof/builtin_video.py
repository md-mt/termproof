from __future__ import annotations

from pathlib import Path

from .config import EvidenceConfig, VideoConfig
from .protocols import VideoBackend as VideoBackend


class AggFfmpegBackend:
    """agg + ffmpeg video backend (current behavior)."""

    name = "agg_ffmpeg"
    # Distinguishes the built-in backend from caller-supplied custom
    # VideoBackend plugins: the built-in path is gated on host tools
    # (agg/ffmpeg), while custom plugin dispatch remains ungated.
    builtin = True

    def __init__(self, config: VideoConfig | None = None) -> None:
        self.config = config or VideoConfig()

    @classmethod
    def from_config(cls, evidence: EvidenceConfig) -> AggFfmpegBackend:
        return cls(evidence.video)

    def render(
        self,
        cast_path: Path,
        output_path: Path,
        fps: int,
    ) -> None:
        from .evidence import render_mp4

        render_mp4(cast_path, output_path, fps, self.config)
