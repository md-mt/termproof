#!/usr/bin/env python3
"""Byte-equality gate for every copy of the canonical recipe schema (#174).

The Python package resource is the reference. Every other copy is compared
against it, byte for byte, and each exists for a reason it cannot be talked out
of:

  python/termproof/_resources/recipe-schema-v1.json
      The reference. `recipe_schema.load_recipe_schema()` reads this and only
      this, so it is what the wheel and the sdist ship and what a build system
      assembling the package from sdist sources gets.

  rust/crates/termproof/resources/recipe-schema-v1.json
      The crate's copy, embedded with `include_str!`. A registry checkout has
      no repository above it, so a crate that looks outside itself for the
      schema does not have it.

  python/docs/recipe-schema-v1.json
      Compatibility only. This is the path the schema was published at, linked
      from `docs/recipe-format-v1.md`, and a URL someone may already have in a
      `$schema` line, a script or a bookmark. It is not in the wheel, so it is
      not in an installed package and no import path reaches it; the sdist does
      carry it, because the sdist ships `docs/` and a source distribution
      missing a checked-in source file would be the anomaly. Nothing loads it
      either way, so it costs a file here and nothing downstream.

One copy per self-contained artifact is the floor; a wheel cannot read a file
out of a crate. The docs copy is above that floor and is kept anyway, because
breaking a published URL is a separate decision from fixing packaging and this
change is not making it.

The check is on bytes, not on parsed JSON: the crate embeds the text with
`include_str!`, so whitespace and key order are part of what ships, and a
published URL should serve the same bytes it always did.

There is no `--fix`. Which copy is right is a decision, and silently rewriting
one of them would turn an edit made in the wrong place into a green build.
Change the schema everywhere, in the same commit.

Usage:
  python scripts/check_schema_copies.py

Exit codes: 0 all identical, 1 drift or a missing copy.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
REPO_ROOT = ROOT.parent

# The path `load_recipe_schema()` reads. Every other copy answers to it.
REFERENCE = ROOT / "termproof" / "_resources" / "recipe-schema-v1.json"
COPIES = (
    REPO_ROOT / "rust" / "crates" / "termproof" / "resources" / "recipe-schema-v1.json",
    ROOT / "docs" / "recipe-schema-v1.json",
)


def _rel(path: Path) -> str:
    return str(path.relative_to(REPO_ROOT))


def main() -> int:
    missing = [_rel(path) for path in (REFERENCE, *COPIES) if not path.is_file()]
    if missing:
        print(
            "canonical recipe schema is missing at: " + ", ".join(missing),
            file=sys.stderr,
        )
        print(
            "Hint: each copy exists for a reason — the package resource is what "
            "the artifacts ship, the crate copy is what a registry consumer can "
            "reach, and the docs copy is a published URL. None is optional; see "
            "the docstring in this script.",
            file=sys.stderr,
        )
        return 1

    reference = REFERENCE.read_bytes()
    drifted = [path for path in COPIES if path.read_bytes() != reference]
    if not drifted:
        print(
            f"canonical recipe schema identical across {1 + len(COPIES)} copies "
            f"({len(reference)} bytes)"
        )
        return 0

    for path in drifted:
        print(
            f"canonical recipe schema drift: {_rel(path)} ({len(path.read_bytes())} bytes) "
            f"differs from {_rel(REFERENCE)} ({len(reference)} bytes)",
            file=sys.stderr,
        )
    print(
        "Hint: these are one file. Apply the change to every copy, in the same "
        "commit, and re-run this check.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
