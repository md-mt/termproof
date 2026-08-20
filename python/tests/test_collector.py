"""Tests for the evidence collector.

Mirrors ``rust/crates/termproof/src/evidence/collector.rs``'s test module where
the behaviour is shared, so a divergence between the two implementations shows
up as a failing test on one side rather than as two manifests that disagree.
"""

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from termproof import collector as collector_module
from termproof import evidence as evidence_module
from termproof.attributed import AttributedCell, AttributedScreen
from termproof.collector import (
    CaptureKind,
    EvidenceCollector,
    EvidenceManifest,
    EvidencePublisher,
    RawOutput,
    Recording,
    RunIdentity,
    ScreenCapture,
    static_source,
)
from termproof.config import EvidenceConfig
from termproof.dedup import Deduper
from termproof.models import RunResult, StepResult


def _identity() -> RunIdentity:
    return RunIdentity(
        recipe_name="login",
        renderer="default",
        run_id="20240101-000000-login-default-1",
    )


def _run_result(recipe_name: str, renderer: str) -> RunResult:
    return RunResult(
        recipe_name=recipe_name,
        passed=True,
        exit_code=0,
        duration_seconds=1.0,
        priority="P0",
        execution="scripted",
        renderer=renderer,
        score=1.0,
        steps=[],
        assertions=[],
        artifacts={},
    )


class _Replay:
    """A source that is not a live session — the case the protocol exists for."""

    def __init__(self, frames: list[str]) -> None:
        self.frames = frames
        self.at = 0

    def capture_screen(self, raw: RawOutput) -> ScreenCapture:
        screen = self.frames[self.at]
        self.at += 1
        return ScreenCapture(
            screen=screen,
            attributed=None,
            raw_output="".join(self.frames[: self.at]) if raw is RawOutput.KEEP else None,
        )


class _RecordingRenderer:
    extension = "png"

    def __init__(self) -> None:
        self.rendered: list[Path] = []

    def render_attributed(self, screen, output_path: Path, cols: int, rows: int) -> None:
        self.rendered.append(output_path)
        output_path.write_text("png")


class _FailingRenderer:
    extension = "png"

    def render_attributed(self, screen, output_path: Path, cols: int, rows: int) -> None:
        raise ValueError("render failed")


class _Uploader:
    def __init__(self) -> None:
        self.uploaded: list[Path] = []

    def upload(self, path: Path) -> str | None:
        self.uploaded.append(path)
        return f"https://example/{path.name}"


class CaptureTest(unittest.TestCase):
    def test_captures_keep_their_order_and_labels(self) -> None:
        collector = EvidenceCollector()
        replay = _Replay(["one", "two"])
        collector.capture("first", replay)
        collector.capture_failure("blew-up", replay)

        steps = collector.steps
        self.assertEqual([0, 1], [s.index for s in steps])
        self.assertEqual(["first", "blew-up"], [s.label for s in steps])
        self.assertEqual(CaptureKind.FAILURE, steps[1].kind)

    def test_raw_output_is_kept_for_failures_only(self) -> None:
        # The log is cumulative, so a copy per checkpoint is quadratic and every
        # copy but the last is a prefix of a later one.
        collector = EvidenceCollector()
        collector.capture("ok", static_source("screen", raw_output="all of it"))
        collector.capture_failure("bad", static_source("screen", raw_output="all of it"))

        self.assertIsNone(collector.steps[0].raw_output)
        self.assertEqual("all of it", collector.steps[1].raw_output)

    def test_text_can_be_captured_without_a_source(self) -> None:
        collector = EvidenceCollector()
        collector.capture("live", static_source("from a session"))
        collector.capture_text("from-log", "recovered")
        collector.capture_text("post-mortem", "last screen", CaptureKind.FAILURE)

        steps = collector.steps
        self.assertEqual(3, len(steps))
        self.assertEqual(1, steps[1].index)
        self.assertEqual("recovered", steps[1].screen)
        # The default the READMEs document as the difference from Rust, which
        # takes the kind positionally.
        self.assertEqual(CaptureKind.CHECKPOINT, steps[1].kind)
        self.assertEqual(CaptureKind.FAILURE, steps[2].kind)
        self.assertIsNone(steps[2].raw_output)

    def test_a_source_that_reports_a_grid_keeps_it(self) -> None:
        grid = AttributedScreen(rows=((AttributedCell(text="A", fg="ff0000"),),))

        class _Attributed:
            def capture_screen(self, raw: RawOutput) -> ScreenCapture:
                return ScreenCapture(screen="A", attributed=grid)

        collector = EvidenceCollector()
        collector.capture("coloured", _Attributed())
        self.assertEqual(grid, collector.steps[0].attributed)


class PublishTest(unittest.TestCase):
    def test_text_is_written_even_with_no_renderer(self) -> None:
        # The text is what an assertion was evaluated against; a picture cannot
        # answer that question, so losing the renderer must not lose the text.
        with tempfile.TemporaryDirectory() as tmpdir:
            collector = EvidenceCollector()
            collector.capture("one", static_source("hello"))
            manifest = collector.publish(
                EvidencePublisher(directory=Path(tmpdir), identity=_identity())
            )

            self.assertEqual(1, len(manifest.steps))
            self.assertTrue(Path(manifest.steps[0].screen_text).exists())
            self.assertIsNone(manifest.steps[0].screenshot)

    def test_the_screen_is_written_verbatim(self) -> None:
        # No trailing newline added. The Rust implementation writes the screen
        # unaltered, and a newline on one side only makes the two documents'
        # artifacts differ while their manifests agree.
        with tempfile.TemporaryDirectory() as tmpdir:
            collector = EvidenceCollector()
            collector.capture_text("one", "line one\nline two")
            manifest = collector.publish(
                EvidencePublisher(directory=Path(tmpdir), identity=_identity())
            )

            written = Path(manifest.steps[0].screen_text).read_text(encoding="utf-8")
            self.assertEqual("line one\nline two", written)

    def test_an_identical_screen_reuses_the_image(self) -> None:
        renderer = _RecordingRenderer()
        with tempfile.TemporaryDirectory() as tmpdir:
            collector = EvidenceCollector()
            collector.capture_text("before", "same")
            collector.capture_text("after", "same")
            manifest = collector.publish(
                EvidencePublisher(
                    directory=Path(tmpdir), identity=_identity(), renderer=renderer
                )
            )

        self.assertEqual(1, len(renderer.rendered))
        self.assertIsNotNone(manifest.steps[1].same_as)
        self.assertEqual("before", manifest.steps[1].same_as.label)
        self.assertEqual(manifest.steps[0].screenshot, manifest.steps[1].screenshot)
        self.assertEqual([manifest.steps[1]], manifest.deduped())

    def test_a_colour_only_change_is_a_change(self) -> None:
        # Fingerprinting the grid rather than the text is the whole reason the
        # dedup key is not `step.screen`.
        plain = AttributedScreen(rows=((AttributedCell(text="A"),),))
        red = AttributedScreen(rows=((AttributedCell(text="A", fg="ff0000"),),))

        class _Fixed:
            def __init__(self, grid):
                self.grid = grid

            def capture_screen(self, raw: RawOutput) -> ScreenCapture:
                return ScreenCapture(screen="A", attributed=self.grid)

        renderer = _RecordingRenderer()
        with tempfile.TemporaryDirectory() as tmpdir:
            collector = EvidenceCollector()
            collector.capture("plain", _Fixed(plain))
            collector.capture("red", _Fixed(red))
            manifest = collector.publish(
                EvidencePublisher(
                    directory=Path(tmpdir), identity=_identity(), renderer=renderer
                )
            )

        self.assertEqual(2, len(renderer.rendered))
        self.assertIsNone(manifest.steps[1].same_as)

    def test_a_render_failure_is_recorded_and_does_not_stop_the_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            collector = EvidenceCollector()
            collector.capture_text("one", "hello")
            manifest = collector.publish(
                EvidencePublisher(
                    directory=Path(tmpdir),
                    identity=_identity(),
                    renderer=_FailingRenderer(),
                )
            )
            # The text still landed, which is the part a failure is diagnosed
            # from. Asserted inside the block, while the directory still exists.
            self.assertTrue(Path(manifest.steps[0].screen_text).exists())

        self.assertEqual("render failed", manifest.steps[0].error)
        self.assertIsNone(manifest.steps[0].screenshot)

    def test_a_failed_render_is_not_offered_for_reuse(self) -> None:
        """The next identical screen must not point at an image that was never made."""

        class _FailsOnce:
            extension = "png"

            def __init__(self) -> None:
                self.calls = 0

            def render_attributed(self, screen, output_path: Path, cols, rows) -> None:
                self.calls += 1
                if self.calls == 1:
                    raise ValueError("render failed")
                output_path.write_text("png")

        renderer = _FailsOnce()
        with tempfile.TemporaryDirectory() as tmpdir:
            collector = EvidenceCollector()
            collector.capture_text("one", "same")
            collector.capture_text("two", "same")
            manifest = collector.publish(
                EvidencePublisher(
                    directory=Path(tmpdir), identity=_identity(), renderer=renderer
                )
            )

        self.assertEqual(2, renderer.calls)
        self.assertIsNone(manifest.steps[1].same_as)
        self.assertIsNotNone(manifest.steps[1].screenshot)

    def test_uploads_are_best_effort(self) -> None:
        class _Broken:
            def upload(self, path: Path) -> str | None:
                raise RuntimeError("no network")

        with tempfile.TemporaryDirectory() as tmpdir:
            collector = EvidenceCollector()
            collector.capture_text("one", "hello")
            manifest = collector.publish(
                EvidencePublisher(
                    directory=Path(tmpdir),
                    identity=_identity(),
                    renderer=_RecordingRenderer(),
                    uploader=_Broken(),
                )
            )

        self.assertIsNone(manifest.steps[0].url)
        self.assertIsNotNone(manifest.steps[0].screenshot)

    def test_the_manifest_is_written_and_reads_back(self) -> None:
        uploader = _Uploader()
        with tempfile.TemporaryDirectory() as tmpdir:
            collector = EvidenceCollector()
            collector.capture_text("one", "hello")
            manifest = collector.publish(
                EvidencePublisher(
                    directory=Path(tmpdir),
                    identity=_identity(),
                    renderer=_RecordingRenderer(),
                    uploader=uploader,
                )
            )

            document = json.loads(manifest.path.read_text())

        self.assertEqual(1, document["manifest_version"])
        self.assertEqual("login", document["run"]["recipe_name"])
        self.assertEqual(1, len(document["steps"]))
        self.assertEqual("checkpoint", document["steps"][0]["kind"])
        self.assertEqual(1, len(uploader.uploaded))
        self.assertEqual({"evidence_manifest": str(manifest.path)}, manifest.artifacts())


class RecordingTest(unittest.TestCase):
    def test_recordings_reach_the_manifest_alongside_the_steps(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            collector = EvidenceCollector()
            collector.capture_text("one", "hello")
            collector.attach_recording(
                Recording(
                    label="full-session",
                    cast="/tmp/session.cast",
                    video="/tmp/session.mp4",
                    url="https://example/v",
                )
            )
            manifest = collector.publish(
                EvidencePublisher(directory=Path(tmpdir), identity=_identity())
            )
            document = json.loads(manifest.path.read_text())

        self.assertEqual(1, len(document["recordings"]))
        self.assertEqual("full-session", document["recordings"][0]["label"])

    def test_a_run_with_no_recordings_omits_the_key(self) -> None:
        # Additive precisely because it disappears when empty. If this breaks,
        # EVIDENCE_MANIFEST_VERSION has to move with it -- on both sides.
        with tempfile.TemporaryDirectory() as tmpdir:
            collector = EvidenceCollector()
            collector.capture_text("one", "hello")
            manifest = collector.publish(
                EvidencePublisher(directory=Path(tmpdir), identity=_identity())
            )
            document = json.loads(manifest.path.read_text())

        self.assertNotIn("recordings", document)


#: A cast with one event, the shape ``save_cast`` is expected to produce.
_A_CAST = '{"version":2,"width":10,"height":3}\n[0.5,"o","live"]\n'


def _save_a_cast(dest: Path) -> None:
    """Writes :data:`_A_CAST` and returns, the way a real ``save_cast`` would."""
    dest.write_text(_A_CAST, encoding="utf-8")


class _StubConverter:
    """Writes a fixed byte instead of shelling out to rsvg-convert and ffmpeg."""

    def __init__(self) -> None:
        self.converted: list[Path] = []

    def convert(self, cast_path: Path, video_path: Path | None = None) -> Path:
        output = cast_path.with_suffix(".mp4") if video_path is None else video_path
        self.converted.append(cast_path)
        output.write_text("mp4", encoding="utf-8")
        return output


class _BrokenConverter:
    def convert(self, cast_path: Path, video_path: Path | None = None) -> Path:
        raise RuntimeError("encoder exploded")


class _RefusingUploader:
    """Declines without saying why, which is all the protocol allows."""

    def upload(self, path: Path) -> str | None:
        return None


class _ExplodingUploader:
    def upload(self, path: Path) -> str | None:
        raise RuntimeError("store down")


class RecordSessionTest(unittest.TestCase):
    """The five-step session recording, and what each step's failure does.

    Mirrors ``record_session``'s tests in ``collector.rs``. Nothing here may
    raise: a recording is evidence about a run, not part of its verdict, so a
    test that fails by exception rather than by assertion is itself the bug.
    """

    def _collector(self) -> EvidenceCollector:
        collector = EvidenceCollector()
        collector.capture("only", static_source("screen text"))
        return collector

    def test_record_session_runs_the_five_steps_in_order(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            directory = Path(tmpdir) / "evidence"
            uploader = _Uploader()
            publisher = EvidencePublisher(
                directory=directory,
                identity=_identity(),
                renderer=_RecordingRenderer(),
                uploader=uploader,
                video_converter=_StubConverter(),
            )
            collector = self._collector()
            collector.record_session("full-session", publisher, _save_a_cast)

            recording = collector.recordings[0]
            self.assertEqual("full-session", recording.label)
            self.assertIsNone(recording.error)

            # 1. The cast is where the collector said it would be.
            cast = Path(recording.cast)
            self.assertEqual("recording-00-full-session.cast", cast.name)
            contents = cast.read_text(encoding="utf-8")

            # 2. With the captured screen appended to it, which is the whole
            #    reason step 2 exists: the session's own last frame is not the
            #    evidence.
            self.assertTrue(contents.startswith(_A_CAST), contents)
            self.assertIn("screen text", contents)

            # 3 and 4.
            video = Path(recording.video or "")
            self.assertEqual("recording-00-full-session.mp4", video.name)
            self.assertEqual("mp4", video.read_text(encoding="utf-8"))
            self.assertEqual(f"https://example/{video.name}", recording.url)
            self.assertEqual([video], uploader.uploaded)

            # 5. And all of it reaches the manifest, which is what a report
            #    reads.
            manifest = collector.publish(publisher)
            document = json.loads(manifest.path.read_text())

        self.assertEqual(1, len(document["recordings"]))
        self.assertEqual(str(video), document["recordings"][0]["video"])

    def test_a_cast_that_cannot_be_saved_stops_the_sequence(self) -> None:
        # Nothing downstream has anything to work on, so nothing downstream
        # runs -- and the recording says which step it was.
        def explode(dest: Path) -> None:
            raise RuntimeError("disk on fire")

        with tempfile.TemporaryDirectory() as tmpdir:
            uploader = _Uploader()
            converter = _StubConverter()
            publisher = EvidencePublisher(
                directory=Path(tmpdir),
                identity=_identity(),
                uploader=uploader,
                video_converter=converter,
            )
            collector = self._collector()
            collector.record_session("full-session", publisher, explode)

            recording = collector.recordings[0]
            self.assertEqual("save cast: disk on fire", recording.error)
            self.assertIsNone(recording.video)
            self.assertIsNone(recording.url)
            self.assertEqual([], converter.converted)
            self.assertEqual([], uploader.uploaded)
            self.assertFalse(Path(recording.cast).exists())

    def test_a_save_that_writes_nothing_is_the_save_step_failing(self) -> None:
        # A callable that returns normally and writes no file is step 1 going
        # wrong, not step 2 finding a missing file: blaming the append would
        # send a reader to the wrong code.
        with tempfile.TemporaryDirectory() as tmpdir:
            converter = _StubConverter()
            publisher = EvidencePublisher(
                directory=Path(tmpdir), identity=_identity(), video_converter=converter
            )
            collector = self._collector()
            collector.record_session("full-session", publisher, lambda dest: None)

            error = collector.recordings[0].error or ""
            self.assertTrue(error.startswith("save cast: "), error)
            self.assertIn("wrote no file", error)
            self.assertEqual([], converter.converted)

    def test_an_append_failure_does_not_stop_the_conversion(self) -> None:
        # Step 2 is the one non-fatal step: the cast is on disk either way, and
        # a recording that ends on the session is worth more than none.
        #
        # An empty cast is the append failure reachable through
        # `record_session`, the hold not being caller-supplied here. The stub
        # converter does not read the cast, so this can assert the video
        # survived; the Rust mirror uses a real `CastVideoConverter`, which
        # cannot read an empty cast either, and asserts instead that step 3 was
        # attempted and both failures were recorded.
        with tempfile.TemporaryDirectory() as tmpdir:
            publisher = EvidencePublisher(
                directory=Path(tmpdir),
                identity=_identity(),
                video_converter=_StubConverter(),
            )
            collector = self._collector()
            collector.record_session("empty", publisher, lambda dest: dest.write_text(""))

            recording = collector.recordings[0]
            error = recording.error or ""
            self.assertTrue(error.startswith("append checkpoint frames: "), error)
            self.assertIsNotNone(recording.video)

    def test_two_failures_are_both_recorded(self) -> None:
        # `error` is one field, so a second failure must not evict the first:
        # a report that names only the conversion sends a reader looking for a
        # broken encoder when the evidence never reached the cast either.
        #
        # The Rust mirror asserts this inside
        # `an_append_failure_does_not_stop_the_conversion`, where a real
        # `CastVideoConverter` cannot read the empty cast either and so fails
        # of its own accord.
        with tempfile.TemporaryDirectory() as tmpdir:
            publisher = EvidencePublisher(
                directory=Path(tmpdir),
                identity=_identity(),
                video_converter=_BrokenConverter(),
            )
            collector = self._collector()
            collector.record_session("empty", publisher, lambda dest: dest.write_text(""))

            error = collector.recordings[0].error or ""
            self.assertTrue(error.startswith("append checkpoint frames: "), error)
            self.assertTrue(error.endswith("; convert: encoder exploded"), error)

    def test_a_publisher_with_no_video_converter_says_so(self) -> None:
        # Not silence: `record_session` was called to produce a video, so a
        # publisher that cannot is a failure of the convert step.
        with tempfile.TemporaryDirectory() as tmpdir:
            publisher = EvidencePublisher(directory=Path(tmpdir), identity=_identity())
            collector = self._collector()
            collector.record_session("full-session", publisher, _save_a_cast)

            recording = collector.recordings[0]
            self.assertEqual("convert: no video converter configured", recording.error)
            # Steps 1 and 2 still happened, so the cast is still evidence.
            self.assertIn("screen text", Path(recording.cast).read_text(encoding="utf-8"))
            self.assertIsNone(recording.video)

    def test_a_failed_conversion_is_never_uploaded(self) -> None:
        # The error path a hand-written version gets wrong: uploading the path
        # a conversion did not produce, and reporting a store failure for a
        # video that was never encoded.
        with tempfile.TemporaryDirectory() as tmpdir:
            uploader = _Uploader()
            publisher = EvidencePublisher(
                directory=Path(tmpdir),
                identity=_identity(),
                uploader=uploader,
                video_converter=_BrokenConverter(),
            )
            collector = self._collector()
            collector.record_session("full-session", publisher, _save_a_cast)

            recording = collector.recordings[0]
            self.assertEqual("convert: encoder exploded", recording.error)
            self.assertIsNone(recording.video)
            self.assertIsNone(recording.url)
            self.assertEqual([], uploader.uploaded)

    def test_a_failed_upload_keeps_the_video(self) -> None:
        # Step 4 is last, so its failure costs the URL and nothing else. The
        # video is still on disk and still worth naming.
        with tempfile.TemporaryDirectory() as tmpdir:
            publisher = EvidencePublisher(
                directory=Path(tmpdir),
                identity=_identity(),
                uploader=_ExplodingUploader(),
                video_converter=_StubConverter(),
            )
            collector = self._collector()
            collector.record_session("full-session", publisher, _save_a_cast)

            recording = collector.recordings[0]
            self.assertEqual("upload: store down", recording.error)
            self.assertIsNotNone(recording.video)
            self.assertIsNone(recording.url)

    def test_an_uploader_that_declines_without_a_reason_still_names_the_step(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            publisher = EvidencePublisher(
                directory=Path(tmpdir),
                identity=_identity(),
                uploader=_RefusingUploader(),
                video_converter=_StubConverter(),
            )
            collector = self._collector()
            collector.record_session("full-session", publisher, _save_a_cast)

            recording = collector.recordings[0]
            self.assertEqual("upload: uploader returned no URL", recording.error)
            # Step 4 is last: a declined upload costs the URL, not the video.
            self.assertIsNotNone(recording.video)
            self.assertIsNone(recording.url)

    def test_a_publisher_with_no_uploader_is_not_a_failure(self) -> None:
        # Absent is not broken: a publisher without an uploader was not asked to
        # upload, exactly as in `publish`.
        with tempfile.TemporaryDirectory() as tmpdir:
            publisher = EvidencePublisher(
                directory=Path(tmpdir),
                identity=_identity(),
                video_converter=_StubConverter(),
            )
            collector = self._collector()
            collector.record_session("full-session", publisher, _save_a_cast)

            recording = collector.recordings[0]
            self.assertIsNone(recording.error)
            self.assertIsNotNone(recording.video)
            self.assertIsNone(recording.url)

    def test_two_recordings_with_one_label_do_not_share_a_cast(self) -> None:
        # Labels are caller-supplied and may repeat; the second recording must
        # not overwrite the first one's evidence.
        with tempfile.TemporaryDirectory() as tmpdir:
            publisher = EvidencePublisher(
                directory=Path(tmpdir),
                identity=_identity(),
                video_converter=_StubConverter(),
            )
            collector = self._collector()
            collector.record_session("full-session", publisher, _save_a_cast)
            collector.record_session("full-session", publisher, _save_a_cast)

            first, second = collector.recordings
            self.assertNotEqual(first.cast, second.cast)
            self.assertNotEqual(first.video, second.video)
            self.assertEqual("recording-01-full-session.cast", Path(second.cast).name)
            self.assertEqual([None, None], [first.error, second.error])

    def test_a_recorded_session_sits_beside_a_hand_attached_one(self) -> None:
        # `record_session` and `attach_recording` write to the same list, in
        # call order, so a caller that encodes its own video is not shut out.
        with tempfile.TemporaryDirectory() as tmpdir:
            publisher = EvidencePublisher(
                directory=Path(tmpdir),
                identity=_identity(),
                video_converter=_StubConverter(),
            )
            collector = self._collector()
            collector.attach_recording(Recording(label="hand-made", cast="/tmp/other.cast"))
            collector.record_session("full-session", publisher, _save_a_cast)

            manifest = collector.publish(publisher)
            document = json.loads(manifest.path.read_text())

        self.assertEqual(
            ["hand-made", "full-session"], [r["label"] for r in document["recordings"]]
        )


class AttachToTest(unittest.TestCase):
    """Joining a manifest to a result, which is what stops A being paired with B."""

    def _manifest(self, tmpdir: str, identity: RunIdentity) -> EvidenceManifest:
        collector = EvidenceCollector()
        collector.capture_text("one", "hello")
        return collector.publish(EvidencePublisher(directory=Path(tmpdir), identity=identity))

    def test_the_manifest_lands_in_the_results_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest = self._manifest(tmpdir, _identity())
            result = _run_result("login", "default")
            manifest.attach_to(result)

            self.assertEqual(str(manifest.path), result.artifacts["evidence_manifest"])

    def test_existing_artifacts_survive(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest = self._manifest(tmpdir, _identity())
            result = _run_result("login", "default")
            result.artifacts["cast"] = "/tmp/session.cast"
            manifest.attach_to(result)

            self.assertEqual("/tmp/session.cast", result.artifacts["cast"])

    def test_another_runs_evidence_is_refused(self) -> None:
        # The whole point: nothing about the file layout stops a caller pairing
        # run A's evidence with run B's result, so this is where it is noticed.
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest = self._manifest(tmpdir, _identity())
            result = _run_result("checkout", "default")

            with self.assertRaises(ValueError) as caught:
                manifest.attach_to(result)

            self.assertIn("login/default", str(caught.exception))
            self.assertIn("checkout/default", str(caught.exception))
            self.assertNotIn("evidence_manifest", result.artifacts)

    def test_a_different_renderer_is_refused_too(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest = self._manifest(tmpdir, _identity())
            result = _run_result("login", "ink")

            with self.assertRaises(ValueError):
                manifest.attach_to(result)

    def test_artifacts_does_not_check(self) -> None:
        # Documented as the unchecked seam for callers whose index is not a
        # RunResult; `attach_to` is the one that refuses.
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest = self._manifest(tmpdir, _identity())
            self.assertEqual({"evidence_manifest": str(manifest.path)}, manifest.artifacts())


class _NeverReuses:
    """A deduper that says every screen needs rendering.

    Substituted for the real one so that a caller keeping its own fingerprint
    comparison on the side would still dedupe, and be caught doing it.
    """

    def __init__(self) -> None:
        self.checked: list[str] = []

    def check(self, label: str, screen: AttributedScreen) -> str | None:
        self.checked.append(label)
        return None

    def forget(self) -> None:
        pass


class _AlwaysReuses:
    """A deduper that says every screen matches, naming an image nothing wrote.

    Nothing in the package could reach this verdict on its own — the screens it
    is asked about differ — so a caller that reports it is taking the deduper's
    word rather than deciding for itself.
    """

    SENTINEL = "sentinel.svg"

    def __init__(self) -> None:
        self.checked: list[str] = []

    def check(self, label: str, screen: AttributedScreen) -> str | None:
        self.checked.append(label)
        return self.SENTINEL

    def forget(self) -> None:
        raise AssertionError("nothing was asked to render, so nothing can have failed")


class SharedDedupTest(unittest.TestCase):
    """Both publishing paths take their dedup verdict from :mod:`termproof.dedup`.

    The rule used to be written out twice — once in ``EvidenceCollector.publish``
    and once in ``evidence._render_step_screens`` — which is how the two could
    disagree about what counts as a changed screen. These pin the delegation
    itself, not just its current answers, so re-inlining either copy fails here
    even if the re-inlined copy happens to be correct today.
    """

    DISTINCT_STEPS = [
        StepResult("one", True, "", "screen one"),
        StepResult("two", True, "", "screen two"),
    ]

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)

    def test_neither_module_has_a_deduper_of_its_own(self) -> None:
        self.assertIs(Deduper, collector_module.Deduper)
        self.assertIs(Deduper, evidence_module.Deduper)

    def test_the_collector_dedupes_only_when_the_deduper_says_so(self) -> None:
        stub = _NeverReuses()
        renderer = _RecordingRenderer()
        with tempfile.TemporaryDirectory() as tmpdir:
            collector = EvidenceCollector()
            collector.capture_text("before", "same")
            collector.capture_text("after", "same")
            with mock.patch.object(collector_module, "Deduper", lambda: stub):
                manifest = collector.publish(
                    EvidencePublisher(
                        directory=Path(tmpdir), identity=_identity(), renderer=renderer
                    )
                )

        # Two byte-identical screens: the real deduper collapses them, and this
        # one does not. Both images exist and neither step claims to reuse.
        self.assertEqual(["before", "after"], stub.checked)
        self.assertEqual(2, len(renderer.rendered))
        self.assertEqual([], manifest.deduped())

    def test_a_failed_render_forgets_through_the_deduper(self) -> None:
        # `Deduper.forget` is how the collector says "the image you were told to
        # make does not exist". Asserted here as a call, because the observable
        # consequence is already covered above and would survive an inlined copy.
        forgotten: list[bool] = []

        class _Recording(Deduper):
            def forget(self) -> None:
                forgotten.append(True)
                super().forget()

        with tempfile.TemporaryDirectory() as tmpdir:
            collector = EvidenceCollector()
            collector.capture_text("one", "same")
            collector.capture_text("two", "same")
            with mock.patch.object(collector_module, "Deduper", _Recording):
                manifest = collector.publish(
                    EvidencePublisher(
                        directory=Path(tmpdir),
                        identity=_identity(),
                        renderer=_FailingRenderer(),
                    )
                )

        self.assertEqual([True, True], forgotten)
        self.assertIsNone(manifest.steps[1].same_as)

    def test_render_artifacts_reports_the_deduper_verdict(self) -> None:
        stub = _AlwaysReuses()
        renderer = _RecordingRenderer()
        run_dir = Path(self._tmp.name)
        with mock.patch.object(evidence_module, "Deduper", lambda: stub):
            evidence_module._render_step_screens(
                run_dir,
                self.DISTINCT_STEPS,
                80,
                24,
                renderer,
                "svg",
                EvidenceConfig(dedup_step_screenshots=True),
            )

        manifest = json.loads(
            (run_dir / "steps" / evidence_module.STEPS_MANIFEST_NAME).read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(["01-one.svg", "02-two.svg"], stub.checked)
        # The screens differ, so a module deciding for itself would render both.
        self.assertEqual([], renderer.rendered)
        self.assertEqual(
            [_AlwaysReuses.SENTINEL] * 2, [entry["screenshot"] for entry in manifest]
        )
        self.assertEqual([True, True], [entry["unchanged_from_previous"] for entry in manifest])

    def test_dedup_off_never_asks_the_deduper(self) -> None:
        # `dedup_step_screenshots` is off by default and must stay a hard skip:
        # a deduper consulted-then-ignored is a state machine advancing on a
        # path where nothing reads it.
        stub = _AlwaysReuses()
        renderer = _RecordingRenderer()
        run_dir = Path(self._tmp.name)
        with mock.patch.object(evidence_module, "Deduper", lambda: stub):
            evidence_module._render_step_screens(
                run_dir, self.DISTINCT_STEPS, 80, 24, renderer, "svg", EvidenceConfig()
            )

        self.assertEqual([], stub.checked)
        self.assertEqual(2, len(renderer.rendered))


class CrossImplementationShapeTest(unittest.TestCase):
    """Local checks on the shape shared with the Rust implementation.

    The manifest key set used to be asserted here by spelling the Rust field
    names out, derived by reading the Rust structs rather than by running them.
    That could only ever catch a rename on the Python side. It now lives in
    ``conformance/probe_evidence_manifest.py`` and
    ``rust/crates/termproof/tests/differential_evidence_manifest.rs``, which
    build the same scenario on both sides and compare the published manifest
    *and* every file it points at — see ``conformance/README.md``.

    What is left here is the filename scheme, which is cheap to check locally
    and is the input to the comparison rather than its output.
    """

    def test_the_file_stem_matches_the_rust_scheme(self) -> None:
        collector = EvidenceCollector()
        collector.capture_text("a label/with slashes", "x")
        self.assertEqual("step-00-a-label-with-slashes", collector.steps[0].file_stem())

    def test_a_long_label_is_truncated_the_same_way(self) -> None:
        collector = EvidenceCollector()
        collector.capture_text("x" * 60, "screen")
        self.assertEqual(f"step-00-{'x' * 40}", collector.steps[0].file_stem())


if __name__ == "__main__":
    unittest.main()
