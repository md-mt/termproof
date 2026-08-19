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
a single reader can consume. See ``spec/`` for what is guaranteed to match.

Needs a renderer for images. Text is written regardless of whether one is
available, because the text is what an assertion was evaluated against and a
picture cannot answer that question.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Protocol

from .attributed import DEFAULT_COLUMNS, DEFAULT_ROWS, AttributedScreen, attributed_screen_from_lines

#: Schema version of the published manifest. Shared with the Rust
#: implementation; move the two together or not at all.
EVIDENCE_MANIFEST_VERSION = 1

#: Manifest filename written into the publish directory.
MANIFEST_FILE = "evidence.json"

#: Longest label fragment allowed in a generated filename.
MAX_LABEL_IN_FILENAME = 40


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

    recipe_name: str
    renderer: str
    run_id: str

    def to_dict(self) -> dict[str, str]:
        return {
            "recipe_name": self.recipe_name,
            "renderer": self.renderer,
            "run_id": self.run_id,
        }


class ScreenshotRendererLike(Protocol):
    """The renderer protocol, satisfied by :class:`termproof.rsvg.RsvgPngRenderer`."""

    extension: str

    def render_attributed(
        self, screen: AttributedScreen, output_path: Path, cols: int, rows: int
    ) -> None: ...


class UploaderLike(Protocol):
    """Optional upload seam. Returns ``None`` when the upload did not happen."""

    def upload(self, path: Path) -> str | None: ...


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

    def artifacts(self) -> dict[str, str]:
        """One entry pointing at this manifest, not one per step.

        The manifest is the index; a caller wanting per-step paths reads it,
        rather than having them duplicated into a flat map with no way to
        express order.
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
        # The image the dedup verdict refers to. Tracked as a step rather than
        # a label because labels are caller-supplied and may repeat.
        last_rendered: tuple[ReusedFrom, str, str | None] | None = None
        previous_fingerprint: str | None = None

        for step in self._steps:
            stem = step.file_stem()
            text_path = publisher.directory / f"{stem}.txt"
            text_path.write_text(step.screen + "\n", encoding="utf-8")

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

            # Fingerprint the grid the image is rendered from, not the text, so
            # that a colour-only change counts as a change.
            fingerprint = step.attributed.render_fingerprint()
            if fingerprint == previous_fingerprint and last_rendered is not None:
                source, image, url = last_rendered
                entry.same_as = source
                entry.screenshot = image
                entry.url = url
            elif publisher.renderer is None:
                previous_fingerprint = None
            else:
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
                    # Without this, the next identical screen is told to reuse
                    # an image that was never produced.
                    last_rendered = None
                    previous_fingerprint = None
                    published.append(entry)
                    continue
                url = _upload(publisher, image_path)
                entry.screenshot = str(image_path)
                entry.url = url
                last_rendered = (
                    ReusedFrom(index=step.index, label=step.label),
                    str(image_path),
                    url,
                )
            previous_fingerprint = fingerprint
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


ToolRunnerLike = Callable[[str, list[str], int], None]

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
    "static_source",
]
