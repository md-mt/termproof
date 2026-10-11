#!/usr/bin/env python3
"""Oracle half of the build-info differential harness.

Records what the Python :meth:`termproof.build_info.BuildInfo.to_dict` emits
for a fixed scenario — the serialised provenance record for the binary under
test. The Rust half transcribes the same scenario and compares the documents.

The scenario is code, not a corpus of cases, as with the run result: records
are constructed directly with fixed values, never through ``from_command`` /
``from_binary`` / ``from_source_build``, which probe ``--version``, ask git
for a commit and read the clock. Six records cover the shapes one cannot:
each mode either implementation names (``installed``, ``source``, and the
Rust-only ``package``), empty-string fields where a revision belongs, and no
binary at all. ``to_dict`` stats the binary path (via ``verify_provenance``),
so the records point at a real temporary file, recorded as ``@BIN``.

This half records the Python document as it is. The known divergences —
renamed fields, the Python-only ``command`` and ``provenance_verified``
keys, ``null`` where Rust spells an absent binary ``""``, empty strings
counting as present on the Rust side, and ``package`` verifying there
(#209) — are **not** recorded here: they are named allowances in the Rust
test, so the checked-in expectation stays the oracle's testimony and each
allowance has to be edited deliberately, in code, if either side changes.

Regenerate deliberately::

    cd /path/to/termproof/python
    TERMPROOF_PYTHON_REPO=$PWD uv run python \\
        ../conformance/probe_build_info.py \\
        > ../conformance/corpus/build_info.expected.json
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.environ.get("TERMPROOF_PYTHON_REPO", str(Path(__file__).parent.parent / "python")))

from termproof.build_info import BuildInfo  # noqa: E402

TIMESTAMP = "2026-01-02T03:04:05"


def scenario(binary: str) -> list[BuildInfo]:
    """The fixed scenario. Keep in step with differential_build_info.rs."""
    return [
        # 0: installed, real binary — verified on both sides.
        BuildInfo(
            mode="installed",
            command=[binary, "--serve"],
            binary_path=binary,
            version="tool 1.2.3",
            git_commit="abc123",
            timestamp=TIMESTAMP,
        ),
        # 1: source with target and both revision spellings — verified.
        BuildInfo(
            mode="source",
            command=[binary],
            binary_path=binary,
            version="tool 1.2.3",
            git_commit="abc123",
            timestamp=TIMESTAMP,
            build_target="//app:cli",
            source_ref="PR-42",
        ),
        # 2: source whose revision fields are empty strings, not None.
        BuildInfo(
            mode="source",
            command=[binary],
            binary_path=binary,
            version="tool 1.2.3",
            git_commit="",
            timestamp=TIMESTAMP,
            build_target="//app:cli",
            source_ref="",
        ),
        # 3: source whose build target is an empty string, not None.
        BuildInfo(
            mode="source",
            command=[binary],
            binary_path=binary,
            version="tool 1.2.3",
            git_commit=None,
            timestamp=TIMESTAMP,
            build_target="",
            source_ref="PR-42",
        ),
        # 4: the Rust-only "package" mode.
        BuildInfo(
            mode="package",
            command=[binary],
            binary_path=binary,
            version="tool 1.2.3",
            git_commit=None,
            timestamp=TIMESTAMP,
        ),
        # 5: no binary at all — binary_path is None, command empty.
        BuildInfo(
            mode="installed",
            command=[],
            binary_path=None,
            version="unknown",
            git_commit=None,
            timestamp=TIMESTAMP,
        ),
    ]


def main() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        binary = Path(tmp) / "built"
        binary.write_text("x", encoding="utf-8")
        documents = [info.to_dict() for info in scenario(str(binary))]
        for document in documents:
            if document["binary_path"] == str(binary):
                document["binary_path"] = "@BIN"
            document["command"] = [
                "@BIN" if part == str(binary) else part for part in document["command"]
            ]
    json.dump(documents, sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
