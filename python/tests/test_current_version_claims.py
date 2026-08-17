"""The repository may tell only one story about which version is current.

A stale version in a comment has now surfaced in three consecutive review
rounds, each time in a surface the previous sweep did not reach: first
`SECURITY.md`, then `rust/docs/publishing.md` and its `publish-plan.py`
example, then a workflow header, a workflow comment and a Dockerfile header.
Each round the fix was to correct that surface. Sweeping by hand does not
converge — the same lesson `test_public_claims.py` records — so the sweep
lives here.

**What this asserts is agreement, not correctness.** It does not know what is
on crates.io, and it deliberately does not compare against the manifest: a
version bump lands before the publish it precedes, so "published through X" is
briefly and legitimately behind `Cargo.toml`. Tying these to the manifest would
turn every release bump into a false failure, and an automated Rust release
would push a red `main`.

What it can say without an oracle is the thing that actually went wrong three
times: two surfaces claiming *different* current versions. One project tells
one story. When the story changes, it changes everywhere in the same commit,
and this names every place that has to move.

A comment is a claim. Workflow headers, Dockerfile prose and script docstrings
are in scope for exactly the reason README prose is.
"""

from __future__ import annotations

import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent

#: Phrasings that make a version a statement about *now* rather than an
#: example, a dependency pin or a historical range's lower bound.
CURRENCY = re.compile(
    r"\btoday\b|\bcurrently\b|\blatest published\b|\bVERIFIED\b|\bso far\b"
    r"|\bas of\b|\bthrough\b|\bhas run\b|\bran\b",
    re.IGNORECASE,
)

#: A bare or `v`-prefixed semver, not part of a longer dotted string (so
#: `1.0.69` inside `thiserror 1.0.69` still matches, but `0.3.3.1` does not).
VERSION = re.compile(r"(?<![\w.])v?(\d+\.\d+\.\d+)(?![\w.])")

#: Generated output, vendored tooling, lockfiles, and this suite itself —
#: which necessarily contains example versions to test against.
EXCLUDED_PREFIXES = (
    "python/examples/artifacts/",
    "python/site/artifacts/",
    "python/_site/",
    "conformance/corpus/",
    "rust/.specify/",
    "rust/.claude/",
    "python/.hermes/",
    "python/tests/",
    "python/docs-site/package-lock.json",
    "python/uv.lock",
    "rust/Cargo.lock",
)


def _assertions() -> dict[str, list[str]]:
    """Map each asserted-as-current version to where it is asserted.

    The window is the matching line plus the one after it: a comment that wraps
    mid-sentence — `... every tag from v0.2.1 through` / `v0.3.3 ...` — is one
    claim, and a line-only scan reads the range's lower bound as the answer.
    That exact wrap is how the workflow header escaped the last sweep.
    """
    tracked = subprocess.run(
        ["git", "ls-files"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.split()

    found: dict[str, list[str]] = {}
    for name in tracked:
        if name.startswith(EXCLUDED_PREFIXES):
            continue
        try:
            lines = (REPO_ROOT / name).read_text(encoding="utf-8").splitlines()
        except (UnicodeDecodeError, OSError):
            continue
        for index, line in enumerate(lines):
            if not CURRENCY.search(line):
                continue
            versions = VERSION.findall("\n".join(lines[index : index + 2]))
            if not versions:
                continue
            # The newest version in the window: a claim written as a range
            # ("from v0.2.1 through v0.3.3") is a claim about its upper bound.
            top = max(versions, key=lambda v: [int(part) for part in v.split(".")])
            found.setdefault(top, []).append(f"{name}:{index + 1}")
    return found


class CurrentVersionClaimsTest(unittest.TestCase):
    def test_the_sweep_is_not_vacuous(self) -> None:
        """Guard the guard: a broken pattern would agree with itself."""
        found = _assertions()
        sites = [site for group in found.values() for site in group]
        self.assertGreater(len(sites), 8, "the sweep found almost nothing")
        # The three surfaces that escaped the previous round, so a scope that
        # stops covering workflows or Dockerfiles fails here.
        for required in (
            ".github/workflows/rust-release.yml",
            ".github/workflows/rust-security.yml",
            "rust/docker/termproof.Dockerfile",
            "rust/docs/publishing.md",
            "SECURITY.md",
        ):
            self.assertTrue(
                any(site.startswith(required + ":") for site in sites),
                f"{required} carries no current-version claim; if that is "
                "deliberate, remove it from this list",
            )

    def test_every_surface_names_the_same_current_version(self) -> None:
        found = _assertions()
        self.assertEqual(
            1,
            len(found),
            "the repository claims more than one current version:\n"
            + "\n".join(
                f"  {version}: " + ", ".join(sorted(sites))
                for version, sites in sorted(found.items())
            ),
        )


if __name__ == "__main__":
    unittest.main()
