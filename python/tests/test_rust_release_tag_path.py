"""Pushing an `rs-v*` tag by hand must produce a whole release.

The 0.4.1 release is the case this file exists for. The tag was pushed by hand;
`rust-release.yml` built the binaries and then waited for a GitHub release that
nothing on the tag-push path was going to create, and failed. That failure read
as an attachment problem. It was not one: `rust-publish-crates.yml` triggers on
a *published release* and nothing else, so crates.io received nothing at all,
and the only signal was one red job among several green ones.

Two properties come out of that, and both are asserted here rather than left to
prose in a workflow header:

1. The tag-push path creates its own release when none exists, the way
   `python-release.yml` already did — and is a no-op when the weekly automation
   has already created one, so there is never a second release.
2. The path ends by asking crates.io whether the crates actually shipped. Every
   job being green is not evidence of that, which is the whole lesson of 0.4.1.

The script behaviour is exercised against a local file:// index rather than
crates.io, so these tests are offline and do not depend on what is published.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
WORKFLOWS = REPO_ROOT / ".github" / "workflows"
RELEASE = WORKFLOWS / "rust-release.yml"
PUBLISH = WORKFLOWS / "rust-publish-crates.yml"
SCRIPTS = REPO_ROOT / ".github" / "scripts" / "rust"
VERIFY = SCRIPTS / "verify-published.sh"
DECIDE = SCRIPTS / "release-decide.py"

requires_cargo = unittest.skipUnless(shutil.which("cargo"), "cargo is not installed")
requires_curl = unittest.skipUnless(shutil.which("curl"), "curl is not installed")
requires_jq = unittest.skipUnless(shutil.which("jq"), "jq is not installed")


def _workflow(path: Path) -> dict:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def _steps(workflow: dict, job: str) -> list[dict]:
    return workflow["jobs"][job]["steps"]


def _step(workflow: dict, job: str, name: str) -> dict:
    for step in _steps(workflow, job):
        if step.get("name") == name:
            return step
    raise AssertionError(f"{job} has no step named {name!r}")


def _crate_names() -> list[str]:
    return sorted(p.name for p in (REPO_ROOT / "rust" / "crates").iterdir() if p.is_dir())


class TagPushCreatesItsOwnReleaseTest(unittest.TestCase):
    """The gap 0.4.1 fell into: a tag with no release, and no way to get one."""

    def setUp(self) -> None:
        self.workflow = _workflow(RELEASE)

    def test_the_wait_records_the_answer_instead_of_failing_on_it(self) -> None:
        """A missing release is now a branch, not the end of the job.

        The old wait ended in `exit 1`, which is what turned a whole missed
        release into something that looked like a failed upload.
        """
        wait = _step(self.workflow, "attach", "Wait for the release to exist")
        self.assertEqual("wait", wait["id"])
        self.assertIn("exists=true", wait["run"])
        self.assertIn("exists=false", wait["run"])
        self.assertNotIn("exit 1", wait["run"])

    def test_the_release_is_created_only_when_the_wait_found_none(self) -> None:
        """This is what stops the weekly path producing two releases.

        The wait is ten checks over 150 seconds. The automation creates its
        release seconds after pushing the tag and this job is minutes behind
        it, so on that path the first check finds it and this step never runs.
        """
        create = _step(self.workflow, "attach", "Create the release the tag push did not")
        self.assertEqual("steps.wait.outputs.exists != 'true'", create["if"])

        names = [step.get("name") for step in _steps(self.workflow, "attach")]
        self.assertLess(
            names.index("Wait for the release to exist"),
            names.index("Create the release the tag push did not"),
            "creating before waiting would race the weekly automation into two releases",
        )

    def test_creating_the_release_uses_a_token_that_can_trigger_the_publish(self) -> None:
        """`GITHUB_TOKEN` here would be worse than failing.

        A release created with the default token does not start
        rust-publish-crates.yml, and that workflow uploads on
        `release: published` and nothing else — so no re-run could recover it.
        A missing secret has to fail the job instead.
        """
        create = _step(self.workflow, "attach", "Create the release the tag push did not")
        self.assertEqual("${{ secrets.RELEASE_TOKEN }}", create["env"]["GH_TOKEN"])
        self.assertEqual("${{ secrets.RELEASE_TOKEN }}", create["env"]["RELEASE_TOKEN"])
        self.assertIn('if [ -z "$RELEASE_TOKEN" ]; then', create["run"])
        self.assertIn("::error::the RELEASE_TOKEN secret is not set", create["run"])

    def test_the_tag_is_checked_against_the_manifest_before_a_release_exists(self) -> None:
        """A release publish-crates.yml would refuse is worse than no release."""
        create = _step(self.workflow, "attach", "Create the release the tag push did not")
        self.assertIn("publish-plan.py | jq -r .version", create["run"])
        self.assertIn('if [ "$TAG" != "rs-v$VERSION" ]; then', create["run"])
        self.assertLess(
            create["run"].index('"rs-v$VERSION"'),
            create["run"].index("gh release create"),
            "the guard has to run before the release exists, not after",
        )

    def test_the_notes_come_from_the_same_renderer_the_weekly_path_uses(self) -> None:
        """An empty body would be a regression against the automated path."""
        create = _step(self.workflow, "attach", "Create the release the tag push did not")
        self.assertIn('release-decide.py --at "$VERSION"', create["run"])
        self.assertIn("--notes-file release-notes.md", create["run"])
        self.assertIn("--verify-tag", create["run"])

    def test_the_attach_job_checks_out_deeply_enough_to_render_notes(self) -> None:
        checkout = next(
            step
            for step in _steps(self.workflow, "attach")
            if str(step.get("uses", "")).startswith("actions/checkout@")
        )
        self.assertEqual(0, checkout["with"]["fetch-depth"])


class CratesPublishStaysTheOneGateTest(unittest.TestCase):
    """The fix must not buy self-sufficiency by widening the publish trigger.

    A published release being the only thing that uploads is what makes the
    `crates-io` environment approval hook possible, and it is what the publish
    workflow's header claims about the whole repository.
    """

    def setUp(self) -> None:
        self.publish = _workflow(PUBLISH)

    def test_the_publish_still_triggers_only_on_a_published_release(self) -> None:
        self.assertEqual({"types": ["published"]}, self.publish[True]["release"])
        self.assertNotIn("push", self.publish[True])
        self.assertEqual(
            "github.event_name == 'release' && "
            "startsWith(github.event.release.tag_name, 'rs-v')",
            self.publish["jobs"]["publish"]["if"],
        )
        self.assertEqual("crates-io", self.publish["jobs"]["publish"]["environment"])

    def test_nothing_in_the_release_workflow_uploads_to_a_registry(self) -> None:
        text = RELEASE.read_text(encoding="utf-8")
        self.assertNotIn("cargo publish", text)
        self.assertNotIn("CARGO_REGISTRY_TOKEN", text)


class TheReleasePathEndsByAskingTheRegistryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.workflow = _workflow(RELEASE)
        self.job = self.workflow["jobs"]["verify-crates"]

    def test_it_runs_last_on_the_tag_path(self) -> None:
        self.assertEqual("attach", self.job["needs"])
        self.assertEqual("startsWith(github.ref, 'refs/tags/rs-v')", self.job["if"])

    def test_the_crate_set_is_derived_and_never_written_down(self) -> None:
        step = _step(self.workflow, "verify-crates", "Every crate the plan names is on crates.io")
        self.assertIn("publish-plan.py", step["run"])
        self.assertIn("verify-published.sh", step["run"])
        self.assertIn("export ORDER VERSION", step["run"])
        self.assertIn("ORDER=\"$(jq -r '.order | join(\" \")' <<<\"$PLAN\")\"", step["run"])

    def test_the_verifier_names_no_crate(self) -> None:
        text = VERIFY.read_text(encoding="utf-8")
        named = [name for name in _crate_names() if name in text]
        self.assertEqual(
            [],
            named,
            "the publish set is a manifest decision; a name written into the "
            "verifier is a name that goes stale the first time it changes",
        )

    def test_the_verifier_is_executable(self) -> None:
        self.assertTrue(bool(VERIFY.stat().st_mode & 0o111), f"{VERIFY} must be executable")


@requires_curl
class VerifyPublishedScriptTest(unittest.TestCase):
    """Run the real script against a local sparse index laid out on disk.

    `curl` reads `file://` the same way it reads `https://`, so the sharding,
    the version match and the polling are all exercised without a network and
    without depending on what happens to be published.
    """

    VERSION = "9.9.9"

    def _index(self, entries: dict[str, list[str]]) -> str:
        root = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, root, True)
        for name, versions in entries.items():
            # The layout crates.io uses, and the one the script computes.
            shard = root / name[:2] / name[2:4]
            shard.mkdir(parents=True, exist_ok=True)
            shard.joinpath(name).write_text(
                "".join(json.dumps({"name": name, "vers": v}) + "\n" for v in versions),
                encoding="utf-8",
            )
        return root.as_uri()

    def _run(self, order: str, index: str, version: str | None = None):
        return subprocess.run(
            [str(VERIFY)],
            capture_output=True,
            text=True,
            env={
                "PATH": os.environ["PATH"],
                "ORDER": order,
                "VERSION": version or self.VERSION,
                "INDEX": index,
                "ATTEMPTS": "2",
                "INTERVAL": "0",
            },
        )

    def test_it_passes_when_every_crate_is_on_the_index(self) -> None:
        index = self._index({"alpha-crate": ["9.9.8", self.VERSION], "beta-crate": [self.VERSION]})
        result = self._run("alpha-crate beta-crate", index)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("every planned crate is on crates.io", result.stdout)

    def test_it_fails_naming_only_what_did_not_ship(self) -> None:
        """The point of the check: say which crate is missing, not that one is."""
        index = self._index({"alpha-crate": [self.VERSION], "beta-crate": ["9.9.8"]})
        result = self._run("alpha-crate beta-crate", index)
        self.assertEqual(1, result.returncode)
        self.assertIn("::error::", result.stdout)
        error = [line for line in result.stdout.splitlines() if line.startswith("::error::")][0]
        self.assertIn("beta-crate", error)
        self.assertNotIn("alpha-crate", error)

    def test_a_crate_absent_from_the_index_entirely_is_missing(self) -> None:
        """A 404 and a wrong version are the same answer to the same question."""
        result = self._run("alpha-crate", self._index({}))
        self.assertEqual(1, result.returncode)
        self.assertIn("alpha-crate", result.stdout)

    def test_it_polls_rather_than_looking_once(self) -> None:
        """The publish runs its own gate first, so it lands minutes later."""
        result = self._run("alpha-crate", self._index({}))
        waits = [line for line in result.stdout.splitlines() if line.startswith("waiting for")]
        self.assertEqual(2, len(waits), result.stdout)

    def test_an_empty_publish_set_is_not_a_failure(self) -> None:
        """Every member held back is a manifest decision, not a missed upload."""
        result = self._run("", self._index({}))
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("::notice::", result.stdout)


@requires_cargo
class ReleaseNotesForATagThatAlreadyExistsTest(unittest.TestCase):
    """`--at` is what lets the tag path reuse the weekly path's renderer.

    Without it the script derives the *next* version from the commit range, so
    notes for a tag that already exists would be headed one release too far
    ahead — and the compare link would point at a tag nobody cut.
    """

    def _decide(self, *args: str) -> dict:
        result = subprocess.run(
            [str(DECIDE), *args],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        return json.loads(result.stdout)

    def test_the_pinned_version_is_the_one_the_notes_carry(self) -> None:
        decided = self._decide("--at", "9.9.9", "--no-auto-base", "--to", "HEAD")
        self.assertTrue(decided["release"])
        self.assertEqual("9.9.9", decided["next_version"])
        self.assertEqual("rs-v9.9.9", decided["tag"])
        self.assertEqual("none", decided["bump"])
        self.assertTrue(decided["notes"].startswith("## termproof 9.9.9\n"))

    def test_the_notes_are_not_empty(self) -> None:
        """The stated bar for this path: no worse than the weekly one."""
        notes = self._decide("--at", "9.9.9", "--no-auto-base", "--to", "HEAD")["notes"]
        self.assertIn("### ", notes)
        self.assertIn("Binaries for", notes)

    def test_deciding_mode_still_derives_a_bump(self) -> None:
        """`--at` must not have leaked into the path the weekly release takes."""
        decided = self._decide("--no-auto-base", "--to", "HEAD")
        self.assertNotIn("describing", decided["reason"])


@requires_cargo
@requires_jq
class CreateStepShellTest(unittest.TestCase):
    """Run the create step's own shell, with `gh` stubbed out.

    Everything else in this file reads the workflow. This runs it: the step's
    `run:` block is lifted out of the YAML and executed against a fake `gh`
    that records its arguments, so the branch that was missing when 0.4.1 was
    cut is exercised without a tag, a release or a registry anywhere near it.

    The tag is derived from the manifest rather than written down, so this
    tests the guard rather than a version.
    """

    #: Written by the step into the working directory, the way CI does.
    ARTIFACTS = ("decision.json", "release-notes.md")

    STUB = """\
#!/usr/bin/env bash
echo "gh $*" >> "{log}"
case "$1 $2" in
  "release create") exit {create_rc} ;;
  "release view") exit {view_rc} ;;
esac
exit 0
"""

    def setUp(self) -> None:
        for name in self.ARTIFACTS:
            path = REPO_ROOT / name
            if path.exists():
                self.skipTest(f"{name} already exists in the working tree")
            self.addCleanup(path.unlink, True)

        workflow = _workflow(RELEASE)
        step = _step(workflow, "attach", "Create the release the tag push did not")
        self.body = (
            step["run"]
            .replace("${{ github.server_url }}", "https://github.com")
            .replace("${{ github.repository }}", "md-mt/termproof")
        )
        plan = subprocess.run(
            [str(SCRIPTS / "publish-plan.py")],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            check=True,
        )
        self.version = json.loads(plan.stdout)["version"]

    def _run(self, tag: str, token: str = "stub-token", create_rc: int = 0, view_rc: int = 1):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp, True)
        log = tmp / "gh.log"
        stub = tmp / "gh"
        stub.write_text(
            self.STUB.format(log=log, create_rc=create_rc, view_rc=view_rc), encoding="utf-8"
        )
        stub.chmod(0o755)
        summary = tmp / "summary.md"
        summary.write_text("", encoding="utf-8")
        script = tmp / "step.sh"
        script.write_text(self.body, encoding="utf-8")

        # `bash -e` is what GitHub runs a `run:` block under.
        result = subprocess.run(
            ["bash", "-e", str(script)],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            env={
                **os.environ,
                "PATH": f"{tmp}{os.pathsep}{os.environ['PATH']}",
                "TAG": tag,
                "RELEASE_TOKEN": token,
                "GH_TOKEN": token,
                "GH_REPO": "md-mt/termproof",
                "GITHUB_REPOSITORY": "md-mt/termproof",
                "GITHUB_STEP_SUMMARY": str(summary),
            },
        )
        return result, (log.read_text(encoding="utf-8") if log.exists() else "")

    def test_it_creates_the_release_from_the_tag_alone(self) -> None:
        result, log = self._run(f"rs-v{self.version}")
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn(
            f"gh release create rs-v{self.version} --title rs-v{self.version} "
            "--notes-file release-notes.md --verify-tag",
            log,
        )

    def test_the_notes_it_writes_are_the_rendered_ones(self) -> None:
        result, _ = self._run(f"rs-v{self.version}")
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        notes = (REPO_ROOT / "release-notes.md").read_text(encoding="utf-8")
        self.assertTrue(notes.startswith(f"## termproof {self.version}\n"), notes[:80])
        self.assertIn("Binaries for", notes)

    def test_no_token_means_no_release(self) -> None:
        """Better a tag with no release than a release that can never publish."""
        result, log = self._run(f"rs-v{self.version}", token="")
        self.assertEqual(1, result.returncode)
        self.assertIn("::error::the RELEASE_TOKEN secret is not set", result.stdout)
        self.assertEqual("", log, "nothing may be created without a usable token")

    def test_a_tag_the_publish_would_refuse_creates_nothing(self) -> None:
        result, log = self._run("rs-v9.9.9")
        self.assertEqual(1, result.returncode)
        self.assertIn("does not match the workspace version", result.stdout)
        self.assertEqual("", log)

    def test_losing_a_race_to_create_is_not_a_failure(self) -> None:
        result, log = self._run(f"rs-v{self.version}", create_rc=1, view_rc=0)
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("::notice::", result.stdout)
        self.assertIn("release view", log)

    def test_a_create_that_really_failed_still_fails(self) -> None:
        result, _ = self._run(f"rs-v{self.version}", create_rc=1, view_rc=1)
        self.assertEqual(1, result.returncode)


if __name__ == "__main__":
    unittest.main()
