"""The repository may tell only one story about which version is current.

A stale version in a comment has now surfaced in four consecutive review
rounds, each time in a surface the previous sweep did not reach: first
`SECURITY.md`, then `rust/docs/publishing.md` and its `publish-plan.py`
example, then a workflow header, a workflow comment and a Dockerfile header —
and then, when 0.3.4 shipped to both registries, every one of them at once.
Each round the fix was to correct that surface. Sweeping by hand does not
converge — the same lesson `test_public_claims.py` records — so the sweep
lives here.

**What is asserted, and why each one exists.**

*Agreement, per artifact.* Two surfaces disagreeing about one artifact is drift
every time. Grouped per artifact rather than globally, because the version
train is shared and the release paths are not: after a Rust release the crate
is at the new version and PyPI is still at the old one, correctly.

*Correctness, against the manifest.* Agreement alone is what let 0.3.4 ship
while twelve surfaces went on saying 0.3.3 in perfect unison. So the manifest
version must be the one *something* claims, no claim may run ahead of it, and a
claim naming no artifact at all — a statement about the train itself — must be
exactly it. `python/scripts/check_version.py` already pins
`python/pyproject.toml` to `rust/Cargo.toml` and to a `CHANGELOG.md` heading,
so reading it here adds an oracle rather than a third mechanism.

*Contradiction, for the claims that carry no version.* `README.md` said "not
yet on PyPI" a full day after the package was there. No version sweep can see
that sentence, and a banned-wording list only catches phrasings someone thought
of first. What catches it is that the same document, two hundred lines below,
recorded PyPI as published: a denial is a failure exactly when the repository
elsewhere records that registry as carrying a version.

This file used to argue against the manifest tie, and the argument was worth
taking seriously: a version bump lands before the publish it precedes, so
"published through X" is briefly and legitimately behind the manifest, and
tying the two would turn every release bump into a red `main`. What answers it
is not a weaker assertion but a stronger release script.
`.github/scripts/rust/version-bump.py` moves the claims in the same commit as
the manifests, scoped to the artifacts the running release actually uploads,
and this file imports its patterns rather than keeping a second copy so the
rewriter and the sweep cannot disagree about what counts.

**What this still cannot see.**

- *The registry.* Nothing here queries PyPI or crates.io; a release that is
  tagged, bumped and merged but never uploaded passes everything below. That
  is deliberate — a networked test fails offline and in a sandbox, a worse
  failure than the one it prevents — and it is the gap a human covers by
  reading the release run.
- *A coherent rewrite of an artifact's whole story.* Moving every claim about
  one artifact backwards together, denial included, passes. The guard catches
  drift, which is what actually happens; it is not proof against a deliberate
  edit of the thing it reads.
- *A denial phrased in a way `NOT_PUBLISHED` has not met.* That set grows the
  way `test_public_claims.py` grows: when a new one is found.

A comment is a claim. Workflow headers, Dockerfile prose and script docstrings
are in scope for exactly the reason README prose is.
"""

from __future__ import annotations

import importlib.util
import re
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


#: Phrasings that assert an artifact is *not* on a registry. This is not a
#: banned-wording list: each is only a failure when the repository elsewhere
#: records that same registry as carrying a published version, which makes it
#: a contradiction rather than a phrase someone disapproves of. "not yet on
#: PyPI" sat on the front door for a day after the package was there, agreeing
#: with nothing and contradicted by the table two hundred lines below it.
NOT_PUBLISHED = {
    "pypi": re.compile(
        r"not (?:yet )?(?:\w+ )?on PyPI|gated behind the `?ENABLE_PYPI`?",
        re.IGNORECASE,
    ),
    "crates": re.compile(
        r"not (?:yet )?published to crates\.io|not (?:yet )?on crates\.io",
        re.IGNORECASE,
    ),
}


def _held_back() -> tuple[set[str], tuple[str, ...]]:
    """Crate names carrying `publish = false`, and the directories they own.

    Derived from the manifests rather than named here, the same way
    `.github/scripts/rust/publish-plan.py` derives the publish set: adding or
    renaming a held-back crate needs no edit to this file. Their "not published
    to crates.io" notices are true and must stay, so they are exempt from the
    contradiction check below — which is about the `termproof` crate.
    """
    names: set[str] = set()
    directories: list[str] = []
    for manifest in sorted((REPO_ROOT / "rust" / "crates").glob("*/Cargo.toml")):
        text = manifest.read_text(encoding="utf-8")
        if not re.search(r"^publish\s*=\s*false\s*$", text, re.MULTILINE):
            continue
        match = re.search(r'^name\s*=\s*"([^"]+)"', text, re.MULTILINE)
        if match:
            names.add(match.group(1))
        directories.append(
            manifest.parent.relative_to(REPO_ROOT).as_posix() + "/"
        )
    return names, tuple(directories)


def _claims() -> list[tuple[str, str, str | None]]:
    """Every current-version claim as `(site, version, artifact)`.

    `claim_windows` owns what counts and how far a wrapped claim reaches, and
    `claim_artifact` owns which artifact it speaks for; this only collects
    them.
    """
    found: list[tuple[str, str, str | None]] = []
    for name in version_bump.claim_files(REPO_ROOT):
        try:
            lines = (REPO_ROOT / name).read_text(encoding="utf-8").splitlines()
        except (UnicodeDecodeError, OSError):
            continue
        for index, claimed, span in version_bump.claim_windows(lines):
            artifact = version_bump.claim_artifact(name, lines, span)
            found.append((f"{name}:{index + 1}", claimed, artifact))
    return found


def _assertions() -> dict[str, list[str]]:
    """Asserted-as-current version -> where it is asserted."""
    found: dict[str, list[str]] = {}
    for site, version, _ in _claims():
        found.setdefault(version, []).append(site)
    return found


def _by_artifact() -> dict[str | None, dict[str, list[str]]]:
    """Artifact -> version -> sites."""
    found: dict[str | None, dict[str, list[str]]] = {}
    for site, version, artifact in _claims():
        found.setdefault(artifact, {}).setdefault(version, []).append(site)
    return found


def _order(version: str) -> list[int]:
    return [int(part) for part in version.split(".")]


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

    def test_every_surface_speaking_for_one_artifact_agrees_with_itself(
        self,
    ) -> None:
        """Two surfaces disagreeing about one artifact is drift, always.

        Grouped by artifact rather than globally, because after a Rust-only
        release the two groups legitimately differ: the crate is at the new
        version and PyPI is still at the old one. Within a group there is no
        such excuse.
        """
        for artifact, versions in sorted(
            _by_artifact().items(), key=lambda item: item[0] or ""
        ):
            with self.subTest(artifact=artifact or "the version train"):
                self.assertEqual(
                    1,
                    len(versions),
                    f"surfaces disagree about {artifact or 'the version train'}:\n"
                    + "\n".join(
                        f"  {version}: " + ", ".join(sorted(sites))
                        for version, sites in sorted(versions.items())
                    ),
                )

    def test_no_claim_runs_ahead_of_the_manifest(self) -> None:
        """A claim newer than the train is wrong under every reading."""
        manifest = _manifest_version()
        ahead = [
            f"{site} claims {version}"
            for site, version, _ in _claims()
            if _order(version) > _order(manifest)
        ]
        self.assertEqual(
            [],
            sorted(ahead),
            f"python/pyproject.toml is at {manifest}; these are ahead of it:\n  "
            + "\n  ".join(sorted(ahead)),
        )

    def test_the_release_that_moved_the_train_reached_the_prose(self) -> None:
        """Agreement on a stale number is still stale.

        A release makes the manifest version the published one for whatever it
        uploaded, so *something* must be claiming the manifest version. This is
        what the twelve-surfaces-stale-in-unison defect fails: they all agreed,
        and none of them named the version that had shipped.

        It is deliberately "at least one artifact" rather than "every artifact".
        The version train is shared but the release paths are not — the Rust
        auto-release cuts `rs-v*` and PyPI is only uploaded on `py-v*` — so a
        PyPI claim one release behind the manifest is the correct state between
        those two releases, and `version-bump.py --publishes` is what keeps it
        there.
        """
        manifest = _manifest_version()
        current = {
            artifact: sorted(versions, key=_order)[-1]
            for artifact, versions in _by_artifact().items()
        }
        self.assertIn(
            manifest,
            current.values(),
            f"python/pyproject.toml is at {manifest}, but nothing claims it:\n  "
            + "\n  ".join(
                f"{artifact or 'the version train'}: {version}"
                for artifact, version in sorted(
                    current.items(), key=lambda item: item[0] or ""
                )
            ),
        )

    def test_a_claim_about_the_train_itself_is_at_the_manifest(self) -> None:
        """Only an artifact gets to lag; the train is the manifest by definition.

        A claim that names no registry and sits outside either implementation's
        tree is about the project's current version. Without this, a stale
        sentence dropped into a root document would form its own agreeing
        group of one and pass everything above.
        """
        manifest = _manifest_version()
        stale = [
            f"{site} claims {version}"
            for site, version, artifact in _claims()
            if artifact is None and version != manifest
        ]
        self.assertEqual(
            [],
            sorted(stale),
            f"python/pyproject.toml is at {manifest}; these are not:\n  "
            + "\n  ".join(sorted(stale)),
        )

    def test_nothing_denies_a_publication_the_repository_records(self) -> None:
        """The half of the defect that carried no version number.

        `README.md` said "not yet on PyPI" while, two hundred lines below, its
        own "What is published" table said `yes, through 0.3.4`. No version
        sweep can see the first sentence — it names no version — and the
        wording net in `test_public_claims.py` had never been taught the
        phrase, so it survived a day past the publish that falsified it.

        What makes this an assertion rather than a blocklist is the condition:
        a phrasing is only a failure when the repository *elsewhere* records a
        published version for that same registry. Withdraw the publication
        everywhere and the phrasing becomes legal again, which is the correct
        behaviour — the two would then agree.
        """
        published = {artifact for _, _, artifact in _claims() if artifact is not None}
        self.assertTrue(published, "no artifact carries a published version")
        held_names, held_directories = _held_back()
        self.assertTrue(held_names, "no held-back crate found to exempt")

        offenders = []
        for name in version_bump.claim_files(REPO_ROOT):
            # `termproof-cli` and `termproof-plugin-protocol` really are not on
            # crates.io, and their own READMEs must go on saying so.
            if name.startswith(held_directories):
                continue
            try:
                lines = (REPO_ROOT / name).read_text(encoding="utf-8").splitlines()
            except (UnicodeDecodeError, OSError):
                continue
            for index, line in enumerate(lines):
                if any(held in line for held in held_names):
                    continue
                for artifact in sorted(published):
                    match = NOT_PUBLISHED[artifact].search(line)
                    if match:
                        offenders.append(
                            f"{name}:{index + 1}: {match.group(0)!r} — but the "
                            f"repository records {artifact} as published"
                        )
        self.assertEqual([], sorted(offenders), "\n" + "\n".join(sorted(offenders)))

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
            # Nothing that named the manifest version may still name it. A
            # claim deliberately left at an older version — the PyPI rows
            # between a Rust release and the next Python one — is not this
            # rewrite's business and must not trip it.
            leftover = [
                f"{name}:{index + 1}"
                for index, claimed, _ in version_bump.claim_windows(rewritten.splitlines())
                if claimed == current
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

    def test_a_claim_at_the_end_of_a_sentence_is_still_a_claim(self) -> None:
        """A full stop hid a stale claim from the sweep and the rewriter.

        `CLAIM_VERSION` forbade any trailing dot, to keep `0.3.3` inside
        `0.3.3.1` from reading as a version. That also swallowed `0.3.3.` at
        the end of a sentence, so `Published through 0.3.3.` appended to
        `README.md` left the whole guard green.
        """
        self.assertEqual(
            ["0.3.3"], version_bump.CLAIM_VERSION.findall("Published through 0.3.3.")
        )
        self.assertEqual(
            ["0.3.3"], version_bump.CLAIM_VERSION.findall("through v0.3.3, and")
        )
        # Still not a version: a longer dotted string, either way it continues.
        self.assertEqual([], version_bump.CLAIM_VERSION.findall("0.3.3.1"))
        self.assertEqual([], version_bump.CLAIM_VERSION.findall("0.3.3.rc1"))

        text = "Published through 0.3.3.\n"
        rewritten, edits = version_bump.rewrite_claims(text, "0.3.3", "0.3.4")
        self.assertEqual(1, len(edits), edits)
        self.assertEqual("Published through 0.3.4.\n", rewritten)

    def test_a_release_does_not_move_a_claim_it_does_not_publish(self) -> None:
        """The serious one: a Rust release must not vouch for PyPI.

        Both rows sit in the same table, two lines apart, and the version train
        is shared — so before the scope existed a Rust-only bump rewrote the
        PyPI row too. `python-release.yml` triggers on `py-v*` and gates the
        upload on that tag, so nothing about that rewrite had happened.
        """
        text = (
            "| `termproof` on PyPI | yes, through 0.3.4 |\n"
            "| `termproof` crate on crates.io | yes, through 0.3.4 |\n"
        )
        rewritten, edits = version_bump.rewrite_claims(
            text, "0.3.4", "0.3.5", name="README.md", publishes={"crates"}
        )
        self.assertEqual(1, len(edits), edits)
        self.assertIn("on PyPI | yes, through 0.3.4 |", rewritten)
        self.assertIn("crates.io | yes, through 0.3.5 |", rewritten)

        # The mirror case, and the default: a bump that publishes both moves
        # both, which is right for a manual release that precedes each tag.
        both, edits = version_bump.rewrite_claims(
            text, "0.3.4", "0.3.5", name="README.md", publishes=set(version_bump.ARTIFACTS)
        )
        self.assertEqual(2, len(edits), edits)
        self.assertIn("on PyPI | yes, through 0.3.5 |", both)

    def test_a_claim_naming_no_artifact_belongs_to_the_tree_it_lives_in(
        self,
    ) -> None:
        """Attribution falls back to the path, then to the version train.

        The Rust Dockerfile header and the release workflow's own header say
        nothing about a registry, but a Rust release is what moves them.
        """
        line = ["# reading what the shipped CLI can reach today (v0.3.4):"]
        self.assertEqual(
            "crates",
            version_bump.claim_artifact("rust/docker/termproof.Dockerfile", line, [0]),
        )
        self.assertEqual(
            "crates",
            version_bump.claim_artifact(".github/workflows/rust-release.yml", line, [0]),
        )
        self.assertEqual(
            "pypi",
            version_bump.claim_artifact("python/docs/releases.md", line, [0]),
        )
        self.assertIsNone(version_bump.claim_artifact("README.md", line, [0]))
        # Its own words win over where it lives.
        pypi = ["| `termproof` on PyPI | yes, through 0.3.4 |"]
        self.assertEqual(
            "pypi", version_bump.claim_artifact("rust/docs/publishing.md", pypi, [0])
        )

    def test_a_self_contained_claim_leaves_its_history_consistent(self) -> None:
        """Why the two release headers are worded the way they are.

        The rewriter follows a claim onto its next line and no further — going
        wider would edit prose that is not a claim at all. So a claim whose
        enumeration wraps past the break comes out contradicting itself:
        "through 0.3.5 … and rs-v0.3.4, the last one". The fix is prose shape,
        and this pins it: the sentence carries the version, and the history
        after it is phrased to stay true at every version.
        """
        wrapped = (
            "# VERIFIED: this ran on every release tag through\n"
            "# 0.3.4 — v0.2.1 to v0.3.3 there, and rs-v0.3.4, the newest here.\n"
        )
        out, _ = version_bump.rewrite_claims(
            wrapped, "0.3.4", "0.3.5", name="x.yml", publishes={"crates"}
        )
        self.assertIn("through\n# 0.3.5", out)
        self.assertIn("rs-v0.3.5, the newest here", out)  # dragged along, wrongly

        self_contained = (
            "# VERIFIED: this ran on every release tag through 0.3.4.\n"
            "# That is v0.2.1 to v0.3.3 there, plus every tag cut here since —\n"
            "# rs-v0.3.4 was the first.\n"
        )
        out, edits = version_bump.rewrite_claims(
            self_contained, "0.3.4", "0.3.5", name="x.yml", publishes={"crates"}
        )
        self.assertEqual(1, len(edits), edits)
        self.assertIn("through 0.3.5.", out)
        self.assertIn("rs-v0.3.4 was the first", out)

    def test_the_two_release_headers_use_that_shape(self) -> None:
        """The shape above, asserted on the real files that had the defect."""
        current = _manifest_version()
        for name in (
            ".github/workflows/rust-release.yml",
            "rust/docs/publishing.md",
        ):
            with self.subTest(name=name):
                text = (REPO_ROOT / name).read_text(encoding="utf-8")
                out, _ = version_bump.rewrite_claims(
                    text, current, "99.0.0", name=name, publishes={"crates"}
                )
                # Every `rs-v<version>` in these two is history — which tag was
                # the first cut here, which range came from the old repository.
                # A bump that moved one means the enumeration was inside a
                # claim's blast radius again, and the header now contradicts
                # the sentence above it.
                tag = re.compile(r"\brs-v\d+\.\d+\.\d+")
                self.assertEqual(sorted(tag.findall(text)), sorted(tag.findall(out)))
                # The pre-consolidation range is history for the same reason.
                self.assertIn("v0.2.1", out)
                self.assertIn("v0.3.3", out)

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
