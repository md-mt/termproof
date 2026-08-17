from __future__ import annotations

import json
import re
import shlex
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
DOCS = ROOT / "docs" / "releases.md"
WORKFLOW = REPO_ROOT / ".github" / "workflows" / "python-release.yml"
RECEIPT = ROOT / "docs" / "ci" / "evidence-receipt.json"


def _documented_release_command() -> list[str]:
    """Parse the `termproof run` invocation from the Local Release Check block."""
    text = DOCS.read_text(encoding="utf-8")
    block = text.split("## Local Release Check", 1)[1].split("```", 2)[1]
    for line in block.replace("\\\n", " ").splitlines():
        if "termproof run" in line:
            return shlex.split(line)
    raise AssertionError("no `termproof run` command in the Local Release Check block")


class DocumentedTagFormatTest(unittest.TestCase):
    """The tag format the docs prescribe must be the one the workflows accept.

    The consolidation prefixed the two release paths — `py-v*` for the Python
    package, `rs-v*` for the Rust workspace — and both release documents went
    on telling maintainers to push an unprefixed `v<version>`. A tag in that
    form triggers nothing: `python-release.yml` and `rust-release.yml` filter
    on the prefixes and `rust-publish-crates.yml` refuses a release whose tag
    does not start `rs-v`. Nothing connected the prose to the filters, so the
    drift was invisible until someone cut a release.

    Unprefixed tags still appear in both documents as history. What this test
    forbids is an *instruction* to use one.
    """

    PY_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "python-release.yml"
    RS_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "rust-release.yml"
    PUBLISH_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "rust-publish-crates.yml"
    PY_DOCS = ROOT / "docs" / "releases.md"
    RS_DOCS = REPO_ROOT / "rust" / "docs" / "publishing.md"

    #: A `v0.3.4` or `v<version>` that is not preceded by `py-` or `rs-`, on a
    #: line that reads as an instruction rather than as history.
    UNPREFIXED_TAG = re.compile(r"(?<![-\w])v(?:\d+\.\d+\.\d+|<version>)")
    INSTRUCTION = re.compile(
        r"\b(push|create|tag is|tag such as|use)\b", re.IGNORECASE
    )

    def _push_tag_filters(self, path: Path) -> list[str]:
        workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
        return workflow[True]["push"]["tags"]

    def test_the_two_release_workflows_filter_on_distinct_prefixes(self) -> None:
        self.assertEqual(["py-v*.*.*"], self._push_tag_filters(self.PY_WORKFLOW))
        self.assertEqual(["rs-v*.*.*"], self._push_tag_filters(self.RS_WORKFLOW))

    def test_the_crates_publish_guard_matches_the_rust_prefix(self) -> None:
        text = self.PUBLISH_WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("startsWith(github.event.release.tag_name, 'rs-v')", text)
        self.assertIn('"rs-v$VERSION"', text)

    def test_the_docs_prescribe_the_prefix_the_workflow_accepts(self) -> None:
        self.assertIn("py-v<version>", self.PY_DOCS.read_text(encoding="utf-8"))
        self.assertIn("rs-v<version>", self.RS_DOCS.read_text(encoding="utf-8"))

    def test_no_release_document_instructs_an_unprefixed_tag(self) -> None:
        offenders = []
        for path in (self.PY_DOCS, self.RS_DOCS):
            for lineno, line in enumerate(
                path.read_text(encoding="utf-8").splitlines(), start=1
            ):
                if not self.UNPREFIXED_TAG.search(line):
                    continue
                if not self.INSTRUCTION.search(line):
                    continue
                # "not `v0.3.4`", "must not be used", "predate", "history" —
                # naming the wrong form in order to rule it out is the point.
                if re.search(r"\bnot\b|history|predate|obsolete", line, re.I):
                    continue
                offenders.append(
                    f"{path.relative_to(REPO_ROOT).as_posix()}:{lineno}: {line.strip()}"
                )
        self.assertEqual(
            [],
            offenders,
            "release docs must prescribe `py-v*` / `rs-v*`; an unprefixed tag "
            "triggers no workflow:\n" + "\n".join(offenders),
        )


class SharedVersionTrainTest(unittest.TestCase):
    """The two implementations share one version train.

    That is a claim the root README, the changelog and SECURITY.md all make. It
    is only true while the two manifests agree, and nothing enforced it: the
    Rust workspace is bumped by its own auto-release workflow and the Python
    package by hand, from two different places. `check_version.py` compares
    them; this is the test that the comparison is wired up and currently holds.
    """

    def _pyproject_version(self) -> str:
        text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        return re.search(r'^version\s*=\s*"([^"]+)"', text, re.M).group(1)

    def _cargo_version(self) -> str:
        text = (REPO_ROOT / "rust" / "Cargo.toml").read_text(encoding="utf-8")
        section = text.split("[workspace.package]", 1)[1]
        return re.search(r'^version\s*=\s*"([^"]+)"', section, re.M).group(1)

    def test_the_two_manifests_agree(self) -> None:
        self.assertEqual(
            self._pyproject_version(),
            self._cargo_version(),
            "pyproject.toml and rust/Cargo.toml disagree; the shared version "
            "train is a claim in README.md, CHANGELOG.md and SECURITY.md",
        )

    def test_the_changelog_has_one_entry_for_that_version(self) -> None:
        version = self._pyproject_version()
        changelog = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        headings = [
            line for line in changelog.splitlines()
            if line.startswith(f"## [{version}]")
        ]
        self.assertEqual(
            1, len(headings),
            f"CHANGELOG.md must have exactly one heading for {version}, "
            f"found {len(headings)}",
        )

    def test_check_version_script_reads_both_manifests(self) -> None:
        source = (ROOT / "scripts" / "check_version.py").read_text(encoding="utf-8")
        self.assertIn('"rust" / "Cargo.toml"', source)
        self.assertIn("[workspace.package]", source)


class ReleaseDocsTest(unittest.TestCase):
    def test_local_release_check_matches_release_receipt(self) -> None:
        argv = _documented_release_command()
        release = json.loads(RECEIPT.read_text(encoding="utf-8"))["targets"]["release"]

        self.assertEqual("run", argv[argv.index("termproof") + 1])
        recipes = argv[argv.index("termproof") + 2 :]
        flags = recipes[next(i for i, arg in enumerate(recipes) if arg.startswith("-")) :]
        recipes = recipes[: len(recipes) - len(flags)]

        self.assertEqual(release["recipes"], recipes)
        self.assertEqual(release["video"], "--video" in flags)
        self.assertEqual(str(release["video_fps"]), flags[flags.index("--video-fps") + 1])
        self.assertEqual(release["out"], flags[flags.index("--out") + 1])

    def test_pypi_trusted_publisher_values_are_documented(self) -> None:
        text = DOCS.read_text(encoding="utf-8")

        self.assertIn("Owner: `md-mt`", text)
        self.assertIn("Repository: `termproof`", text)
        self.assertIn("Workflow: `python-release.yml`", text)
        self.assertIn("Environment: `pypi`", text)
        self.assertIn("ENABLE_PYPI", text)
        self.assertIn("invalid-publisher", text)
        self.assertIn("smoke-install.sh", text)

    def test_release_workflow_retains_trusted_publisher_claims(self) -> None:
        workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
        release = workflow["jobs"]["release"]
        # `id-token: write` is PyPI trusted publishing and `contents: write`
        # creates the GitHub release. Both sit on the job rather than the
        # workflow, matching Release (Rust); the workflow default is read.
        self.assertEqual("read", workflow["permissions"]["contents"])
        self.assertEqual("write", release["permissions"]["id-token"])
        self.assertEqual("write", release["permissions"]["contents"])
        self.assertEqual("pypi", release["environment"])

    def test_smoke_install_script_exists_and_is_executable(self) -> None:
        script = ROOT / "scripts" / "smoke-install.sh"
        self.assertTrue(script.exists(), f"missing {script}")
        self.assertTrue(bool(script.stat().st_mode & 0o111), "smoke-install.sh must be executable")
        text = script.read_text(encoding="utf-8")
        self.assertIn("termproof --help", text)
        self.assertIn("import termproof", text)

    def test_pypi_publish_is_opt_in(self) -> None:
        workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
        steps = workflow["jobs"]["release"]["steps"]

        publish_step = next(step for step in steps if step["name"] == "Publish to PyPI")
        self.assertEqual(
            "startsWith(github.ref, 'refs/tags/py-v') && vars.ENABLE_PYPI == 'true'",
            publish_step["if"],
        )
        self.assertEqual("pypa/gh-action-pypi-publish@release/v1", publish_step["uses"])

        skip_step = next(step for step in steps if step["name"] == "Note skipped PyPI publish")
        self.assertEqual(
            "startsWith(github.ref, 'refs/tags/py-v') && vars.ENABLE_PYPI != 'true'",
            skip_step["if"],
        )
        self.assertIn("ENABLE_PYPI", skip_step["run"])


if __name__ == "__main__":
    unittest.main()
