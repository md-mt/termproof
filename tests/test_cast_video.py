from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from termproof.attributed import AttributedCell, AttributedScreen
from termproof.cast_video import (
    DEFAULT_IDLE_TIME_LIMIT,
    RsvgFfmpegBackend,
    frames_from_cast,
    read_cast,
)
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

    def test_a_missing_tool_names_itself(self) -> None:
        backend = self._backend(rsvg_path=None)
        with mock.patch("shutil.which", return_value=None):
            with self.assertRaises(RuntimeError) as raised:
                backend.render(self.cast, self.tmp / "out.mp4", 4)
        self.assertIn("rsvg-convert", str(raised.exception))

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


if __name__ == "__main__":
    unittest.main()
