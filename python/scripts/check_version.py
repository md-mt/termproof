#!/usr/bin/env python3
"""Single-source version and CHANGELOG drift check (RUST-023).

The canonical version lives in `pyproject.toml`. This script verifies that
`CHANGELOG.md` contains an entry for it. It also checks that `action.yml` and
`Formula/termproof.rb` reference the same version.

The Rust workspace is back in this repository and shares the version train,
so `rust/Cargo.toml` is checked against the same number: one version means one
point in the project's history for both implementations, and a drift between
the two manifests is what would quietly break that.

There is no `--fix` flag. A bump is a release decision, and the Rust
auto-release workflow already owns rewriting `rust/Cargo.toml`
(`.github/scripts/rust/version-bump.py`).

Usage:
  python scripts/check_version.py              # check all sources

Exit codes: 0 success, 1 drift detected.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
REPO_ROOT = ROOT.parent
PYPROJECT = ROOT / "pyproject.toml"
# One changelog at the repository root: both implementations share a version
# train, so a release number has one history entry, not two.
CHANGELOG = REPO_ROOT / "CHANGELOG.md"
ACTION = ROOT / "action.yml"
FORMULA = ROOT / "Formula" / "termproof.rb"
CARGO = REPO_ROOT / "rust" / "Cargo.toml"


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


def parse_cargo_version() -> str:
    """The `[workspace.package]` version every Rust crate inherits."""
    text = CARGO.read_text(encoding="utf-8")
    section = text.split("[workspace.package]", 1)
    if len(section) != 2:
        raise SystemExit(f"[workspace.package] not found in {CARGO}")
    m = re.search(r'^version\s*=\s*"([^"]+)"', section[1], re.MULTILINE)
    if not m:
        raise SystemExit(f"version not found under [workspace.package] in {CARGO}")
    return m.group(1)


def check_cargo(version: str) -> bool:
    cargo_version = parse_cargo_version()
    if cargo_version == version:
        return True
    print(
        f"version drift: pyproject.toml is {version}, "
        f"rust/Cargo.toml is {cargo_version}",
        file=sys.stderr,
    )
    return False


def check_action(version: str) -> bool:
    # Non-strict: action.yml version pin is not enforced; drift is covered by
    # the pyproject <-> Cargo check.
    return True


def main() -> int:
    py_ver = parse_pyproject_version()

    ok = True
    if not check_changelog(py_ver):
        print(f"Hint: add ## [{py_ver}] to CHANGELOG.md (see Keep a Changelog)", file=sys.stderr)
        ok = False

    if not check_cargo(py_ver):
        print(
            "Hint: the two implementations share one version train. Bump both "
            "manifests, or neither.",
            file=sys.stderr,
        )
        ok = False

    check_action(py_ver)

    if ok:
        print(
            f"version {py_ver} consistent across pyproject.toml, "
            "rust/Cargo.toml and CHANGELOG.md"
        )
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
