from __future__ import annotations

import importlib.util
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from termproof.attributed import AttributedCell, AttributedScreen, attributed_screen_from_text
from termproof.cast_video import (
    DEFAULT_CHECKPOINT_HOLD,
    DEFAULT_FPS,
    DEFAULT_IDLE_TIME_LIMIT,
    MIN_CHECKPOINT_HOLD,
    RsvgFfmpegBackend,
    append_checkpoint_frames,
    frames_from_cast,
    read_cast,
)
from termproof.collector import CapturedStep, CaptureKind
from termproof.config import SvgRenderConfig, VideoConfig


class _FakeReplay:
    """Accumulates fed text; each snapshot is a one-cell screen of it."""

    def __init__(self, columns: int, rows: int) -> None:
        self.columns = columns
        self.rows = rows
        self.text = ""

    def feed(self, data: str) -> None:
        self.text += data

    def snapshot(self) -> AttributedScreen:
        return AttributedScreen(rows=((AttributedCell(text=self.text or " "),),))


def _fake_factory(columns: int, rows: int) -> _FakeReplay:
    return _FakeReplay(columns, rows)


class _RecordingRunner:
    def __init__(self) -> None:
        self.calls: list[tuple[str, list[str], int]] = []

    def __call__(self, executable: str, args: list[str], timeout: int) -> None:
        self.calls.append((executable, args, timeout))
        if "--output" in args:
            Path(args[args.index("--output") + 1]).write_bytes(b"\x89PNG")


def _write_cast(path: Path, events: list[tuple[float, str]], width: int = 80, height: int = 24) -> None:
    lines = [json.dumps({"version": 2, "width": width, "height": height})]
    lines.extend(json.dumps([t, "o", data]) for t, data in events)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


class ReadCastTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)

    def test_header_and_output_events(self) -> None:
        cast = self.tmp / "s.cast"
        _write_cast(cast, [(0.0, "a"), (0.5, "b")], width=100, height=30)
        header, events = read_cast(cast)
        self.assertEqual(100, header["width"])
        self.assertEqual([(0.0, "a"), (0.5, "b")], list(events))

    def test_input_events_are_ignored(self) -> None:
        cast = self.tmp / "s.cast"
        cast.write_text(
            "\n".join(
                [
                    json.dumps({"version": 2, "width": 80, "height": 24}),
                    json.dumps([0.0, "i", "typed"]),
                    json.dumps([0.1, "o", "shown"]),
                ]
            )
            + "\n",
            encoding="utf-8",
        )
        _, events = read_cast(cast)
        self.assertEqual([(0.1, "shown")], list(events))

    def test_an_empty_cast_yields_nothing(self) -> None:
        cast = self.tmp / "s.cast"
        cast.write_text("", encoding="utf-8")
        header, events = read_cast(cast)
        self.assertEqual({}, header)
        self.assertEqual([], list(events))


class FrameTimingTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.cast = Path(self._tmp.name) / "s.cast"

    def _frames(self, events: list[tuple[float, str]], **kwargs: object) -> list[AttributedScreen]:
        """Frames with no closing hold, so counts here are the sampling alone.

        The hold is a fixed tail; leaving it on would add a constant to every
        expected count in this class and obscure what each case is measuring.
        `test_the_final_frame_is_held_rather_than_flashed` covers it.
        """
        kwargs.setdefault("last_frame_duration", 0.0)
        _write_cast(self.cast, events)
        return frames_from_cast(self.cast, replay_factory=_fake_factory, **kwargs)  # type: ignore[arg-type]

    def test_one_frame_per_interval_of_playback(self) -> None:
        # 1s of activity at 4 fps: frames at 0.00, 0.25, 0.50, 0.75, 1.00.
        events = [(i / 10, "x") for i in range(11)]
        self.assertEqual(5, len(self._frames(events, fps=4)))

    def test_an_idle_gap_is_clamped_not_replayed_in_real_time(self) -> None:
        # 60s of silence would be 240 frames at 4 fps without the clamp.
        frames = self._frames([(0.0, "a"), (60.0, "b")], fps=4, idle_time_limit=1.0)
        self.assertEqual(5, len(frames))

    def test_the_clamp_is_configurable(self) -> None:
        few = self._frames([(0.0, "a"), (60.0, "b")], fps=4, idle_time_limit=0.25)
        many = self._frames([(0.0, "a"), (60.0, "b")], fps=4, idle_time_limit=2.0)
        self.assertLess(len(few), len(many))

    def test_time_going_backwards_does_not_rewind_playback(self) -> None:
        frames = self._frames([(0.0, "a"), (5.0, "b"), (1.0, "c")], fps=4)
        self.assertGreater(len(frames), 0)

    def test_the_last_frame_is_always_the_final_screen(self) -> None:
        frames = self._frames([(0.0, "a"), (0.05, "b")], fps=1)
        self.assertEqual("ab", frames[-1].rows[0][0].text)

    def test_the_final_screen_is_not_appended_twice(self) -> None:
        # Sampling already captured the end state, so the tail guard must not
        # add a second identical frame.
        frames = self._frames([(0.0, "a")], fps=1000)
        self.assertEqual([f.rows[0][0].text for f in frames], ["a"])

    def test_a_cast_with_no_output_still_yields_one_frame(self) -> None:
        self.assertEqual(1, len(self._frames([], fps=24)))

    def test_the_final_frame_is_held_rather_than_flashed(self) -> None:
        """The last frame is the one a reviewer opened the video for.

        Without a hold it occupies a single frame -- 42ms at 24fps -- so the
        state the run ended in is gone before it can be read. `agg_ffmpeg` gets
        this from agg's own `--last-frame-duration`, which this backend was
        ignoring.
        """
        frames = self._frames([(0.0, "a"), (0.5, "b")], fps=4, last_frame_duration=2.0)
        self.assertEqual(8, sum(1 for frame in frames if frame == frames[-1]))

    def test_a_screen_repeated_earlier_does_not_shorten_the_hold(self) -> None:
        """Only the tail counts: an identical screen mid-session is another moment."""
        frames = self._frames([(0.0, "a"), (5.0, "")], fps=2, last_frame_duration=1.0)
        tail = 0
        while tail < len(frames) and frames[-1 - tail] == frames[-1]:
            tail += 1
        self.assertGreaterEqual(tail, 2)

    def test_grid_size_comes_from_the_cast_header(self) -> None:
        _write_cast(self.cast, [(0.0, "x")], width=132, height=50)
        captured: list[_FakeReplay] = []

        def factory(columns: int, rows: int) -> _FakeReplay:
            replay = _FakeReplay(columns, rows)
            captured.append(replay)
            return replay

        frames_from_cast(self.cast, replay_factory=factory)  # type: ignore[arg-type]
        self.assertEqual((132, 50), (captured[0].columns, captured[0].rows))


class RsvgFfmpegBackendTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        self.cast = self.tmp / "s.cast"
        _write_cast(self.cast, [(0.0, "a"), (0.5, "b")])
        self.runner = _RecordingRunner()

    def _backend(self, **kwargs: object) -> RsvgFfmpegBackend:
        defaults: dict[str, object] = {
            "rsvg_path": "/fake/rsvg-convert",
            "ffmpeg_path": "/fake/ffmpeg",
            "runner": self.runner,
            "replay_factory": _fake_factory,
        }
        defaults.update(kwargs)
        return RsvgFfmpegBackend(**defaults)  # type: ignore[arg-type]

    def test_one_rasterizer_call_per_frame_then_one_encode(self) -> None:
        self._backend().render(self.cast, self.tmp / "out.mp4", 4)
        rsvg_calls = [c for c in self.runner.calls if c[0] == "/fake/rsvg-convert"]
        ffmpeg_calls = [c for c in self.runner.calls if c[0] == "/fake/ffmpeg"]
        self.assertEqual(1, len(ffmpeg_calls))
        self.assertGreater(len(rsvg_calls), 0)
        self.assertEqual(self.runner.calls[-1][0], "/fake/ffmpeg")

    def test_frames_are_numbered_for_the_ffmpeg_pattern(self) -> None:
        self._backend().render(self.cast, self.tmp / "out.mp4", 4)
        first_png = self.runner.calls[0][1][1]
        self.assertTrue(first_png.endswith("frame-00000.png"), first_png)
        self.assertIn("frame-%05d.png", " ".join(self.runner.calls[-1][1]))

    def test_chroma_is_not_subsampled(self) -> None:
        args = self._backend().ffmpeg_args("f-%05d.png", self.tmp / "out.mp4", 24)
        self.assertIn("yuv444p", args)
        self.assertNotIn("yuv420p", args)

    def test_encode_settings_come_from_the_video_config(self) -> None:
        backend = self._backend(video=VideoConfig(crf=30, preset="ultrafast", tune="zerolatency"))
        args = backend.ffmpeg_args("f-%05d.png", self.tmp / "out.mp4", 24)
        self.assertEqual("30", args[args.index("-crf") + 1])
        self.assertEqual("ultrafast", args[args.index("-preset") + 1])
        self.assertEqual("zerolatency", args[args.index("-tune") + 1])

    def test_the_frame_rate_reaches_ffmpeg(self) -> None:
        args = self._backend().ffmpeg_args("f-%05d.png", self.tmp / "out.mp4", 12)
        self.assertEqual("12", args[args.index("-framerate") + 1])

    def test_the_svg_config_reaches_the_frames(self) -> None:
        backend = self._backend(svg=SvgRenderConfig(bg="#ff0000"))
        written: list[str] = []
        original = self.runner.__call__

        def capture(executable: str, args: list[str], timeout: int) -> None:
            if executable == "/fake/rsvg-convert":
                written.append(Path(args[-1]).read_text(encoding="utf-8"))
            original(executable, args, timeout)

        backend.runner = capture  # type: ignore[assignment]
        backend.render(self.cast, self.tmp / "out.mp4", 4)
        self.assertTrue(all("#ff0000" in svg for svg in written))

    def test_scratch_frames_do_not_survive_the_call(self) -> None:
        self._backend().render(self.cast, self.tmp / "out.mp4", 4)
        scratch = Path(self.runner.calls[0][1][1]).parent
        self.assertFalse(scratch.exists())

    def test_output_directories_are_created(self) -> None:
        out = self.tmp / "nested" / "out.mp4"
        self._backend().render(self.cast, out, 4)
        self.assertTrue(out.parent.is_dir())

    def test_the_hold_does_not_re_rasterize_the_same_frame(self) -> None:
        """A 3s hold at 24fps is 72 identical frames; rasterizing each is waste."""
        present: list[str] = []

        def runner(executable: str, args: list[str], timeout: int) -> None:
            if executable == "/fake/ffmpeg":
                # The scratch directory is deleted on return, so the encoder's
                # view of it has to be captured while it still exists.
                present.extend(
                    sorted(p.name for p in Path(args[args.index("-i") + 1]).parent.glob("*.png"))
                )
                return
            self.runner(executable, args, timeout)

        expected = frames_from_cast(
            self.cast, fps=4, last_frame_duration=2.0, replay_factory=_fake_factory
        )
        self._backend(last_frame_duration=2.0, runner=runner).render(
            self.cast, self.tmp / "out.mp4", 4
        )
        # Every frame the encoder needs exists, contiguously numbered...
        self.assertEqual(len(expected), len(present))
        self.assertEqual(
            [f"frame-{i:05d}.png" for i in range(len(expected))], present
        )
        # ...but the held frame was rasterized once, not once per repeat.
        self.assertLess(len(self.runner.calls), len(expected))

    def test_a_configured_last_frame_duration_is_honoured(self) -> None:
        from termproof.config import EvidenceConfig

        backend = RsvgFfmpegBackend.from_config(
            EvidenceConfig(video=VideoConfig(last_frame_duration=5.0))
        )
        self.assertEqual(5.0, backend.last_frame_duration)

    def test_a_missing_tool_names_itself_and_the_alternative(self) -> None:
        backend = self._backend(rsvg_path=None)
        with mock.patch("shutil.which", return_value=None):
            with self.assertRaises(RuntimeError) as raised:
                backend.render(self.cast, self.tmp / "out.mp4", 4)
        message = str(raised.exception)
        self.assertIn("rsvg-convert", message)
        self.assertIn("librsvg", message)
        self.assertIn("agg_ffmpeg", message)

    def test_a_missing_ffmpeg_names_itself_and_the_alternative(self) -> None:
        """The second tool must be as diagnosable as the first."""
        backend = self._backend(ffmpeg_path=None)
        with mock.patch("shutil.which", return_value=None):
            with self.assertRaises(RuntimeError) as raised:
                backend.render(self.cast, self.tmp / "out.mp4", 4)
        message = str(raised.exception)
        self.assertIn("ffmpeg", message)
        self.assertIn("agg_ffmpeg", message)

    def test_a_rasterizer_failure_propagates(self) -> None:
        def failing(executable: str, args: list[str], timeout: int) -> None:
            raise subprocess.CalledProcessError(1, [executable, *args])

        with self.assertRaises(subprocess.CalledProcessError):
            self._backend(runner=failing).render(self.cast, self.tmp / "out.mp4", 4)

    def test_idle_limit_defaults_when_the_config_leaves_it_unset(self) -> None:
        from termproof.config import EvidenceConfig

        backend = RsvgFfmpegBackend.from_config(EvidenceConfig())
        self.assertEqual(DEFAULT_IDLE_TIME_LIMIT, backend.idle_time_limit)

    def test_a_configured_idle_limit_is_honoured(self) -> None:
        from termproof.config import EvidenceConfig

        backend = RsvgFfmpegBackend.from_config(EvidenceConfig(video=VideoConfig(idle_time_limit=3.0)))
        self.assertEqual(3.0, backend.idle_time_limit)

    def test_convert_returns_where_the_video_landed(self) -> None:
        # The seam `EvidenceCollector.record_session` drives: `render` returns
        # nothing, so a caller that wants a video path has to be handed one.
        out = self.tmp / "elsewhere.mp4"
        self.assertEqual(out, self._backend().convert(self.cast, out))
        self.assertEqual(self.runner.calls[-1][0], "/fake/ffmpeg")
        self.assertIn(str(out), self.runner.calls[-1][1])

    def test_convert_defaults_the_video_beside_the_cast(self) -> None:
        self.assertEqual(self.tmp / "s.mp4", self._backend().convert(self.cast))

    def test_convert_encodes_at_the_rate_rust_defaults_to(self) -> None:
        # An unconfigured backend is the counterpart of `CastVideoConverter`'s
        # own default, so the two implementations record at one frame rate.
        self._backend().convert(self.cast)
        self.assertIn(str(DEFAULT_FPS), self.runner.calls[-1][1])

    def test_convert_honours_a_configured_frame_rate(self) -> None:
        self._backend(video=VideoConfig(fps=12)).convert(self.cast)
        self.assertIn("12", self.runner.calls[-1][1])


#: Replaying an appended cast through the real emulator is the strongest check
#: on it, and the only one here that needs a third-party package. Skipped rather
#: than dropped so `scripts/run_stdlib_tests.py`, which installs nothing, still
#: runs everything else in this class.
requires_pyte = unittest.skipUnless(importlib.util.find_spec("pyte"), "pyte is not installed")


def _step(
    index: int, label: str, screen: str, kind: CaptureKind = CaptureKind.CHECKPOINT
) -> CapturedStep:
    return CapturedStep(
        index=index,
        label=label,
        kind=kind,
        screen=screen,
        attributed=attributed_screen_from_text(screen, columns=80, rows=24),
    )


class AppendCheckpointFramesTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)
        self.cast = self.tmp / "session.cast"

    def _events(self) -> list[tuple[float, str]]:
        """Every event in the cast as ``(timestamp, data)``, header dropped."""
        lines = self.cast.read_text(encoding="utf-8").splitlines()
        parsed = [json.loads(line) for line in lines[1:]]
        return [(event[0], event[2]) for event in parsed]

    def test_checkpoints_are_appended_in_capture_order(self) -> None:
        _write_cast(self.cast, [(0.5, "live")])
        steps = [_step(0, "one", "first"), _step(1, "two", "second")]
        self.assertEqual(2, append_checkpoint_frames(self.cast, steps))

        events = self._events()
        # The session's own event, the two checkpoints, and the closing hold.
        self.assertEqual(4, len(events))
        self.assertEqual("live", events[0][1])
        self.assertTrue(events[1][1].endswith("first"), events[1][1])
        self.assertTrue(events[2][1].endswith("second"), events[2][1])
        self.assertEqual("\x1b[m", events[3][1])

    def test_timestamps_continue_from_the_session_and_only_increase(self) -> None:
        _write_cast(self.cast, [(0.5, "a"), (2.25, "b")])
        steps = [_step(0, "one", "first"), _step(1, "two", "second")]
        append_checkpoint_frames(self.cast, steps, hold_seconds=1.5)

        times = [at for at, _ in self._events()]
        self.assertEqual([0.5, 2.25, 3.75, 5.25, 6.75], times)
        self.assertTrue(all(b > a for a, b in zip(times, times[1:], strict=False)))

    def test_the_hold_is_the_gap_between_frames_and_defaults(self) -> None:
        _write_cast(self.cast, [(0.0, "a")])
        steps = [_step(0, "one", "first"), _step(1, "two", "second")]
        append_checkpoint_frames(self.cast, steps)

        # The last checkpoint is held as long as the ones before it, which is
        # what the closing event is for.
        #
        # Spelled 3.0 rather than DEFAULT_CHECKPOINT_HOLD: written in terms of
        # the constant, this passes just as happily if the two implementations'
        # defaults drift apart, which is the one thing it is here to stop. The
        # Rust side pins the same literal.
        self.assertEqual([0.0, 3.0, 6.0, 9.0], [at for at, _ in self._events()])
        self.assertEqual(3.0, DEFAULT_CHECKPOINT_HOLD)

    def test_a_fractional_hold_is_rounded_the_way_rust_rounds(self) -> None:
        # Two claims in one case, because one input carries both.
        #
        # That rounding happens at all: unrounded, these timestamps go out as
        # 0.7000005 and 1.1000005000000002, and a reviewer reading them should
        # not have to.
        #
        # And that it is *Rust's* rounding: the base carries a seventh decimal,
        # which is what a Rust-recorded cast ends on -- `CastRecorder` writes
        # `as_secs_f64()` unrounded -- and that is where the two rules part.
        # `round(at, 6)` would write 0.9 and 1.3 for the second and fourth
        # frames where the transcribed rule writes 0.900001 and 1.300001. A
        # whole-decimal base does not discriminate: both rules agree on every
        # frame, and a test built on one would pass with the transcription
        # reverted.
        #
        # Asserted as text because the Rust side asserts the same strings.
        _write_cast(self.cast, [(0.5000005, "a")])
        steps = [_step(0, "one", "first"), _step(1, "two", "second"), _step(2, "three", "third")]
        append_checkpoint_frames(self.cast, steps, hold_seconds=0.2)

        written = self.cast.read_text(encoding="utf-8").splitlines()[1:]
        self.assertEqual(
            ["0.5000005", "0.700001", "0.900001", "1.100001", "1.300001"],
            [line.lstrip("[").split(",")[0] for line in written],
        )

    def test_no_checkpoints_is_a_silent_no_op(self) -> None:
        _write_cast(self.cast, [(0.0, "a")])
        before = self.cast.read_text(encoding="utf-8")
        self.assertEqual(0, append_checkpoint_frames(self.cast, []))
        self.assertEqual(before, self.cast.read_text(encoding="utf-8"))

        # No-op, not merely harmless: a run that captured nothing must not
        # fail, and must not need the cast to be there to be told so.
        self.assertEqual(0, append_checkpoint_frames(self.tmp / "absent.cast", []))

    @requires_pyte
    def test_the_appended_cast_still_replays(self) -> None:
        _write_cast(self.cast, [(0.0, "live")])
        steps = [_step(0, "one", "first"), _step(1, "two", "second")]
        append_checkpoint_frames(self.cast, steps)

        # Replaying it is the strongest statement that it is still a cast: the
        # player parses the header, every event and every payload.
        painted = [f.text_lines(trim_right=True)[0] for f in frames_from_cast(self.cast)]
        self.assertEqual("second", painted[-1])
        self.assertIn("live", painted)
        self.assertLess(painted.index("first"), painted.index("second"))

    def test_the_appended_cast_is_still_a_v2_cast(self) -> None:
        _write_cast(self.cast, [(0.0, "live")])
        steps = [_step(0, "one", "first"), _step(1, "two", "second")]
        append_checkpoint_frames(self.cast, steps)

        header, events = read_cast(self.cast)
        self.assertEqual(2, header["version"])
        self.assertEqual(80, header["width"])
        # The header is untouched and every line under it still reads as an
        # output event: the session's, the two checkpoints, and the hold.
        self.assertEqual(4, len(list(events)))

    @requires_pyte
    def test_a_multi_line_screen_is_repainted_row_by_row(self) -> None:
        # A cast payload goes to a raw terminal, where a bare newline drops a
        # row without returning the carriage and the screen comes back as a
        # staircase.
        _write_cast(self.cast, [(0.0, "live")])
        append_checkpoint_frames(self.cast, [_step(0, "menu", "MENU\nitem")])

        text = frames_from_cast(self.cast)[-1].text_lines(trim_right=True)
        self.assertEqual("MENU", text[0])
        self.assertEqual("item", text[1])

    @requires_pyte
    def test_a_scroll_region_left_by_the_session_does_not_eat_rows(self) -> None:
        # The failure this guards is the quietest one available: a full-screen
        # TUI leaves DECSTBM set, the evidence screen is taller than the region,
        # and painting it scrolls rows out of existence. The cast stays valid
        # and plays fine; it just shows a screen that was never captured.
        header = json.dumps({"version": 2, "width": 20, "height": 8})
        event = json.dumps([0.0, "o", "\x1b[3;6r\x1b[?6h"])
        self.cast.write_text(f"{header}\n{event}\n", encoding="utf-8")

        rows = [f"L{i}" for i in range(1, 9)]
        append_checkpoint_frames(self.cast, [_step(0, "full", "\n".join(rows))])

        self.assertEqual(
            rows,
            frames_from_cast(self.cast)[-1].text_lines(trim_right=True),
            "rows were scrolled out of the region instead of painted",
        )

    @requires_pyte
    def test_a_checkpoint_paints_over_the_screen_before_it(self) -> None:
        # Each screen is a whole picture, so a shorter one must not leave the
        # tail of a longer one behind it.
        _write_cast(self.cast, [(0.0, "live")])
        steps = [_step(0, "long", "abcdefgh"), _step(1, "short", "xy")]
        append_checkpoint_frames(self.cast, steps)

        self.assertEqual("xy", frames_from_cast(self.cast)[-1].text_lines(trim_right=True)[0])

    @requires_pyte
    def test_the_failure_screen_is_appended_too(self) -> None:
        # The frame a reviewer most wants held is the one the run died on.
        _write_cast(self.cast, [(0.0, "live")])
        steps = [_step(0, "ok", "fine"), _step(1, "boom", "ERROR", CaptureKind.FAILURE)]
        self.assertEqual(2, append_checkpoint_frames(self.cast, steps))

        self.assertEqual("ERROR", frames_from_cast(self.cast)[-1].text_lines(trim_right=True)[0])

    def test_a_cast_missing_its_final_newline_is_not_spliced(self) -> None:
        # A recorder killed mid-write leaves one; appending blind would fuse
        # two events into one unparseable line.
        header = json.dumps({"version": 2, "width": 80, "height": 24})
        self.cast.write_text(f"{header}\n[0.0, \"o\", \"a\"]", encoding="utf-8")

        append_checkpoint_frames(self.cast, [_step(0, "one", "first")])
        self.assertEqual(3, len(self._events()))

    def test_a_hold_that_would_stall_the_timestamps_is_rejected(self) -> None:
        _write_cast(self.cast, [(0.0, "a")])
        steps = [_step(0, "one", "first")]
        # 1e-9 is the case the name is about: positive and finite, so an
        # `isfinite and > 0` check waves it through, and then six-decimal
        # timestamps land every appended event on the same one.
        #
        # 6e-7 and 7.5e-7 are what make the *floor* the thing under test rather
        # than any check that happens to reject a tiny number. They are the
        # holds that round up to a whole microsecond without advancing by one,
        # so they are accepted by a check on the rounded hold and still collide
        # -- 6e-7 gives 1e-06, 1e-06, 2e-06, 2e-06. A hold below half a
        # microsecond cannot make that point: 5e-7 and smaller round to zero, so
        # the weaker check rejects them too and the test passes either way.
        for bad in (0.0, -1.0, float("nan"), float("inf"), 1e-9, 6e-7, 7.5e-7):
            with self.subTest(hold=bad):
                with self.assertRaises(ValueError):
                    append_checkpoint_frames(self.cast, steps, hold_seconds=bad)
        # Rejected before anything was written.
        self.assertEqual(1, len(self._events()))

        # The floor is a floor, not a value swept up to. Spelled 1e-6 rather
        # than MIN_CHECKPOINT_HOLD for the reason the default hold is spelled
        # 3.0: in terms of the constant this follows it wherever it goes, and
        # the two implementations would be free to disagree about which holds
        # they accept.
        self.assertEqual(1e-6, MIN_CHECKPOINT_HOLD)
        append_checkpoint_frames(self.cast, steps, hold_seconds=1e-6)
        times = [at for at, _ in self._events()]
        self.assertTrue(all(b > a for a, b in zip(times, times[1:], strict=False)))

    def test_the_event_encoder_is_pinned_to_what_rust_emits(self) -> None:
        # The Rust implementation writes these same lines with `serde_json`:
        # compact separators, non-ASCII left as UTF-8. Python's defaults are
        # neither, so the encoder is pinned and this is what holds it there.
        _write_cast(self.cast, [(0.0, "a")])
        append_checkpoint_frames(self.cast, [_step(0, "unicode", "héllo")], hold_seconds=1.0)

        appended = self.cast.read_text(encoding="utf-8").splitlines()[-2]
        self.assertEqual('[1.0,"o","\\u001b[m\\u001b[r\\u001b[H\\u001b[2Jhéllo"]', appended)


if __name__ == "__main__":
    unittest.main()
