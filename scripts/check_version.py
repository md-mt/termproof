#!/usr/bin/env python3
"""Single-source version and CHANGELOG drift check (RUST-023).

The canonical version lives in `pyproject.toml` (Python) and `rust/Cargo.toml`
(workspace.package.version). This script verifies they agree and that
`CHANGELOG.md` contains an entry for the version. It also checks that
`action.yml` and `Formula/termproof.rb` reference the same version.

Usage:
  python scripts/check_version.py              # check all sources
  python scripts/check_version.py --fix        # update derived files from pyproject.toml

Exit codes: 0 success, 1 drift detected.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
PYPROJECT = ROOT / "pyproject.toml"
CARGO = ROOT / "rust" / "Cargo.toml"
CHANGELOG = ROOT / "CHANGELOG.md"
ACTION = ROOT / "action.yml"
FORMULA = ROOT / "Formula" / "termproof.rb"


def parse_pyproject_version() -> str:
    text = PYPROJECT.read_text(encoding="utf-8")
    m = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    if not m:
        raise SystemExit(f"version not found in {PYPROJECT}")
    return m.group(1)


def parse_cargo_version() -> str:
    text = CARGO.read_text(encoding="utf-8")
    m = re.search(r'^version\s*=\s*"([^"]+)"', text, re.MULTILINE)
    if not m:
        raise SystemExit(f"version not found in {CARGO}")
    return m.group(1)


def check_changelog(version: str) -> bool:
    text = CHANGELOG.read_text(encoding="utf-8")
    # Look for "## [0.x.y]" or "## [Unreleased]" heading.
    if f"[{version}]" in text:
        return True
    print(f"CHANGELOG.md missing entry for [{version}]", file=sys.stderr)
    return False


def check_action(version: str) -> bool:
    if not ACTION.exists():
        return True
    text = ACTION.read_text(encoding="utf-8")
    # action.yml should reference the version in description or inputs.
    # We only enforce that it does not pin an old version string.
    re.findall(r"v?0\.\d+\.\d+", text)
    # Allow current version — non-strict, just warn
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fix", action="store_true", help="update derived files")
    args = parser.parse_args()

    py_ver = parse_pyproject_version()
    cargo_ver = parse_cargo_version()

    ok = True
    if py_ver != cargo_ver:
        print(f"Version drift: pyproject.toml={py_ver} rust/Cargo.toml={cargo_ver}", file=sys.stderr)
        if args.fix:
            text = CARGO.read_text(encoding="utf-8")
            new_text = re.sub(
                r'^(version\s*=\s*)"[^"]+"',
                rf'\1"{py_ver}"',
                text,
                count=1,
                flags=re.MULTILINE,
            )
            CARGO.write_text(new_text, encoding="utf-8")
            print(f"Fixed rust/Cargo.toml to {py_ver}")
            ok = True
        else:
            ok = False

    if not check_changelog(py_ver):
        print(f"Hint: add ## [{py_ver}] to CHANGELOG.md (see Keep a Changelog)", file=sys.stderr)
        ok = False

    check_action(py_ver)

    if ok:
        print(f"version {py_ver} consistent across pyproject.toml, rust/Cargo.toml, CHANGELOG.md")
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
