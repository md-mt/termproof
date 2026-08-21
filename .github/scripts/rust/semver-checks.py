#!/usr/bin/env python3
"""Run `cargo semver-checks` and hold its findings to a checked-in waiver list.

    .github/scripts/rust/semver-checks.py

This wraps the check rather than replacing it. Every lint still runs, against
the same published baseline, and the tool's own output is echoed verbatim. The
only thing this adds is the last step: compare the set of findings against
`semver-waivers.toml` and exit non-zero unless the two agree exactly.

# Why a wrapper and not a lint switch

`cargo-semver-checks` 0.50.0 has no per-item waiver: no `--exclude-lint`, no
JSON output to post-process, and the `[package.metadata.semver-checks.lints]`
table is not read at this version (checked — the findings still fail with it
set). The mechanisms it does offer are all-or-nothing: silence a lint for the
whole crate, or drop the job. Both would waive breaks nobody has looked at,
which is the property that makes a waiver dangerous.

So the waiver is by *finding*, not by lint. `field name of struct Recipe` is
waived; `field checks of struct Recipe` is not, and a change that removed it
would fail this job with the lint still saying so.

# Exact agreement, in both directions

An unwaived finding fails, which is the obvious half. A waiver that matches
nothing also fails, which is the half that matters more: it is what stops a
waiver outliving the release it was written for. When the maintainer bumps the
version and publishes, the baseline moves past these breaks, the findings
disappear, and this job fails asking for the waiver to be deleted. A waiver
that cannot expire is a disabled check with extra steps.

# Finding identity

A finding is `<lint>: <item>`, where the item is the tool's own wording with
the trailing file path and line number cut off — those move whenever the file
does and say nothing about which API broke. `cargo-semver-checks` reports each
finding once per feature set it checked, so the set is deduplicated.
"""

from __future__ import annotations

import re
import subprocess
import sys
import tomllib
from pathlib import Path

RUST_ROOT = Path(__file__).resolve().parents[3] / "rust"
WAIVERS = RUST_ROOT / "semver-waivers.toml"

COMMAND = ["cargo", "semver-checks", "check-release", "-p", "termproof"]

# `--- failure struct_pub_field_missing: pub struct's pub field removed ... ---`
_FAILURE_HEADER = re.compile(r"^--- failure ([a-z0-9_]+): ")
# The tool indents each offending item by two spaces under `Failed in:`.
_ITEM = re.compile(r"^ {2}(\S.*)$")
# Everything from the location onward: ` in /abs/path.rs:12`, or
# `, previously in file /abs/path.rs:166`.
_LOCATION = re.compile(r"(, previously in file | in )/.*$")


def findings(output: str) -> set[str]:
    """The `<lint>: <item>` findings in a `cargo semver-checks` run."""
    found: set[str] = set()
    lint: str | None = None
    in_items = False
    for line in output.splitlines():
        header = _FAILURE_HEADER.match(line)
        if header:
            lint, in_items = header.group(1), False
            continue
        if line.startswith("Failed in:"):
            in_items = True
            continue
        if not in_items:
            continue
        item = _ITEM.match(line)
        if item is None:
            # A blank line or an unindented line ends the item block.
            in_items = False
            continue
        found.add(f"{lint}: {_LOCATION.sub('', item.group(1)).strip()}")
    return found


def waived() -> tuple[set[str], str]:
    """The waived findings, and the reason recorded beside them."""
    if not WAIVERS.exists():
        return set(), ""
    data = tomllib.loads(WAIVERS.read_text(encoding="utf-8"))
    return set(data.get("waived", [])), data.get("reason", "")


def main() -> int:
    completed = subprocess.run(
        COMMAND,
        cwd=RUST_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    output = completed.stdout + completed.stderr
    sys.stdout.write(output)
    sys.stdout.flush()

    found = findings(output)
    allowed, reason = waived()

    unwaived = sorted(found - allowed)
    stale = sorted(allowed - found)

    if not unwaived and not stale:
        if found:
            print(
                f"\nsemver-checks: {len(found)} finding(s), all waived by "
                f"{WAIVERS.name}.\nWaiver reason: {reason}"
            )
        elif completed.returncode != 0:
            # The tool failed for a reason that is not a semver finding — a
            # build error, a missing baseline. Do not swallow it.
            print("\nsemver-checks: no findings parsed, but the tool failed.")
            return completed.returncode
        return 0

    if unwaived:
        print("\nsemver-checks: breaking change(s) with no waiver:")
        for finding in unwaived:
            print(f"  {finding}")
        print(
            "\nEither this is not intended, or it needs an entry in "
            f"{WAIVERS.name} and a CHANGELOG line describing it."
        )
    if stale:
        print("\nsemver-checks: waiver entries that no longer match anything:")
        for finding in stale:
            print(f"  {finding}")
        print(
            f"\nEither the break they cover is gone — the baseline moved past "
            f"it in a release, so delete them from {WAIVERS.name} — or the run "
            f"above did not get as far as reporting findings. Read its output."
        )
    return 1


if __name__ == "__main__":
    sys.exit(main())
