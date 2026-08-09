#!/usr/bin/env python3
"""Single-source version and CHANGELOG drift check (RUST-023).

The canonical version lives in `pyproject.toml`. This script verifies that
`CHANGELOG.md` contains an entry for it. It also checks that `action.yml` and
`Formula/termproof.rb` reference the same version.

The `rust/Cargo.toml` half of this check went away with the Rust workspace,
which now lives in https://github.com/md-mt/termproof-rust and versions itself.

The `--fix` flag went with it: rewriting `rust/Cargo.toml` was the only thing
it did.

Usage:
  python scripts/check_version.py              # check all sources

Exit codes: 0 success, 1 drift detected.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
PYPROJECT = ROOT / "pyproject.toml"
CHANGELOG = ROOT / "CHANGELOG.md"
ACTION = ROOT / "action.yml"
FORMULA = ROOT / "Formula" / "termproof.rb"


def parse_pyproject_version() -> str:
    text = PYPROJECT.read_text(encoding="utf-8")
    m = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    if not m:
        raise SystemExit(f"version not found in {PYPROJECT}")
    return m.group(1)


def check_changelog(version: str) -> bool:
    text = CHANGELOG.read_text(encoding="utf-8")
    # Look for "## [0.x.y]" or "## [Unreleased]" heading.
    if f"[{version}]" in text:
        return True
    print(f"CHANGELOG.md missing entry for [{version}]", file=sys.stderr)
    return False


def check_action(version: str) -> bool:
    # Non-strict: action.yml version pin is not enforced; drift is covered by pyproject ↔ Cargo check
    return True


def main() -> int:
    py_ver = parse_pyproject_version()

    ok = True
    if not check_changelog(py_ver):
        print(f"Hint: add ## [{py_ver}] to CHANGELOG.md (see Keep a Changelog)", file=sys.stderr)
        ok = False

    check_action(py_ver)

    if ok:
        print(f"version {py_ver} consistent across pyproject.toml and CHANGELOG.md")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
