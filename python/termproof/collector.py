"""An ordered, labelled record of what the screen looked like during a run.

The Rust implementation has had this since it was consolidated into this
repository; the Python side had only the module-level helpers in
:mod:`termproof.evidence`, which render whatever a completed
:class:`~termproof.models.RunResult` happens to carry. That is enough for a
declarative recipe, where the runner knows every step in advance. It is not
enough for a caller driving a session imperatively — branching on what the
screen shows — because such a caller decides *while running* which moments are
worth keeping, and had nowhere to put them.

The shape mirrors ``termproof::evidence::collector`` deliberately, down to the
field names in the manifest, so that the two implementations produce documents
a single reader can consume. ``conformance/probe_evidence_manifest.py`` and
``differential_evidence_manifest.rs`` compare the two whole, manifest and
written files both; see ``spec/`` for what is guaranteed to match.

Needs a renderer for images. Text is written regardless of whether one is
available, because the text is what an assertion was evaluated against and a
picture cannot answer that question.

.. _collector-versus-evidence:

Which of this and :mod:`termproof.evidence` to use
--------------------------------------------------

Who owns what:

* :class:`EvidenceCollector` owns capture — deciding *while a run is going on*
  which moments are worth keeping — and publishing what it captured.
* :func:`termproof.evidence.render_artifacts` owns rendering the artifacts a
  finished :class:`RunResult` already carries, whose step list the recipe fixed
  before the run started.
* :class:`termproof.dedup.Deduper` owns the "has this screen changed?" rule, for
  both of them. Neither implements it; there is one copy in the package.

They still write different documents, and that is why one is not a thin wrapper
over the other:

===============  =================================  ===============================
                 :mod:`termproof.evidence`          this module
===============  =================================  ===============================
Driven by        a finished :class:`RunResult`      a caller, while it runs
Step list        the recipe's, fixed in advance     whatever the caller captured
Writes           ``final.*``, ``steps/``,           ``step-NN-label.*`` and
                 ``steps-manifest.json``, video     ``evidence.json``
Dedup verdict    :class:`~termproof.dedup.Deduper`  :class:`~termproof.dedup.Deduper`
Dedup records    ``unchanged_from_previous``        ``same_as: {index, label}``
Dedup is         off unless configured              always on
A render failure fails the run                      is recorded on the step
Rust counterpart ``evidence::report``               ``evidence::collector``
===============  =================================  ===============================

Use :mod:`termproof.evidence` for a declarative recipe run by
:class:`~termproof.runner.TermProofRunner` — that is what it is wired into. Use
this module when the caller decides what to capture as it goes, which a
declarative recipe cannot express.

Folding one of the two *file layouts* into the other is a different change from
sharing the dedup, and not one to smuggle in here: it would move the paths
:func:`termproof.evidence.render_artifacts` has always written, which every
existing reader of a run directory depends on.

A whole-session recording is five steps, and four of them can fail
-------------------------------------------------------------------

:meth:`EvidenceCollector.record_session` is the wiring between the pieces
around it: it saves the live session's cast through a caller-supplied callable,
appends the captured checkpoints to it with
:func:`termproof.cast_video.append_checkpoint_frames`, converts it to a video,
uploads the video, and records the outcome on a :class:`Recording`. Every
consumer that wanted a video of the whole run wrote that sequence itself, and
what they got wrong was never the happy path — it was which step is allowed to
fail, and what the run is told when one does. See
:meth:`EvidenceCollector.record_session` for the rule.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Protocol

from .attributed import DEFAULT_COLUMNS, DEFAULT_ROWS, AttributedScreen, attributed_screen_from_lines
from .dedup import Deduper
from .models import RunResult

#: Schema version of the published manifest. Shared with the Rust
#: implementation; move the two together or not at all.
EVIDENCE_MANIFEST_VERSION = 1

#: Manifest filename written into the publish directory.
MANIFEST_FILE = "evidence.json"

#: Longest label fragment allowed in a generated filename.
MAX_LABEL_IN_FILENAME = 40

# Names of the four fallible steps of `EvidenceCollector.record_session`, as
# they appear at the front of a `Recording.error`.
#
# Spelled once each, and asserted literally in the tests, because "which step
# failed" is the whole point of the field: a report that says only that
# something went wrong sends a reader back to the machine that produced it. The
# Rust implementation writes the same four strings.
_STEP_SAVE_CAST = "save cast"
_STEP_APPEND_FRAMES = "append checkpoint frames"
_STEP_CONVERT = "convert"
_STEP_UPLOAD = "upload"

# Step 3's failure when the publisher was never given a converter.
_NO_VIDEO_CONVERTER = "no video converter configured"

# Step 4's failure when the uploader declined without saying why.
_NO_URL = "uploader returned no URL"


class RawOutput(Enum):
    """Whether a capture should carry the cumulative output log with it."""

    #: Include it — the caller is recording a failure.
    KEEP = "keep"
    #: Leave it out. The log is cumulative, so a copy per checkpoint is
    #: quadratic and every copy but the last is a prefix of a later one.
    SKIP = "skip"


class CaptureKind(Enum):
    """Why a step was captured."""

    CHECKPOINT = "checkpoint"
    FAILURE = "failure"

    def raw_output(self) -> RawOutput:
        return RawOutput.KEEP if self is CaptureKind.FAILURE else RawOutput.SKIP


@dataclass(frozen=True)
class ScreenCapture:
    """One self-consistent reading of a screen."""

    #: Screen text at the captured instant.
    screen: str
    #: The grid at the same instant, when the source has attributes to report.
    attributed: AttributedScreen | None = None
    #: The cumulative output log, when :attr:`RawOutput.KEEP` was asked for.
    raw_output: str | None = None


class ScreenSource(Protocol):
    """Something a collector can read a screen from.

    One method, not three, for the reason the Rust docstring gives at length:
    text, grid and raw log have to describe the same moment, and against a live
    program they will not if they are fetched separately. A pty session serves
    its text from the last sync point while its grid is read live; a tmux
    backend re-runs ``capture-pane`` as a side effect of being asked for the
    grid. Fetched one at a time the result is a manifest that validates and
    lies — ``step-NN.txt`` describing the screen before an action while
    ``step-NN.png`` describes the screen after it.
    """

    def capture_screen(self, raw: RawOutput) -> ScreenCapture: ...


@dataclass
class CapturedStep:
    """One captured screen, in capture order."""

    #: Position in capture order, zero-based. Filenames use the same number.
    index: int
    #: Caller-supplied label.
    label: str
    #: Why it was captured.
    kind: CaptureKind
    #: Screen text at capture time.
    screen: str
    #: The grid at capture time, synthesised from the text when the source had
    #: no attributed screen of its own.
    attributed: AttributedScreen
    #: Cumulative output log, kept for :attr:`CaptureKind.FAILURE` only.
    raw_output: str | None = None

    def file_stem(self) -> str:
        """Filename stem shared by this step's artifacts."""
        return f"step-{self.index:02d}-{_sanitize(self.label[:MAX_LABEL_IN_FILENAME])}"


@dataclass
class Recording:
    """A recording of a whole session, as against one screen out of it.

    ``error`` is one field rather than separate conversion and upload errors:
    they are mutually exclusive, since a conversion that failed leaves nothing
    to upload.
    """

    label: str
    cast: str
    video: str | None = None
    url: str | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "label": self.label,
            "cast": self.cast,
            "video": self.video,
            "url": self.url,
            "error": self.error,
        }


@dataclass(frozen=True)
class RunIdentity:
    """Which run a manifest belongs to.

    Evidence sits beside the result rather than inside it, so nothing about the
    file layout stops a caller pointing run A's result at run B's evidence.
    This is what lets a reader — and :meth:`EvidenceManifest.attach_to` —
    notice.
    """

    #: Recipe this evidence came from; matches :attr:`RunResult.recipe_name`.
    recipe_name: str
    #: Renderer this evidence came from; matches :attr:`RunResult.renderer`.
    renderer: str
    #: Identifier for this run in particular.
    #:
    #: Recipe and renderer separate two different runs; they do not separate two
    #: runs of the *same* recipe. :class:`~termproof.models.RunResult` has no
    #: field to check this against, so it is recorded rather than verified: a
    #: reader holding a run directory can compare it, and two manifests can be
    #: told apart.
    run_id: str

    def to_dict(self) -> dict[str, str]:
        return {
            "recipe_name": self.recipe_name,
            "renderer": self.renderer,
            "run_id": self.run_id,
        }

    def matches(self, result: RunResult) -> bool:
        """Whether ``result`` is the run this identity describes.

        Compares what the two documents share. See :attr:`run_id` for what this
        cannot rule out.
        """
        return self.recipe_name == result.recipe_name and self.renderer == result.renderer


class ScreenshotRendererLike(Protocol):
    """The renderer protocol, satisfied by :class:`termproof.rsvg.RsvgPngRenderer`."""

    extension: str

    def render_attributed(
        self, screen: AttributedScreen, output_path: Path, cols: int, rows: int
    ) -> None: ...


class UploaderLike(Protocol):
    """Optional upload seam. Returns ``None`` when the upload did not happen."""

    def upload(self, path: Path) -> str | None: ...


class VideoConverterLike(Protocol):
    """Turns a cast into a video and says where the video landed.

    Mirrors Rust's ``CastVideoConverter::convert``, and is satisfied by
    :class:`termproof.cast_video.RsvgFfmpegBackend`. Deliberately not the
    :class:`termproof.protocols.VideoBackend` shape: that one takes an ``fps``
    and returns nothing, so every caller would have to invent an output path
    and a frame rate before it could ask for a video.

    Raises on failure — the counterpart of Rust's ``Err``.
    """

    def convert(self, cast_path: Path, video_path: Path | None = None) -> Path: ...


@dataclass
class EvidencePublisher:
    """Where published evidence goes and how it gets there."""

    #: Directory the artifacts are written into.
    directory: Path
    #: Which run this evidence belongs to. Required rather than optional: a
    #: manifest that cannot say whose it is cannot be checked by anyone.
    identity: RunIdentity
    #: Renders a captured grid to an image. Without one, only text is written.
    renderer: ScreenshotRendererLike | None = None
    #: Uploads are best-effort: a failure leaves the step's ``url`` empty
    #: rather than failing the publish.
    uploader: UploaderLike | None = None
    #: Encodes a session recording, for
    #: :meth:`EvidenceCollector.record_session` and for nothing else —
    #: :meth:`EvidenceCollector.publish` renders stills and does not encode.
    #:
    #: Optional rather than defaulted because a converter is two more binaries
    #: on the host (``rsvg-convert`` and ``ffmpeg``), and a publisher that is
    #: only ever going to write stills should not imply them. A
    #: ``record_session`` against a publisher without one records that as the
    #: ``convert`` step failing.
    video_converter: VideoConverterLike | None = None

    def manifest_path(self) -> Path:
        return self.directory / MANIFEST_FILE


@dataclass
class ReusedFrom:
    """The step whose screenshot another step reuses.

    Both halves, because either alone is not enough: labels are caller-supplied
    and may repeat, so ``"check"`` does not say *which* ``check``; the index
    alone says which but makes the manifest unreadable without
    cross-referencing.
    """

    index: int
    label: str

    def to_dict(self) -> dict[str, object]:
        return {"index": self.index, "label": self.label}


@dataclass
class PublishedStep:
    """One step as it came out of :meth:`EvidenceCollector.publish`."""

    index: int
    label: str
    kind: CaptureKind
    screen_text: str
    raw_output: str | None = None
    screenshot: str | None = None
    url: str | None = None
    same_as: ReusedFrom | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "index": self.index,
            "label": self.label,
            "kind": self.kind.value,
            "screen_text": self.screen_text,
            "raw_output": self.raw_output,
            "screenshot": self.screenshot,
            "url": self.url,
            "same_as": self.same_as.to_dict() if self.same_as else None,
            "error": self.error,
        }


@dataclass
class EvidenceManifest:
    """What a publish produced."""

    manifest_version: int
    run: RunIdentity
    steps: list[PublishedStep]
    recordings: list[Recording] = field(default_factory=list)
    path: Path = Path()

    def to_dict(self) -> dict[str, object]:
        document: dict[str, object] = {
            "manifest_version": self.manifest_version,
            "run": self.run.to_dict(),
            "steps": [s.to_dict() for s in self.steps],
        }
        # Omitted entirely when empty, so a run that records nothing writes the
        # document it wrote before the field existed. That is what lets it be
        # additive without moving EVIDENCE_MANIFEST_VERSION, and it is the same
        # rule the Rust implementation follows.
        if self.recordings:
            document["recordings"] = [r.to_dict() for r in self.recordings]
        return document

    def to_json_pretty(self) -> str:
        return json.dumps(self.to_dict(), indent=2) + "\n"

    def attach_to(self, result: RunResult) -> None:
        """Point ``result`` at this manifest, refusing another run's.

        Evidence sits beside the result rather than inside it, so nothing about
        the file layout stops a caller pairing run A's evidence with run B's
        result. This is the seam that notices — the same contract as the Rust
        ``EvidenceManifest::attach_to``, which returns an error where this
        raises.

        :raises ValueError: if the manifest belongs to a different run.
        """
        if not self.run.matches(result):
            raise ValueError(
                f"evidence for {self.run.recipe_name}/{self.run.renderer} cannot be "
                f"attached to a result for {result.recipe_name}/{result.renderer}"
            )
        result.artifacts.update(self.artifacts())

    def artifacts(self) -> dict[str, str]:
        """One entry pointing at this manifest, not one per step.

        Prefer :meth:`attach_to`, which will not pair a manifest with a result
        from another run. This is for callers building an index that is not a
        :class:`~termproof.models.RunResult`.

        One entry, not one per step: the manifest is the index, and a caller
        that wants the per-step paths reads it rather than having them
        duplicated into a flat map that has no way to express order.
        """
        return {"evidence_manifest": str(self.path)}

    def deduped(self) -> list[PublishedStep]:
        """Steps whose screen matched the one before, so no image of their own."""
        return [s for s in self.steps if s.same_as is not None]


class EvidenceCollector:
    """Collects labelled screen snapshots during a run."""

    def __init__(self, columns: int = DEFAULT_COLUMNS, rows: int = DEFAULT_ROWS) -> None:
        self._steps: list[CapturedStep] = []
        self._recordings: list[Recording] = []
        # Only consulted for sources that report no attributed screen; a grid
        # that exists carries its own dimensions.
        self._columns = columns
        self._rows = rows

    def capture(self, label: str, source: ScreenSource) -> None:
        """Capture the screen as an ordinary checkpoint."""
        self._record(label, CaptureKind.CHECKPOINT, source)

    def capture_failure(self, label: str, source: ScreenSource) -> None:
        """Capture the screen as a failure, keeping the output log with it."""
        self._record(label, CaptureKind.FAILURE, source)

    def capture_text(
        self, label: str, screen: str, kind: CaptureKind = CaptureKind.CHECKPOINT
    ) -> None:
        """Record a screen the caller already holds, with no source to read from.

        No raw output log is attached, even for a failure: there is nothing to
        ask for one.
        """
        self._steps.append(
            CapturedStep(
                index=len(self._steps),
                label=label,
                kind=kind,
                screen=screen,
                attributed=self._grid_from_text(screen),
            )
        )

    def _record(self, label: str, kind: CaptureKind, source: ScreenSource) -> None:
        capture = source.capture_screen(kind.raw_output())
        self._steps.append(
            CapturedStep(
                index=len(self._steps),
                label=label,
                kind=kind,
                screen=capture.screen,
                attributed=capture.attributed or self._grid_from_text(capture.screen),
                raw_output=capture.raw_output,
            )
        )

    def _grid_from_text(self, screen: str) -> AttributedScreen:
        return attributed_screen_from_lines(
            screen.splitlines(), columns=self._columns, rows=self._rows
        )

    def attach_recording(self, recording: Recording) -> None:
        """Attach a whole-session recording.

        The collector does not produce recordings — encoding a cast is a
        tool-shelling job with its own failure modes, and which tool is the
        caller's business. It carries them so that :meth:`publish` can put the
        stills and the video in one manifest.
        """
        self._recordings.append(recording)

    def record_session(
        self,
        label: str,
        publisher: EvidencePublisher,
        save_cast: Callable[[Path], None],
    ) -> None:
        """Save the session's cast, derive a video from it, upload it, and
        record the outcome.

        The five steps, in order:

        1. write the live session's cast, by calling *save_cast* with the path
           to write to — the collector picks the path so the cast lands beside
           the stills it belongs with;
        2. append the captured checkpoints to that cast as held trailing
           frames, through
           :func:`termproof.cast_video.append_checkpoint_frames`;
        3. convert the cast to a video, through the publisher's
           :attr:`~EvidencePublisher.video_converter`;
        4. upload the video, through the publisher's
           :attr:`~EvidencePublisher.uploader`;
        5. attach a :class:`Recording` describing what came of all that, which
           :meth:`publish` then writes into the manifest.

        **No failure fails the run.** Nothing here raises, on purpose: a
        recording is evidence *about* a run, not part of its verdict, so a
        missing video degrades the report and nothing else. Every failure lands
        on the ``Recording`` instead, prefixed with the name of the step that
        produced it — ``save cast``, ``append checkpoint frames``, ``convert``
        or ``upload`` — and reaches the report from there. Two failures in one
        call are joined with ``"; "``, so neither is lost to the other. Step 5
        is the only one that cannot fail: it appends to a list.

        **Which later steps run after a failure.** A step runs only when the
        step before it produced the thing it works on. That is the whole rule,
        and it decides every case:

        ==================  =================  ==========================================
        step that failed    what still runs    why
        ==================  =================  ==========================================
        1, save cast        nothing            no cast to append to, convert or upload
        2, append frames    3 and 4            the cast is still on disk and still
                                               convertible; it just ends on the session
                                               instead of on the evidence
        3, convert          nothing after it   there is no video to upload
        4, upload           —                  it is last; ``video`` is still recorded,
                                               only ``url`` is missing
        ==================  =================  ==========================================

        The case worth naming is the one a hand-written version gets wrong: **an
        upload is never attempted after a failed conversion.** Uploading the
        path a conversion did not produce is how a run ends up reporting a store
        error for a video that was never encoded.

        A publisher with no uploader is not a failure — it is a publisher that
        was not asked to upload, exactly as in :meth:`publish`. A publisher with
        no *converter* is a failure, because converting is what this method was
        called to do.

        *save_cast* writes a cast to the path it is handed, and raises to say it
        could not; the exception's text becomes the step-1 message, where Rust
        takes an ``Err(String)``. A callable that returns normally and writes
        nothing is treated as step 1 failing, rather than left for step 2 to
        discover as a missing file: the step that lied is the one worth naming.
        """
        # Imported here, not at module scope: `cast_video` imports
        # `CapturedStep` from this module, so a top-level import would close
        # the cycle. Nothing else in the collector needs the video path.
        from .cast_video import append_checkpoint_frames

        stem = _recording_file_stem(len(self._recordings), label)
        cast_path = publisher.directory / f"{stem}.cast"
        recording = Recording(label=label, cast=str(cast_path))
        errors: list[str] = []

        # 1. Write the cast. The directory is created here rather than left to
        #    the callable: the collector chose the path, so the collector owes
        #    it somewhere to be written.
        try:
            publisher.directory.mkdir(parents=True, exist_ok=True)
            save_cast(cast_path)
        except Exception as exc:  # noqa: BLE001 - no failure may fail the run
            recording.error = f"{_STEP_SAVE_CAST}: {exc}"
            self._recordings.append(recording)
            return
        if not cast_path.is_file():
            recording.error = (
                f"{_STEP_SAVE_CAST}: reported success but wrote no file at {cast_path}"
            )
            self._recordings.append(recording)
            return

        # 2. Put the evidence sequence on the end of it. Non-fatal: the cast is
        #    on disk either way, and a recording that stops on the session is
        #    worth more than no recording at all.
        try:
            append_checkpoint_frames(cast_path, self._steps)
        except Exception as exc:  # noqa: BLE001 - no failure may fail the run
            errors.append(f"{_STEP_APPEND_FRAMES}: {exc}")

        # 3. Encode it.
        video_path = publisher.directory / f"{stem}.mp4"
        if publisher.video_converter is None:
            errors.append(f"{_STEP_CONVERT}: {_NO_VIDEO_CONVERTER}")
        else:
            try:
                video = Path(publisher.video_converter.convert(cast_path, video_path))
            except Exception as exc:  # noqa: BLE001 - no failure may fail the run
                errors.append(f"{_STEP_CONVERT}: {exc}")
            else:
                recording.video = str(video)
                # 4. Share it. Only reachable with a video in hand.
                if publisher.uploader is not None:
                    try:
                        url = publisher.uploader.upload(video)
                    except Exception as exc:  # noqa: BLE001 - no failure may fail the run
                        errors.append(f"{_STEP_UPLOAD}: {exc}")
                    else:
                        if url is None:
                            errors.append(f"{_STEP_UPLOAD}: {_NO_URL}")
                        else:
                            recording.url = url

        # 5. Record what happened, including which step it happened in.
        if errors:
            recording.error = "; ".join(errors)
        self._recordings.append(recording)

    @property
    def steps(self) -> list[CapturedStep]:
        return list(self._steps)

    @property
    def recordings(self) -> list[Recording]:
        return list(self._recordings)

    def __len__(self) -> int:
        return len(self._steps)

    def publish(self, publisher: EvidencePublisher) -> EvidenceManifest:
        """Write text, render, dedupe, upload, and write the manifest.

        Raises only when the *manifest itself* cannot be written. A screenshot
        that fails to render is recorded on the step as an ``error`` and does
        not fail the run: the text is already on disk, which is the part an
        assertion is diagnosed from.
        """
        publisher.directory.mkdir(parents=True, exist_ok=True)
        extension = getattr(publisher.renderer, "extension", "png")
        published: list[PublishedStep] = []
        deduper = Deduper()
        # The image the deduper's answer refers to. `Deduper.check` reports a
        # label, and labels are caller-supplied and may repeat; tracking the
        # step alongside is exact, because the deduper only ever looks back one
        # rendered step and this is it.
        last_rendered: tuple[ReusedFrom, str, str | None] | None = None

        for step in self._steps:
            stem = step.file_stem()
            text_path = publisher.directory / f"{stem}.txt"
            # Verbatim, with no trailing newline added. The screen is what an
            # assertion was evaluated against, and the Rust implementation
            # writes it unaltered; a newline on one side and not the other
            # makes the two documents' artifacts differ while their manifests
            # agree. `conformance/probe_evidence_manifest.py` pins this.
            text_path.write_text(step.screen, encoding="utf-8")

            raw_output_path: str | None = None
            if step.raw_output is not None:
                raw_path = publisher.directory / f"{stem}-raw.txt"
                raw_path.write_text(step.raw_output, encoding="utf-8")
                raw_output_path = str(raw_path)

            entry = PublishedStep(
                index=step.index,
                label=step.label,
                kind=step.kind,
                screen_text=str(text_path),
                raw_output=raw_output_path,
            )

            # The deduper fingerprints the grid the image is rendered from, not
            # the text, so that a colour-only change counts as a change.
            if deduper.check(step.label, step.attributed) is not None:
                # Nothing to point at when there is no renderer: no image was
                # ever made, so the step keeps its text and no screenshot.
                if last_rendered is not None:
                    source, image, url = last_rendered
                    entry.same_as = source
                    entry.screenshot = image
                    entry.url = url
            elif publisher.renderer is not None:
                image_path = publisher.directory / f"{stem}.{extension}"
                try:
                    publisher.renderer.render_attributed(
                        step.attributed,
                        image_path,
                        step.attributed.column_count,
                        len(step.attributed.rows),
                    )
                except Exception as exc:  # noqa: BLE001 - best effort by contract
                    entry.error = str(exc)
                    # `Deduper.forget`'s contract. Without it the next identical
                    # screen is told to reuse an image that was never produced.
                    deduper.forget()
                    last_rendered = None
                else:
                    url = _upload(publisher, image_path)
                    entry.screenshot = str(image_path)
                    entry.url = url
                    last_rendered = (
                        ReusedFrom(index=step.index, label=step.label),
                        str(image_path),
                        url,
                    )
            published.append(entry)

        manifest = EvidenceManifest(
            manifest_version=EVIDENCE_MANIFEST_VERSION,
            run=publisher.identity,
            steps=published,
            recordings=list(self._recordings),
            path=publisher.manifest_path(),
        )
        manifest.path.write_text(manifest.to_json_pretty(), encoding="utf-8")
        return manifest


def _upload(publisher: EvidencePublisher, path: Path) -> str | None:
    if publisher.uploader is None:
        return None
    try:
        return publisher.uploader.upload(path)
    except Exception:  # noqa: BLE001 - uploads are best effort by contract
        return None


def _sanitize(value: str) -> str:
    return "".join(c if c.isalnum() or c in "-_" else "-" for c in value)


def _recording_file_stem(index: int, label: str) -> str:
    """Filename stem shared by a recording's cast and video.

    Numbered like :meth:`CapturedStep.file_stem` and for the same reason: labels
    are caller-supplied and may repeat, and two recordings called
    ``full-session`` must not overwrite each other's cast.
    """
    return f"recording-{index:02d}-{_sanitize(label[:MAX_LABEL_IN_FILENAME])}"


#: A source built from a screen the caller already has. Useful in tests and for
#: replaying a cast, neither of which has a live program to read from.
def static_source(screen: str, raw_output: str = "") -> ScreenSource:
    class _Static:
        def capture_screen(self, raw: RawOutput) -> ScreenCapture:
            return ScreenCapture(
                screen=screen,
                attributed=None,
                raw_output=raw_output if raw is RawOutput.KEEP else None,
            )

    return _Static()


__all__ = [
    "EVIDENCE_MANIFEST_VERSION",
    "MANIFEST_FILE",
    "CaptureKind",
    "CapturedStep",
    "EvidenceCollector",
    "EvidenceManifest",
    "EvidencePublisher",
    "PublishedStep",
    "RawOutput",
    "Recording",
    "ReusedFrom",
    "RunIdentity",
    "ScreenCapture",
    "ScreenSource",
    "VideoConverterLike",
    "static_source",
]
