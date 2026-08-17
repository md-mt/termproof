"""The Rust release automation must move the whole version train, not part of it.

`version-bump.py` used to rewrite `rust/Cargo.toml` and `Cargo.lock` and
nothing else. That was correct while the Rust workspace was its own repository
with its own version. It is not correct now: `python/scripts/check_version.py`
enforces that `python/pyproject.toml`, `rust/Cargo.toml` and the root
`CHANGELOG.md` agree, and `README.md`, `CHANGELOG.md` and
`rust/docs/publishing.md` all state that the two implementations share one
version train.

So the first real Rust auto-release would have pushed a `main` carrying Rust
at the new version, Python at the old one and no changelog heading — a release
that immediately fails the repository's own drift check, published before
anyone could see it. These tests pin the fix: the script is the one place the
train moves, and it moves all of it.

The rewrite helpers are pure functions over text, so they are tested directly
rather than by running a release.
"""

from __future__ import annotations

import importlib.util
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
SCRIPT = REPO_ROOT / ".github" / "scripts" / "rust" / "version-bump.py"


def _load_script():
    """Import the script by path; its filename is not a valid module name."""
    spec = importlib.util.spec_from_file_location("version_bump", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


version_bump = _load_script()


CARGO = """\
[workspace]
members = ["crates/termproof"]

[workspace.package]
version = "0.3.3"
edition = "2021"

[workspace.dependencies]
termproof = { path = "crates/termproof", version = "0.3.3" }
regex = { version = "1.13.1", default-features = false }
"""

PYPROJECT = """\
[project]
name = "termproof"
version = "0.3.3"
dependencies = [
  "jsonschema>=4.0",
]

[tool.hatch.build.targets.wheel]
packages = ["termproof"]
"""

CHANGELOG = """\
# Changelog

## [Unreleased]

Nothing yet.

## [0.3.3] — 2026-08-16

### Python — Added

- something
"""


class CargoRewriteTest(unittest.TestCase):
    def test_both_version_sites_move_together(self) -> None:
        out, edits = version_bump.rewrite(CARGO, "0.3.3", "0.3.4")
        self.assertEqual(2, len(edits), edits)
        self.assertIn('version = "0.3.4"\nedition', out)
        self.assertIn('termproof = { path = "crates/termproof", version = "0.3.4" }', out)

    def test_a_third_party_pin_is_left_alone(self) -> None:
        out, _ = version_bump.rewrite(CARGO, "0.3.3", "0.3.4")
        self.assertIn('regex = { version = "1.13.1"', out)


class PyprojectRewriteTest(unittest.TestCase):
    def test_project_version_moves(self) -> None:
        out, edits = version_bump.rewrite_pyproject(PYPROJECT, "0.3.3", "0.3.4")
        self.assertEqual(1, len(edits), edits)
        self.assertIn('version = "0.3.4"', out)
        self.assertNotIn('version = "0.3.3"', out)

    def test_only_the_project_section_is_touched(self) -> None:
        """A `version` under `[tool.*]` is not the package's version."""
        text = PYPROJECT + '\n[tool.something]\nversion = "0.3.3"\n'
        out, edits = version_bump.rewrite_pyproject(text, "0.3.3", "0.3.4")
        self.assertEqual(1, len(edits), edits)
        self.assertIn('[tool.something]\nversion = "0.3.3"', out)

    def test_a_dependency_specifier_is_not_a_version_key(self) -> None:
        out, _ = version_bump.rewrite_pyproject(PYPROJECT, "0.3.3", "0.3.4")
        self.assertIn('"jsonschema>=4.0"', out)

    def test_reading_the_version_back_from_the_real_manifest(self) -> None:
        self.assertRegex(
            version_bump.read_pyproject_version(ROOT / "pyproject.toml"),
            r"^\d+\.\d+\.\d+$",
        )


class ChangelogPromotionTest(unittest.TestCase):
    def test_unreleased_becomes_the_release_heading(self) -> None:
        out, edits = version_bump.promote_changelog(CHANGELOG, "0.3.4", "2026-09-01")
        self.assertEqual(1, len(edits), edits)
        self.assertIn("## [0.3.4] — 2026-09-01", out)

    def test_a_fresh_unreleased_section_is_left_for_the_next_change(self) -> None:
        out, _ = version_bump.promote_changelog(CHANGELOG, "0.3.4", "2026-09-01")
        self.assertEqual(1, out.count("## [Unreleased]"))
        self.assertLess(out.index("## [Unreleased]"), out.index("## [0.3.4]"))

    def test_the_pending_entries_are_carried_into_the_release(self) -> None:
        """Promotion, not generation: what contributors wrote is the entry."""
        pending = CHANGELOG.replace("Nothing yet.", "### Rust — Fixed\n\n- a real fix")
        out, _ = version_bump.promote_changelog(pending, "0.3.4", "2026-09-01")
        released = out.split("## [0.3.4]")[1].split("## [0.3.3]")[0]
        self.assertIn("- a real fix", released)

    def test_promoting_twice_is_a_no_op(self) -> None:
        once, _ = version_bump.promote_changelog(CHANGELOG, "0.3.4", "2026-09-01")
        twice, edits = version_bump.promote_changelog(once, "0.3.4", "2026-09-01")
        self.assertEqual([], edits)
        self.assertEqual(once, twice)

    def test_a_missing_unreleased_section_is_an_error_not_a_silent_skip(self) -> None:
        with self.assertRaises(ValueError):
            version_bump.promote_changelog("# Changelog\n\n## [0.3.3] — x\n", "0.3.4", "d")

    def test_the_real_changelog_can_be_promoted(self) -> None:
        """The shipped file must be in a shape the release automation accepts."""
        text = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        out, edits = version_bump.promote_changelog(text, "9.9.9", "2026-01-01")
        self.assertEqual(1, len(edits), edits)
        self.assertIn("## [9.9.9] — 2026-01-01", out)


class DryRunAgainstTheRealTreeTest(unittest.TestCase):
    """`--check` over the working tree must name all four sites and write nothing."""

    def test_check_reports_every_site_and_changes_nothing(self) -> None:
        before = {
            path: path.read_bytes()
            for path in (
                REPO_ROOT / "rust" / "Cargo.toml",
                ROOT / "pyproject.toml",
                REPO_ROOT / "CHANGELOG.md",
            )
        }
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "9.9.9", "--check", "--date", "2026-01-01"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            timeout=300,
        )
        self.assertEqual(0, proc.returncode, proc.stdout + proc.stderr)
        self.assertIn("[workspace.package] version -> 9.9.9", proc.stdout)
        self.assertIn("[project] version -> 9.9.9", proc.stdout)
        self.assertIn("CHANGELOG.md: [Unreleased] -> [9.9.9]", proc.stdout)
        self.assertIn("no files written", proc.stdout)
        for path, content in before.items():
            self.assertEqual(content, path.read_bytes(), f"{path} was modified by --check")


class ReleaseWorkflowVerifiesTheTrainTest(unittest.TestCase):
    """Bumping is not enough; the release must refuse to tag a split train.

    The bump and the check are two different failure modes. A bump that silently
    edits nothing leaves the train split just as surely as no bump at all, so
    the workflow runs `check_version.py` after the bump and before the tag.
    """

    WORKFLOW = REPO_ROOT / ".github" / "workflows" / "rust-auto-release.yml"

    def setUp(self) -> None:
        self.text = self.WORKFLOW.read_text(encoding="utf-8")

    def test_the_release_job_checks_the_train_before_tagging(self) -> None:
        self.assertIn("python/scripts/check_version.py", self.text)
        check_at = self.text.index("python/scripts/check_version.py")
        tag_at = self.text.index("git tag -a")
        self.assertLess(
            check_at, tag_at,
            "the version-train check must run before the tag is created",
        )

    def test_the_bump_runs_before_the_check(self) -> None:
        bump_at = self.text.index("version-bump.py")
        check_at = self.text.index("python/scripts/check_version.py")
        self.assertLess(bump_at, check_at)

    def test_a_first_release_is_refused_unless_forced(self) -> None:
        """No `rs-v*` tag exists, so an unguarded scheduled run would cut a
        duplicate `rs-v0.3.3` with whole-history notes. The guard names the
        baseline tag to create instead."""
        self.assertIn("rs-baseline-v", self.text)
        guard = re.search(
            r"name: Refuse an accidental first release.*?\n\n", self.text, re.DOTALL
        )
        self.assertIsNotNone(guard, "no first-release guard step in the workflow")
        self.assertIn("first_release == 'true'", guard.group(0))
        self.assertIn("inputs.force", guard.group(0))


if __name__ == "__main__":
    unittest.main()
