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
from termproof.models import RunResult


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
