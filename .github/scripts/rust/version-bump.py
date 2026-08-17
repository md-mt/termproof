#!/usr/bin/env python3
"""Move the whole version train to a new version, then prove it took.

    .github/scripts/rust/version-bump.py 0.2.2
    .github/scripts/rust/version-bump.py 0.2.2 --check   # report, change nothing

The two implementations share one version train (README.md, CHANGELOG.md,
rust/docs/publishing.md), and `python/scripts/check_version.py` fails CI when
they drift. This script is the one place the train moves, so an automated Rust
release cannot leave the Python manifest or the changelog behind — which is
exactly what it used to do, bumping `rust/Cargo.toml` alone and pushing a
`main` that failed its own drift check.

Four places carry the version and must move together:

  - `rust/Cargo.toml`, `[workspace.package] version`, which every member
    inherits;
  - `rust/Cargo.toml`, the `version` on each internal dependency in
    `[workspace.dependencies]`, which is what the *published* package resolves
    against. The `path` beside it is what a local build uses, so a stale
    `version` here compiles fine locally and fails at publish time, which is
    the worst moment to find it;
  - `python/pyproject.toml`, `[project] version`;
  - `CHANGELOG.md` at the repository root, where the pending `[Unreleased]`
    section is promoted to a heading for this version and a fresh empty
    `[Unreleased]` takes its place. Keep a Changelog's release step, and what
    keeps the curated entries contributors wrote rather than generating prose
    over the top of them.

Internal dependencies are identified by the presence of `path = `, not by
name. No crate is named in this file, so merging several crates into one, or
adding one, needs no edit here.

Editing is a line-level substitution rather than a TOML round-trip, so
comments, ordering and formatting survive byte-for-byte. The safety net is not
the parser, it is the verification at the end: `cargo metadata` must report
every workspace member at the new version, the Python manifest must read back
at it, and the changelog must carry a heading for it — or this exits non-zero
having said which one did not move.

Re-running it is safe: a tree already at the target version is reported and
left alone rather than promoted twice.
"""

import argparse
import datetime
import json
import os
import re
import subprocess
import sys
from pathlib import Path

RUST_ROOT = os.environ.get("TERMPROOF_RUST_ROOT", "rust")
PYTHON_ROOT = os.environ.get("TERMPROOF_PYTHON_ROOT", "python")

SEMVER = re.compile(r"^\d+\.\d+\.\d+$")
SECTION = re.compile(r"^\s*\[([^\]]+)\]\s*$")

# `version = "0.2.1"` as a bare key, anywhere on the line.
BARE_VERSION = re.compile(r'(?P<lead>^\s*version\s*=\s*")(?P<ver>[^"]+)(?P<tail>")')

# `version = "0.2.1"` inside an inline table, e.g.
# `foo = { path = "crates/foo", version = "0.2.1" }`.
INLINE_VERSION = re.compile(r'(?P<lead>\bversion\s*=\s*")(?P<ver>[^"]+)(?P<tail>")')


def cargo_metadata():
    out = subprocess.run(
        [
            "cargo",
            "metadata",
            "--manifest-path",
            os.path.join(RUST_ROOT, "Cargo.toml"),
            "--no-deps",
            "--format-version",
            "1",
        ],
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    return json.loads(out)


def rewrite(text, old, new):
    """Return (new_text, [description of each edit])."""
    out = []
    edits = []
    section = None
    for lineno, line in enumerate(text.splitlines(keepends=True), start=1):
        header = SECTION.match(line)
        if header:
            section = header.group(1).strip()
            out.append(line)
            continue

        if section == "workspace.package":
            match = BARE_VERSION.match(line)
            if match and match.group("ver") == old:
                line = BARE_VERSION.sub(rf"\g<lead>{new}\g<tail>", line, count=1)
                edits.append(f"line {lineno}: [workspace.package] version -> {new}")

        elif section == "workspace.dependencies" and "path" in line:
            match = INLINE_VERSION.search(line)
            if match and match.group("ver") == old:
                key = line.split("=", 1)[0].strip()
                line = INLINE_VERSION.sub(rf"\g<lead>{new}\g<tail>", line, count=1)
                edits.append(f"line {lineno}: [workspace.dependencies] {key} version -> {new}")

        out.append(line)
    return "".join(out), edits


def rewrite_pyproject(text, old, new):
    """Return (new_text, [edits]) for `[project] version` in pyproject.toml.

    Section-aware for the same reason the Cargo rewrite is: `version = "..."`
    also appears under `[tool.*]` and inside dependency specifiers, and a
    global substitution would reach them.
    """
    out = []
    edits = []
    section = None
    for lineno, line in enumerate(text.splitlines(keepends=True), start=1):
        header = SECTION.match(line)
        if header:
            section = header.group(1).strip()
            out.append(line)
            continue
        if section == "project":
            match = BARE_VERSION.match(line)
            if match and match.group("ver") == old:
                line = BARE_VERSION.sub(rf"\g<lead>{new}\g<tail>", line, count=1)
                edits.append(f"line {lineno}: [project] version -> {new}")
        out.append(line)
    return "".join(out), edits


#: `## [Unreleased]`, however it is capitalised.
UNRELEASED_HEADING = re.compile(r"^##\s*\[Unreleased\]\s*$", re.IGNORECASE | re.MULTILINE)

FRESH_UNRELEASED = """## [Unreleased]

Nothing yet.
"""


def promote_changelog(text, new, date):
    """Return (new_text, [edits]): `[Unreleased]` becomes `[new] — date`.

    A fresh, empty `[Unreleased]` is written above it, so the next change has
    somewhere to land. Whatever contributors wrote under `[Unreleased]` becomes
    the release's entry unchanged — this promotes, it does not generate.

    Idempotent: a changelog that already carries a heading for `new` is left
    alone, so a re-run of a half-finished release does not promote twice.
    """
    if re.search(rf"^##\s*\[{re.escape(new)}\]", text, re.MULTILINE):
        return text, []

    match = UNRELEASED_HEADING.search(text)
    if match is None:
        raise ValueError(
            "CHANGELOG.md has no `## [Unreleased]` heading to promote. A release "
            "needs an entry; add the section back before bumping."
        )

    released = f"## [{new}] \u2014 {date}"
    updated = text[: match.start()] + FRESH_UNRELEASED + "\n" + released + text[match.end() :]
    return updated, [f"CHANGELOG.md: [Unreleased] -> [{new}] \u2014 {date}"]


def read_pyproject_version(path):
    section = None
    for line in path.read_text(encoding="utf-8").splitlines():
        header = SECTION.match(line)
        if header:
            section = header.group(1).strip()
            continue
        if section == "project":
            match = BARE_VERSION.match(line)
            if match:
                return match.group("ver")
    return None



def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("version", help="the new version, e.g. 0.2.2")
    parser.add_argument("--check", action="store_true", help="report edits without writing")
    parser.add_argument(
        "--date",
        help="release date for the changelog heading (default: today, UTC)",
    )
    args = parser.parse_args()

    new = args.version
    if not SEMVER.match(new):
        sys.exit(f"error: '{new}' is not a bare x.y.z version")
    date = args.date or datetime.datetime.now(datetime.timezone.utc).date().isoformat()

    meta = cargo_metadata()
    root = Path(meta["workspace_root"])
    manifest = root / "Cargo.toml"
    # The workspace root is `<repo>/rust`, so its parent is the repository
    # root. Derived rather than assumed from the working directory, so this
    # behaves the same whether it is run from the root or from `rust/`.
    repo = root.parent
    pyproject = repo / PYTHON_ROOT / "pyproject.toml"
    changelog = repo / "CHANGELOG.md"

    old = sorted({pkg["version"] for pkg in meta["packages"]})
    if len(old) != 1:
        detail = ", ".join(f"{p['name']} {p['version']}" for p in meta["packages"])
        sys.exit(f"error: workspace members disagree on version: {detail}")
    old = old[0]

    py_old = read_pyproject_version(pyproject)
    if py_old is None:
        sys.exit(f"error: no [project] version in {pyproject}")
    # Refuse to bump out of a state that is already broken: the train has to be
    # together before it can be moved, or this would paper over the drift by
    # moving both onto the new number and hiding how they diverged.
    if py_old != old and py_old != new:
        sys.exit(
            f"error: the version train is already split — {manifest} is at {old} "
            f"and {pyproject} is at {py_old}. Reconcile them before bumping."
        )

    edits = []
    writes = []

    if old == new:
        print(f"rust workspace already at {new}")
    else:
        updated, cargo_edits = rewrite(manifest.read_text(encoding="utf-8"), old, new)
        if not cargo_edits:
            sys.exit(f"error: found nothing to bump from {old} to {new} in {manifest}")
        edits += cargo_edits
        writes.append((manifest, updated))

    if py_old == new:
        print(f"python package already at {new}")
    else:
        updated, py_edits = rewrite_pyproject(
            pyproject.read_text(encoding="utf-8"), py_old, new
        )
        if not py_edits:
            sys.exit(f"error: found nothing to bump from {py_old} to {new} in {pyproject}")
        edits += py_edits
        writes.append((pyproject, updated))

    try:
        updated, log_edits = promote_changelog(
            changelog.read_text(encoding="utf-8"), new, date
        )
    except ValueError as exc:
        sys.exit(f"error: {exc}")
    if log_edits:
        edits += log_edits
        writes.append((changelog, updated))
    else:
        print(f"CHANGELOG.md already carries a heading for {new}")

    if not edits:
        print(f"already at {new}; nothing to do")
        return

    for edit in edits:
        print(edit)

    if args.check:
        print("--check: no files written")
        return

    for path, content in writes:
        path.write_text(content, encoding="utf-8")

    if old != new:
        # `cargo update -w` refreshes only the workspace members' own entries in
        # Cargo.lock, leaving every third-party pin exactly where it was. Without
        # it the lockfile still claims the old version and the release commit is
        # internally inconsistent.
        subprocess.run(["cargo", "update", "-w", "--manifest-path", str(manifest)], check=True)

    after = cargo_metadata()
    stale = sorted(p["name"] for p in after["packages"] if p["version"] != new)
    if stale:
        sys.exit(
            f"error: after the bump these members are still not at {new}: {', '.join(stale)}. "
            "They probably do not inherit version from [workspace.package]."
        )

    py_after = read_pyproject_version(pyproject)
    if py_after != new:
        sys.exit(f"error: after the bump {pyproject} reads {py_after}, not {new}")

    if not re.search(rf"^##\s*\[{re.escape(new)}\]", changelog.read_text(encoding="utf-8"), re.MULTILINE):
        sys.exit(f"error: after the bump {changelog} has no heading for {new}")

    print(
        f"version train is at {new}: "
        f"{', '.join(sorted(p['name'] for p in after['packages']))}, "
        f"{pyproject.name}, {changelog.name}"
    )


if __name__ == "__main__":
    main()
