"""MP4 recordings rendered frame by frame from the attributed grid.

``AggFfmpegBackend`` shells out to ``agg``, which draws the terminal its own
way. This backend replays the cast into the same attributed screen the
screenshots use, rasterizes each frame with ``rsvg-convert``, and stitches them
with ``ffmpeg``. A frame of the video and a screenshot of the same moment are
then the same image, which matters when a reviewer is comparing them.

The cost is one rasterizer call per *distinct* frame, so this is slower than
``agg``. It buys consistency and needs no Rust toolchain or bundled binary. A
frame identical to the one before it is written by copying the rendered PNG,
which matters because an idle session and the closing hold are both long runs
of a single unchanging screen.

Needs ``rsvg-convert`` and ``ffmpeg`` on PATH.
"""

from __future__ import annotations

import json
import shutil
import tempfile
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from .attributed import AttributedScreen, attributed_screen_from_pyte, screen_svg
from .config import EvidenceConfig, SvgRenderConfig, VideoConfig
from .rsvg import DEFAULT_TIMEOUT_SECONDS, RSVG_CONVERT, ToolRunner, run_tool

FFMPEG = "ffmpeg"
FFMPEG_TIMEOUT_SECONDS = 300

# What to install for each tool, so a missing-tool error is actionable rather
# than only descriptive.
_PACKAGE_FOR_TOOL = {RSVG_CONVERT: "librsvg", FFMPEG: "ffmpeg"}

# A cast records wall-clock time, so a session that sat idle for two minutes
# would spend two minutes of video on an unchanging screen. Clamping each gap
# keeps the pacing watchable without dropping any state the terminal passed
# through.
DEFAULT_IDLE_TIME_LIMIT = 1.0

# 2 fps sampled a 30s session 59 times and missed every transient state. 24 is
# the lowest rate at which the reference recording reads correctly.
DEFAULT_FPS = 24

# How long to hold the closing screen. The last frame is the state the run ended
# in, which is the one a reviewer opened the video for; at 24fps a single frame
# shows it for 42ms. Matches agg's own `--last-frame-duration` default, so the
# two video backends end a recording the same way.
DEFAULT_LAST_FRAME_DURATION = 3.0


class ScreenReplay(Protocol):
    """A terminal being replayed: fed bytes, asked for its current grid."""

    def feed(self, data: str) -> None: ...

    def snapshot(self) -> AttributedScreen: ...


class _PyteReplay:
    def __init__(self, columns: int, rows: int) -> None:
        import pyte

        self._screen = pyte.Screen(columns, rows)
        self._stream = pyte.Stream(self._screen)

    def feed(self, data: str) -> None:
        self._stream.feed(data)

    def snapshot(self) -> AttributedScreen:
        return attributed_screen_from_pyte(self._screen)


#: ``(columns, rows) -> ScreenReplay``. Injectable so the frame timing can be
#: tested without a terminal emulator installed.
ReplayFactory = Callable[[int, int], ScreenReplay]


def _pyte_replay(columns: int, rows: int) -> ScreenReplay:
    return _PyteReplay(columns, rows)


def read_cast(cast_path: Path) -> tuple[dict[str, Any], Iterator[tuple[float, str]]]:
    """Split a v2 cast into its header and its output events."""
    text = cast_path.read_text(encoding="utf-8").splitlines()
    header = json.loads(text[0]) if text else {}

    def events() -> Iterator[tuple[float, str]]:
        for line in text[1:]:
            if not line.strip():
                continue
            event = json.loads(line)
            if len(event) >= 3 and event[1] == "o":
                yield float(event[0]), event[2]

    return header, events()


def frames_from_cast(
    cast_path: Path,
    *,
    fps: int = DEFAULT_FPS,
    idle_time_limit: float = DEFAULT_IDLE_TIME_LIMIT,
    last_frame_duration: float = DEFAULT_LAST_FRAME_DURATION,
    columns: int = 100,
    rows: int = 30,
    replay_factory: ReplayFactory = _pyte_replay,
) -> list[AttributedScreen]:
    """Sample the replayed session at *fps*, clamping idle gaps.

    The final screen is always the last frame, so a recording never ends on a
    state the session had already left, and it is repeated for
    *last_frame_duration* seconds so it can actually be read.
    """
    header, events = read_cast(cast_path)
    replay = replay_factory(int(header.get("width", columns)), int(header.get("height", rows)))

    frames: list[AttributedScreen] = []
    frame_interval = 1.0 / fps
    next_frame_at = 0.0
    playback_time = 0.0
    previous_cast_time = 0.0

    for timestamp, data in events:
        playback_time += min(max(0.0, timestamp - previous_cast_time), idle_time_limit)
        previous_cast_time = timestamp
        replay.feed(data)
        while next_frame_at <= playback_time:
            frames.append(replay.snapshot())
            next_frame_at += frame_interval

    final = replay.snapshot()
    if not frames or frames[-1] != final:
        frames.append(final)

    # Hold the closing screen. Only the frames already at the tail count towards
    # the hold; an identical screen from earlier in the session is a different
    # moment. `render` writes the repeats by copying the rendered PNG, so this
    # costs disk rather than one rasterizer call per frame.
    held = 0
    while held < len(frames) and frames[-1 - held] == final:
        held += 1
    frames.extend([final] * (max(1, round(last_frame_duration * fps)) - held))
    return frames


@dataclass
class RsvgFfmpegBackend:
    """Render a cast to MP4 through the attributed grid."""

    name = "attributed_rsvg"
    # Not `builtin`: that flag gates the agg/ffmpeg tool check in
    # `render_artifacts`, and this backend does its own.
    svg: SvgRenderConfig | None = None
    video: VideoConfig | None = None
    idle_time_limit: float = DEFAULT_IDLE_TIME_LIMIT
    last_frame_duration: float = DEFAULT_LAST_FRAME_DURATION
    rsvg_path: str | None = None
    ffmpeg_path: str | None = None
    runner: ToolRunner = run_tool
    replay_factory: ReplayFactory = _pyte_replay

    @classmethod
    def from_config(cls, evidence: EvidenceConfig) -> RsvgFfmpegBackend:
        return cls(
            svg=evidence.svg,
            video=evidence.video,
            idle_time_limit=(
                DEFAULT_IDLE_TIME_LIMIT
                if evidence.video.idle_time_limit is None
                else evidence.video.idle_time_limit
            ),
            last_frame_duration=(
                DEFAULT_LAST_FRAME_DURATION
                if evidence.video.last_frame_duration is None
                else evidence.video.last_frame_duration
            ),
        )

    def _resolve(self, configured: str | None, tool: str) -> str:
        if configured is not None:
            return configured
        resolved = shutil.which(tool)
        if resolved is None:
            raise RuntimeError(
                f"{tool} is required by the {self.name!r} video backend but was not found on PATH. "
                f"Install {_PACKAGE_FOR_TOOL[tool]}, or use the default 'agg_ffmpeg' video backend."
            )
        return resolved

    def ffmpeg_args(self, pattern: str, output_path: Path, fps: int) -> list[str]:
        """The encode command, minus the executable."""
        video = self.video or VideoConfig()
        return [
            "-y",
            "-loglevel",
            "error",
            "-framerate",
            str(fps),
            "-i",
            pattern,
            "-c:v",
            "libx264",
            # yuv444p, not yuv420p: 4:2:0 subsamples chroma 2x2, which smears
            # the edges of coloured text. A terminal frame is almost entirely
            # text, so the extra bitrate is the right trade.
            "-pix_fmt",
            "yuv444p",
            "-crf",
            str(15 if video.crf is None else video.crf),
            "-preset",
            video.preset or "slower",
            "-tune",
            video.tune or "stillimage",
            "-movflags",
            "+faststart",
            str(output_path),
        ]

    def render(self, cast_path: Path, output_path: Path, fps: int) -> None:
        rsvg = self._resolve(self.rsvg_path, RSVG_CONVERT)
        ffmpeg = self._resolve(self.ffmpeg_path, FFMPEG)
        svg_config = self.svg or SvgRenderConfig()
        output_path.parent.mkdir(parents=True, exist_ok=True)

        frames = frames_from_cast(
            cast_path,
            fps=fps,
            idle_time_limit=self.idle_time_limit,
            last_frame_duration=self.last_frame_duration,
            replay_factory=self.replay_factory,
        )
        if not frames:
            raise RuntimeError(f"{cast_path} produced no frames to render")

        columns = max(frames[0].column_count, 1)
        rows = max(len(frames[0].rows), 1)
        style = svg_config.style(columns, rows)
        with tempfile.TemporaryDirectory(prefix="termproof-frames-") as tmpdir:
            scratch = Path(tmpdir)
            previous: tuple[AttributedScreen, Path] | None = None
            for index, frame in enumerate(frames):
                png_path = scratch / f"frame-{index:05d}.png"
                # ffmpeg needs a contiguous sequence, so a repeated screen still
                # needs its own file -- but not its own rasterizer call. An idle
                # session and the closing hold are both long runs of one screen.
                if previous is not None and previous[0] == frame:
                    shutil.copyfile(previous[1], png_path)
                    continue
                svg_path = scratch / f"frame-{index:05d}.svg"
                svg_path.write_text(screen_svg(frame, style), encoding="utf-8")
                self.runner(
                    rsvg,
                    ["--output", str(png_path), str(svg_path)],
                    DEFAULT_TIMEOUT_SECONDS,
                )
                previous = (frame, png_path)
            self.runner(
                ffmpeg,
                self.ffmpeg_args(str(scratch / "frame-%05d.png"), output_path, fps),
                FFMPEG_TIMEOUT_SECONDS,
            )


__all__ = [
    "DEFAULT_FPS",
    "DEFAULT_IDLE_TIME_LIMIT",
    "DEFAULT_LAST_FRAME_DURATION",
    "FFMPEG",
    "ReplayFactory",
    "RsvgFfmpegBackend",
    "ScreenReplay",
    "frames_from_cast",
    "read_cast",
]
