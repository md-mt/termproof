#!/usr/bin/env python3
"""Oracle half of the evidence-manifest differential harness.

Drives the Python :class:`termproof.collector.EvidenceCollector` over the
scenario below and writes to stdout both halves of what a publish produces:
the ``evidence.json`` document, and the contents of every file it wrote. The
publish directory is substituted out so the result is comparable across
machines.

Both halves, because the manifest is a set of paths and agreeing on the paths
is not agreeing on the files. The first run of this harness found the two
implementations writing byte-identical manifests pointing at step text files
that differed by a trailing newline.

The same reasoning covers the cast this writes into the publish directory: a
manifest agreeing about a recording's path is not agreeing about the recording,
and once ``append_checkpoint_frames`` puts the evidence sequence on the end of
one, the cast is the artifact a reviewer actually watches.

The scenario is not a corpus file, unlike the step and assertion harnesses.
There is only one document shape to compare and it is built by calling an API
rather than by replaying data, so the cases are the code below and the Rust
half transcribes them. Keep the two in step: ``differential_evidence_manifest``
compares byte-for-byte and will say so if they drift.

Regenerate deliberately::

    cd /path/to/termproof/python
    TERMPROOF_PYTHON_REPO=$PWD uv run python \\
        ../conformance/probe_evidence_manifest.py \\
        > ../conformance/corpus/evidence_manifest.expected.json
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.environ.get("TERMPROOF_PYTHON_REPO", str(Path(__file__).parent.parent / "python")))

from termproof.attributed import AttributedScreen  # noqa: E402
from termproof.cast_video import append_checkpoint_frames  # noqa: E402
from termproof.collector import (  # noqa: E402
    MANIFEST_FILE,
    CaptureKind,
    EvidenceCollector,
    EvidencePublisher,
    Recording,
    RunIdentity,
    static_source,
)

#: Stands in for the publish directory, which differs on every machine and
#: between the two halves.
DIRECTORY_PLACEHOLDER = "@DIR"

#: A recorded session for the checkpoint frames to be appended to. Written out
#: by hand rather than by a recorder: a real header carries a wall-clock
#: timestamp and the host's ``SHELL`` and ``TERM``, none of which either
#: implementation controls.
#:
#: It opens by setting a scroll region, because that is what a full-screen TUI
#: leaves behind and it is the state an append has to undo: without the
#: ``\x1b[r`` in the repaint prefix, a checkpoint taller than the region scrolls
#: rows out of the frame. The corpus records the prefix bytes, so both
#: implementations are held to resetting it.
BASE_CAST = (
    '{"version":2,"width":80,"height":24}\n'
    '[0.5,"o","\\u001b[3;20rMENU"]\n'
    '[1.25,"o","\\r\\nitem one"]\n'
)

#: Filename for that cast inside the publish directory.
CHECKPOINT_CAST = "session-with-checkpoints.cast"

#: A second append over the same steps at an explicit, fractional hold, which
#: the default-hold cast cannot cover.
#:
#: Its base ends on a seventh decimal on purpose. That is what a Rust-recorded
#: cast ends on -- ``CastRecorder`` writes ``as_secs_f64()`` unrounded -- and it
#: is the only input shape that tells the two languages' rounding apart:
#: ``round(at, 6)`` writes 0.9 and 1.3 for the second and fourth frames where
#: the rule both sides actually run writes 0.900001 and 1.300001. Over a
#: whole-decimal base the two agree everywhere, so a corpus built on one would
#: regenerate byte-for-byte with the Python transcription reverted.
FRACTIONAL_HOLD = 0.2
FRACTIONAL_HOLD_CAST = "session-with-fractional-hold.cast"
FRACTIONAL_BASE_CAST = '{"version":2,"width":80,"height":24}\n[0.5000005,"o","MENU"]\n'

IDENTITY = RunIdentity(
    recipe_name="login",
    renderer="default",
    run_id="20240101-000000-000000-login-default-1",
)


class _StubRenderer:
    """A renderer that writes a fixed byte and reports success.

    The real rasteriser shells out to ``rsvg-convert``, whose presence and
    version are properties of the machine rather than of either implementation.
    Both halves stub it identically so the manifest records a rendered
    screenshot on every host.
    """

    extension = "png"

    def render_attributed(
        self, screen: AttributedScreen, output_path: Path, cols: int, rows: int
    ) -> None:
        output_path.write_bytes(b"png")


class _StubUploader:
    """Returns a deterministic URL derived from the filename."""

    def upload(self, path: Path) -> str | None:
        return f"https://example.invalid/{path.name}"


def build(directory: Path) -> tuple[dict[str, object], dict[str, str]]:
    collector = EvidenceCollector()

    # A plain checkpoint read from a source.
    collector.capture("menu-open", static_source("MENU\nitem one"))
    # The same screen again: dedup, so `same_as` points back at step 0 and no
    # second image is written.
    collector.capture("menu-open-again", static_source("MENU\nitem one"))
    # A screen the caller already held, with no source to read it from.
    collector.capture_text("from-log", "RECOVERED", CaptureKind.CHECKPOINT)
    # A text capture marked as a failure still carries no raw output: there is
    # no source to ask for one.
    collector.capture_text("post-mortem", "LAST SCREEN", CaptureKind.FAILURE)
    # A failure read from a source does carry the log.
    collector.capture_failure("boom", static_source("ERROR", raw_output="log bytes"))
    # Two screens whose text differs only by SGR escapes. Both sides build the
    # grid for a text capture from plain lines rather than by parsing ANSI, so
    # whether these dedupe together is a statement about that choice — and one
    # the two implementations have to make the same way, since the dedup
    # verdict reaches the manifest.
    collector.capture_text("styled", "\x1b[31mALERT\x1b[0m", CaptureKind.CHECKPOINT)
    collector.capture_text("unstyled", "ALERT", CaptureKind.CHECKPOINT)

    collector.attach_recording(
        Recording(
            label="full-session",
            cast="/tmp/session.cast",
            video="/tmp/session.mp4",
            url="https://example.invalid/session.mp4",
        )
    )
    collector.attach_recording(
        Recording(
            label="failed-encode",
            cast="/tmp/broken.cast",
            error="video conversion failed",
        )
    )

    manifest = collector.publish(
        EvidencePublisher(
            directory=directory,
            identity=IDENTITY,
            renderer=_StubRenderer(),
            uploader=_StubUploader(),
        )
    )
    document = json.loads(manifest.path.read_text(encoding="utf-8"))

    # The evidence sequence written onto the end of a recording. Every captured
    # screen above goes in, including the SGR-escaped one and the two-line one,
    # so the appended payloads exercise both JSON escaping and the carriage
    # returns a raw terminal needs.
    cast = directory / CHECKPOINT_CAST
    cast.write_text(BASE_CAST, encoding="utf-8")
    append_checkpoint_frames(cast, collector.steps)

    fractional = directory / FRACTIONAL_HOLD_CAST
    fractional.write_text(FRACTIONAL_BASE_CAST, encoding="utf-8")
    append_checkpoint_frames(fractional, collector.steps, hold_seconds=FRACTIONAL_HOLD)

    # `evidence.json` is excluded: it is `document`, and recording it twice
    # would let the two copies disagree.
    files = {
        path.name: path.read_text(encoding="utf-8")
        for path in sorted(directory.iterdir())
        if path.is_file() and path.name != MANIFEST_FILE
    }
    return document, files


def normalize(document: object, directory: Path) -> object:
    """Replace the publish directory with :data:`DIRECTORY_PLACEHOLDER`."""
    prefix = str(directory)
    if isinstance(document, dict):
        return {k: normalize(v, directory) for k, v in document.items()}
    if isinstance(document, list):
        return [normalize(v, directory) for v in document]
    if isinstance(document, str):
        return document.replace(prefix, DIRECTORY_PLACEHOLDER)
    return document


def main() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        directory = Path(tmpdir) / "evidence"
        manifest, files = build(directory)
        recorded = normalize({"manifest": manifest, "files": files}, directory)
    json.dump(recorded, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
