"""MP4 recordings rendered frame by frame from the attributed grid.

``AggFfmpegBackend`` shells out to ``agg``, which draws the terminal its own
way. This backend replays the cast into the same attributed screen ``final.svg``
is rendered from, rasterizes each frame with ``rsvg-convert``, and stitches them
with ``ffmpeg``. A frame of the video and the *final* screenshot of the same
moment are then the same image, which matters when a reviewer is comparing them.

That correspondence does not extend to the per-step screenshots under
``steps/``. Those are attributed too now, when the session reported a grid, but
the grid is read from the live session at the moment of the step rather than
replayed from the cast — so a step image and a frame of the same moment are not
guaranteed to be the same bytes. See ``docs/evidence-quality.md``.

The cost is one rasterizer call per *distinct* frame, so this is slower than
``agg``. It buys consistency and needs no Rust toolchain or bundled binary. A
frame identical to the one before it is written by copying the rendered PNG,
which matters because an idle session and the closing hold are both long runs
of a single unchanging screen.

Needs ``rsvg-convert`` and ``ffmpeg`` on PATH.

:func:`append_checkpoint_frames` sits beside all of that and needs neither
tool. It writes the captured screens onto the end of a cast as held frames, so
a recording finishes by replaying the evidence sequence instead of stopping on
whatever the last keystroke painted — the reason a reviewer watches one
artifact rather than opening every still beside it. It works on a closed cast:
nothing about it needs the session that produced the file to still be running.
"""

from __future__ import annotations

import json
import math
import shutil
import tempfile
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from .attributed import AttributedScreen, attributed_screen_from_pyte, screen_svg
from .collector import CapturedStep
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

#: Seconds an appended checkpoint screen stays up before the next one paints.
#: Long enough to read a screen of terminal text, short enough that fifteen of
#: them are still a recording someone sits through. The same three seconds as
#: :data:`DEFAULT_LAST_FRAME_DURATION` and the Rust ``DEFAULT_CHECKPOINT_HOLD``,
#: so a recording's closing hold does not change pace depending on who wrote it.
DEFAULT_CHECKPOINT_HOLD = 3.0

# Repaint the whole grid: reset the pen, reset the scroll region, home the
# cursor, clear the screen. A checkpoint screen is a complete picture, not a
# delta, so it is painted over whatever the previous frame left rather than
# after it.
#
# `\x1b[2J` erases the display and leaves DECSTBM exactly as the recorded
# session set it. A full-screen TUI -- the class of program this package exists
# to record -- sets a scroll region and does not clear it on exit, so without
# `\x1b[r` a screen taller than the region scrolls inside it and rows of the
# evidence are destroyed on the way in. An eight-row screen painted into a
# region of rows 3-6 comes back as `L1 L2 L5 L6 L7 L8`: still a valid cast,
# still plays, simply not the screen that was captured. Resetting the margins
# also neutralises origin mode, which only relocates the origin relative to
# them.
#
# A soft reset (`\x1b[!p`) would cover more state in one sequence and is the
# obvious thing to reach for. It is not used because `avt` implements it and
# `pyte` does not, so the two replay paths this project renders through would
# disagree about what the frame says -- the one outcome worth avoiding more
# than the state it would have reset.
_REPAINT_PREFIX = "\x1b[m\x1b[r\x1b[H\x1b[2J"

# Written once after the last checkpoint, purely to keep the recording running
# for one more hold. A cast ends at its final event, so without it the last
# screen -- the one the run ended on, and the one a reviewer skipped to the end
# for -- would flash for an instant instead of being held like every screen
# before it. An SGR reset is the cheapest event that changes nothing on screen.
_HOLD_TERMINATOR = "\x1b[m"

#: Shortest hold that survives being written down. Timestamps go out at six
#: decimals, so a hold below a microsecond lands two frames on the same one
#: however positive it looked going in -- ``1e-9`` puts every appended event at
#: the session's end time.
#:
#: A whole microsecond, rather than a hold that merely *rounds* to one, because
#: rounding up is not advancing: ``6e-7`` rounds to ``1e-6`` and still writes
#: frames 1 and 2 at the same timestamp.
#:
#: This is a floor on the input, not a proof about the output, and the
#: difference shows at the floor itself: a hold of exactly ``1e-6`` on a cast
#: whose last event carries an exact half-microsecond -- ``999.9999995`` --
#: still collides its first two frames, because both round to ``1000.000001``.
#: It takes the floor exactly *and* a half-microsecond base together, so no
#: recorded session reaches it; every hold above the floor is safe at any base.
#: Stated rather than papered over, since the alternative is comparing against
#: the previous rounded value and carrying that state through the loop.
MIN_CHECKPOINT_HOLD = 1e-6


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


def _last_event_time(event_lines: Sequence[str]) -> float:
    """The latest timestamp already in the cast.

    The largest rather than the last: a cast is written in order, but reading
    the maximum costs nothing and keeps the monotonicity promise even against a
    file some other tool has already appended to out of order.
    """
    latest = 0.0
    for line in event_lines:
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(event, list) and event and isinstance(event[0], (int, float)):
            at = float(event[0])
            if math.isfinite(at):
                latest = max(latest, at)
    return latest


def _repaint(screen: str) -> str:
    """One screen's worth of output data.

    With the newlines a terminal needs rather than the ones a text file has: a
    cast payload goes to a raw terminal, where a bare newline drops a row
    without returning the carriage and the screen comes back as a staircase.
    """
    return _REPAINT_PREFIX + screen.replace("\r\n", "\n").replace("\n", "\r\n")


def _round_micros(at: float) -> float:
    """Six decimals, so a fractional hold reads as ``1.35`` rather than as the
    sixteen digits binary addition actually produces.

    Not ``round(at, 6)``. That rounds the exact decimal and breaks halves to
    even; Rust's ``(at * 1e6).round() / 1e6`` scales first and breaks halves
    away from zero. The two disagree on values these lines can carry -- ``5e-7``
    is the smallest -- and a rounding rule the two implementations almost share
    is worse than no rounding at all, so Rust's expression is transcribed
    instead. Timestamps here are non-negative by construction, which is what
    lets ``floor`` stand in for the away-from-zero half.
    """
    scaled = at * 1e6
    floor = math.floor(scaled)
    return (floor + 1 if scaled - floor >= 0.5 else floor) / 1e6


def _cast_event_line(at: float, data: str) -> str:
    """Serialise one ``[timestamp, "o", data]`` event, newline included.

    The encoder is pinned rather than left at the language default because the
    Rust implementation writes these same lines: compact separators and raw
    UTF-8 are what ``serde_json`` emits, so the two produce the same bytes for
    the same screens.
    """
    event = json.dumps([_round_micros(at), "o", data], ensure_ascii=False, separators=(",", ":"))
    return event + "\n"


def append_checkpoint_frames(
    cast_path: Path,
    steps: Sequence[CapturedStep],
    *,
    hold_seconds: float = DEFAULT_CHECKPOINT_HOLD,
) -> int:
    """Append each captured screen to *cast_path* as a held trailing frame.

    A cast stops at whatever the last keystroke painted, which is rarely the
    evidence -- the checkpoints that made the run reviewable have already
    scrolled away by then. This writes them back onto the end, in capture
    order, each one repainting the whole grid and held for *hold_seconds*
    (default :data:`DEFAULT_CHECKPOINT_HOLD`) before the next. A reviewer then
    watches one recording instead of opening every still beside it.

    Returns how many frames were appended. An empty *steps* is a silent no-op:
    the file is not opened, let alone rewritten.

    **What it does to the file.** Appends only. The header and every recorded
    event are left exactly as the session wrote them, and the new events carry
    on from the last timestamp in the file rather than restarting at zero, so
    the result is still a valid asciinema v2 cast with timestamps that only
    increase. The session does not have to be running -- this reads and appends
    to a closed file, which is what lets it run after the exit code is already
    in hand.

    Every captured step is appended, :attr:`~termproof.collector.CaptureKind.FAILURE`
    included. A run's failure screen is the frame a reviewer most wants held, so
    filtering by kind would drop exactly the wrong one.

    The first checkpoint lands one hold after the session's final event, which
    leaves the live ending on screen for a beat before the replay starts.

    :raises ValueError: if the cast is empty, or if *hold_seconds* is not a
        finite hold of at least :data:`MIN_CHECKPOINT_HOLD`. ``1e-9`` is
        rejected for the same reason ``0.0`` is: it leaves every appended event
        on the same timestamp once written at six decimals, which is the stall
        this promises not to produce.
    :raises OSError: if the cast cannot be read or appended to. Rust returns
        these as ``Err`` alongside the validation failures above; here they stay
        the exception the standard library already raised.
    """
    if not steps:
        return 0
    if not math.isfinite(hold_seconds) or hold_seconds < MIN_CHECKPOINT_HOLD:
        raise ValueError(
            f"checkpoint hold must be at least {MIN_CHECKPOINT_HOLD} seconds, got {hold_seconds}"
        )

    contents = cast_path.read_text(encoding="utf-8")
    lines = contents.splitlines()
    if not lines:
        raise ValueError(f"{cast_path} is empty: a cast has a header line")
    last_event_at = _last_event_time(lines[1:])

    # A cast written by a crashed recorder can lack its final newline, and
    # appending to it blind would splice two events into one unparseable line.
    appended = "" if contents.endswith("\n") else "\n"
    for offset, step in enumerate(steps, start=1):
        appended += _cast_event_line(last_event_at + hold_seconds * offset, _repaint(step.screen))
    appended += _cast_event_line(
        last_event_at + hold_seconds * (len(steps) + 1), _HOLD_TERMINATOR
    )

    with cast_path.open("a", encoding="utf-8") as handle:
        handle.write(appended)
    return len(steps)


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
        # Every frame goes through `rsvg-convert` at intrinsic size before it
        # reaches ffmpeg, so this is a raster path and takes the raster floor.
        style = svg_config.raster_style(columns, rows)
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
    "DEFAULT_CHECKPOINT_HOLD",
    "DEFAULT_FPS",
    "DEFAULT_IDLE_TIME_LIMIT",
    "DEFAULT_LAST_FRAME_DURATION",
    "FFMPEG",
    "MIN_CHECKPOINT_HOLD",
    "ReplayFactory",
    "RsvgFfmpegBackend",
    "ScreenReplay",
    "append_checkpoint_frames",
    "frames_from_cast",
    "read_cast",
]
