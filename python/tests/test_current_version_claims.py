"""The repository may tell only one story about which version is current.

A stale version in a comment has now surfaced in four consecutive review
rounds, each time in a surface the previous sweep did not reach: first
`SECURITY.md`, then `rust/docs/publishing.md` and its `publish-plan.py`
example, then a workflow header, a workflow comment and a Dockerfile header —
and then, when 0.3.4 shipped to both registries, every one of them at once.
Each round the fix was to correct that surface. Sweeping by hand does not
converge — the same lesson `test_public_claims.py` records — so the sweep
lives here.

**Two things are asserted, and the second one is new.**

*Agreement.* Two surfaces claiming different current versions is what actually
went wrong three times running. One project tells one story; when the story
changes, it changes everywhere in the same commit, and this names every place
that has to move.

*Correctness, against the manifests.* Agreement alone is what let 0.3.4 ship
while twelve surfaces went on saying 0.3.3 in perfect unison, and `README.md`
went on saying "not yet on PyPI" a full day after the package was there. So
the one agreed version must also be the version `python/pyproject.toml` is at
— which `python/scripts/check_version.py` already pins to `rust/Cargo.toml`
and to a `CHANGELOG.md` heading.

This file used to argue the opposite, and the argument was worth taking
seriously: a version bump lands before the publish it precedes, so
"published through X" is briefly and legitimately behind `Cargo.toml`, and
tying the two would turn every release bump into a red `main`. What answers it
is not a weaker assertion but a stronger release script.
`.github/scripts/rust/version-bump.py` now moves the claims in the same commit
as the manifests, and this file imports its `CURRENCY` pattern rather than
keeping a second copy, so the rewriter and the sweep cannot disagree about
what counts as a claim. The residual window — the minutes between the bump
commit and the upload finishing — is a claim that is briefly early rather than
indefinitely late, and it is the smaller wrong.

**What this still cannot see is the registry.** Nothing here queries PyPI or
crates.io; a release that is tagged, bumped and merged but never actually
uploaded passes every assertion below. That is deliberate — a networked test
fails offline and in a sandbox, which is a worse failure than the one it
prevents — and it is the gap a human has to cover by reading the release run.

A comment is a claim. Workflow headers, Dockerfile prose and script docstrings
are in scope for exactly the reason README prose is.
"""

from __future__ import annotations

import importlib.util
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent

#: The release script owns the definition of "a current-version claim" because
#: it is the thing that has to rewrite one. Loading it by path rather than
#: re-deriving the patterns here is what stops the sweep and the rewriter
#: drifting apart; `test_version_bump.py` loads the same script the same way.
_SCRIPT = REPO_ROOT / ".github" / "scripts" / "rust" / "version-bump.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("version_bump", _SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


version_bump = _load_script()

CURRENCY = version_bump.CURRENCY
EXCLUDED_PREFIXES = version_bump.CLAIM_EXCLUDED_PREFIXES


def _manifest_version() -> str:
    """The version the repository's own manifests are at.

    `python/pyproject.toml` is the single source `check_version.py` treats as
    canonical, and it already fails CI when `rust/Cargo.toml` or `CHANGELOG.md`
    disagrees with it. Reading it here rather than re-deriving the agreement is
    what keeps this from becoming a third overlapping mechanism.
    """
    version = version_bump.read_pyproject_version(ROOT / "pyproject.toml")
    assert version is not None, "no [project] version in python/pyproject.toml"
    return version


def _assertions() -> dict[str, list[str]]:
    """Map each asserted-as-current version to where it is asserted.

    `claim_windows` owns what counts and how far a wrapped claim reaches; this
    only groups the results by the version they name.
    """
    found: dict[str, list[str]] = {}
    for name in version_bump.claim_files(REPO_ROOT):
        try:
            lines = (REPO_ROOT / name).read_text(encoding="utf-8").splitlines()
        except (UnicodeDecodeError, OSError):
            continue
        for index, claimed, _ in version_bump.claim_windows(lines):
            found.setdefault(claimed, []).append(f"{name}:{index + 1}")
    return found


class CurrentVersionClaimsTest(unittest.TestCase):
    def test_the_sweep_is_not_vacuous(self) -> None:
        """Guard the guard: a broken pattern would agree with itself."""
        found = _assertions()
        sites = [site for group in found.values() for site in group]
        self.assertGreater(len(sites), 8, "the sweep found almost nothing")
        # The surfaces that each escaped a round, so a scope that stops
        # covering workflows, Dockerfiles or the front door fails here.
        for required in (
            ".github/workflows/rust-release.yml",
            ".github/workflows/rust-security.yml",
            "rust/docker/termproof.Dockerfile",
            "rust/docs/publishing.md",
            "README.md",
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

    def test_the_current_version_is_the_version_that_shipped(self) -> None:
        """Agreement on a stale number is still stale.

        A release makes the manifest version the published one, so the
        manifest is the offline oracle for what the prose may claim. When this
        fails on a release commit, the fix is not to relax it: it means
        `version-bump.py` did not move a claim it should have, and the
        published documentation is about to go out a release behind.
        """
        expected = _manifest_version()
        found = _assertions()
        stale = {
            version: sites for version, sites in found.items() if version != expected
        }
        self.assertEqual(
            {},
            stale,
            f"python/pyproject.toml is at {expected}, but these claim otherwise:\n"
            + "\n".join(
                f"  {version}: " + ", ".join(sorted(sites))
                for version, sites in sorted(stale.items())
            ),
        )

    def test_the_release_script_moves_every_claim_it_finds(self) -> None:
        """The guard above is only safe because the bump keeps up with it.

        Without this the manifest tie is a trap: the release commit would bump
        `pyproject.toml`, leave the prose behind, and fail the very `main` the
        release is cut from. Run against the real tree so a claim in a shape
        the rewriter cannot reach shows up here and not in a release run.
        """
        current = _manifest_version()
        target = "99.0.0"
        moved = 0
        for name in version_bump.claim_files(REPO_ROOT):
            try:
                text = (REPO_ROOT / name).read_text(encoding="utf-8")
            except (UnicodeDecodeError, OSError):
                continue
            rewritten, _ = version_bump.rewrite_claims(text, current, target)
            leftover = [
                f"{name}:{index + 1}"
                for index, claimed, _ in version_bump.claim_windows(rewritten.splitlines())
                if claimed != target
            ]
            self.assertEqual([], leftover, f"version-bump.py cannot move {leftover}")
            moved += rewritten != text
        self.assertGreater(moved, 3, "the rewrite reached almost nothing")

    def test_the_rewrite_leaves_versions_that_are_not_claims_alone(self) -> None:
        """A pin, an example and a range's lower bound are not claims."""
        text = (
            'thiserror = "1.0.69"\n'
            "So `rs-v0.3.3` against a workspace at `0.3.3` passes.\n"
            "Published through 0.3.3 today.\n"
            "Releases up to 0.3.3 predate the consolidation.\n"
        )
        rewritten, edits = version_bump.rewrite_claims(text, "0.3.3", "0.3.4")
        self.assertEqual(1, len(edits), edits)
        self.assertIn('thiserror = "1.0.69"', rewritten)
        self.assertIn("`rs-v0.3.3` against a workspace at `0.3.3`", rewritten)
        self.assertIn("Published through 0.3.4 today.", rewritten)
        self.assertIn("Releases up to 0.3.3 predate", rewritten)

    def test_the_rewrite_reaches_a_claim_that_wraps(self) -> None:
        """The wrapped-comment case the window exists for."""
        text = "# VERIFIED: this ran on every tag from\n# v0.2.1 through v0.3.3 in the old repository.\n"
        rewritten, edits = version_bump.rewrite_claims(text, "0.3.3", "0.3.4")
        self.assertEqual(1, len(edits), edits)
        self.assertIn("v0.2.1 through v0.3.4", rewritten)

    def test_the_currency_pattern_is_shared_with_the_release_script(self) -> None:
        """Two copies of this pattern is the failure this import prevents."""
        self.assertIs(CURRENCY, version_bump.CURRENCY)
        self.assertTrue(CURRENCY.search("published through 0.3.4 today"))
        self.assertFalse(CURRENCY.search("releases up to 0.3.3 predate this"))

    def test_the_enumeration_skips_generated_trees(self) -> None:
        """A recorded artifact is not prose, and must not become a claim."""
        names = version_bump.claim_files(REPO_ROOT)
        self.assertGreater(len(names), 100, "the file enumeration collapsed")
        for name in names:
            self.assertFalse(
                name.startswith(EXCLUDED_PREFIXES),
                f"{name} should have been excluded",
            )
        # Driven off `git ls-files`, so an untracked scratch file is invisible
        # and a new documentation page is covered the moment it is added.
        tracked = set(
            subprocess.run(
                ["git", "ls-files"],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
                check=True,
            ).stdout.split()
        )
        self.assertTrue(set(names) <= tracked)


if __name__ == "__main__":
    unittest.main()
