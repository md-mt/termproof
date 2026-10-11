"""The canonical oracle gate and its re-recording workflow stay one environment.

Issue #172: the recorded expectations in `conformance/corpus/` encode
behaviour owned partly by the machine that observed it, so the recording
environment is pinned — the `ubuntu-24.04` runner, CPython 3.13.5 (the
exact patch the recorded `environment` blocks name), a pinned uv, and
`python/uv.lock` — and stated in `conformance/README.md`. Two workflow
surfaces carry that pin: the `oracle` job in the always-on
`oracle-ci.yml`, whose `Oracle freshness result` rollup fails the check
when the corpus does not reproduce under `--strict-environment` (it
becomes a required check only after the bootstrap re-record is green;
`rust/docs/governance.md` §5), and the manual `oracle-regen.yml`, which
is the only way expectations are re-recorded.

The gate lives in its own workflow rather than the path-filtered
`python-ci.yml` for the `CI (Rust)` reason (#226): a filtered-out
workflow reports no check at all, so nothing it contains can ever be
required. Here a `changes` job decides whether an oracle-relevant path
moved and the rollup reports either way.

The pin is only worth having if the two surfaces cannot drift apart or
quietly soften — a gate that gained `continue-on-error`, or a regen
workflow that floated to `ubuntu-latest`, would keep every other check
green while the corpus stopped meaning what it claims. That is what
this asserts. The probe-to-expectation list is read from
`verify_oracle.PROBES` rather than repeated, so a new probe that the
regen workflow forgets fails here.
"""

from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path
from types import ModuleType

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = REPO_ROOT / ".github" / "workflows"
CHECKER = REPO_ROOT / "conformance" / "verify_oracle.py"

CANONICAL_RUNNER = "ubuntu-24.04"
CANONICAL_PYTHON = "3.13.5"
CANONICAL_UV_VERSION = "0.11.8"

# The paths whose movement can change what the probes record, as git
# pathspecs in the `changes` job's diff.
ORACLE_PATHSPECS = (
    "python",
    "spec",
    "conformance",
    ".github/workflows/oracle-ci.yml",
    ".github/workflows/oracle-regen.yml",
)


def _load_checker() -> ModuleType:
    spec = importlib.util.spec_from_file_location("verify_oracle", CHECKER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


verify = _load_checker()


def _workflow(name: str) -> dict:
    return yaml.safe_load((WORKFLOWS / name).read_text(encoding="utf-8"))


def _canonical_pair(job: dict) -> tuple[str, str]:
    """The (runner, interpreter) a job pins, as GitHub would read them."""
    python = next(
        step["with"]["python-version"]
        for step in job["steps"]
        if str(step.get("uses", "")).startswith("actions/setup-python@")
    )
    return job["runs-on"], str(python)


def _uv_pin(job: dict) -> tuple[str, str]:
    """The (setup-uv ref, uv version) a job pins."""
    step = next(
        step
        for step in job["steps"]
        if str(step.get("uses", "")).startswith("astral-sh/setup-uv@")
    )
    return str(step["uses"]), str(step["with"]["version"])


def _diff_pathspecs(run: str, flag: str) -> list[str]:
    """The pathspecs after `--` in the `git diff <flag> ...` command."""
    logical = run.replace("\\\n", " ")
    line = next(
        line for line in logical.splitlines() if f"git diff {flag}" in line
    )
    _, _, pathspecs = line.partition(" -- ")
    result: list[str] = []
    for token in pathspecs.split():
        if token in {"||", ";;"} or token.startswith("status="):
            break
        result.append(token.removesuffix(";;"))
        if token.endswith(";;"):
            break
    return result


class OracleGateWorkflowTest(unittest.TestCase):
    def setUp(self) -> None:
        self.workflow = _workflow("oracle-ci.yml")
        self.job = self.workflow["jobs"]["oracle"]

    def test_the_gate_no_longer_lives_in_the_path_filtered_workflow(self) -> None:
        self.assertNotIn("oracle", _workflow("python-ci.yml")["jobs"])

    def test_the_workflow_is_always_on_with_no_path_filter(self) -> None:
        # PyYAML reads the `on:` key as the boolean True (YAML 1.1).
        triggers = self.workflow[True]
        self.assertEqual(
            {
                "pull_request": None,
                "push": {"branches": ["main"]},
                "workflow_dispatch": None,
            },
            triggers,
        )
        self.assertEqual("read", self.workflow["permissions"]["contents"])

    def test_changes_diffs_exactly_the_oracle_inputs(self) -> None:
        changes = self.workflow["jobs"]["changes"]
        self.assertEqual(
            "${{ steps.diff.outputs.oracle }}", changes["outputs"]["oracle"]
        )
        step = next(
            step
            for step in changes["steps"]
            if "git diff --quiet" in str(step.get("run", ""))
        )
        # Target the --quiet diff specifically: it is the one whose exit
        # status decides, so a pathspec surviving only in the --name-only
        # echo must not satisfy this. The echo must agree exactly too.
        self.assertEqual(
            list(ORACLE_PATHSPECS), _diff_pathspecs(step["run"], "--quiet")
        )
        self.assertEqual(
            list(ORACLE_PATHSPECS),
            _diff_pathspecs(step["run"], "--name-only"),
        )

    def test_the_gate_pins_the_canonical_environment(self) -> None:
        self.assertEqual(
            (CANONICAL_RUNNER, CANONICAL_PYTHON), _canonical_pair(self.job)
        )
        self.assertEqual(
            ("astral-sh/setup-uv@v7", CANONICAL_UV_VERSION), _uv_pin(self.job)
        )

    def test_the_gate_runs_the_strict_check_only_when_relevant(self) -> None:
        self.assertEqual("changes", self.job["needs"])
        self.assertEqual(
            "needs.changes.outputs.oracle == 'true'", self.job["if"]
        )
        step = next(
            step
            for step in self.job["steps"]
            if "verify_oracle.py" in str(step.get("run", ""))
        )
        self.assertIn(
            "python3 conformance/verify_oracle.py --strict-environment",
            step["run"],
        )

    def test_the_gate_cannot_pass_by_being_ignored(self) -> None:
        # The job's only `if:` is the `changes` guard asserted above; no
        # step may add one of its own, and nothing may continue on error.
        self.assertNotIn("continue-on-error", self.job)
        for step in self.job["steps"]:
            self.assertNotIn("continue-on-error", step)
            self.assertNotIn("if", step)
        self.assertIn(
            self.job.get("permissions"), (None, {"contents": "read"})
        )

    def test_the_rollup_always_reports_and_fails_iff_the_gate_fails(
        self,
    ) -> None:
        result = self.workflow["jobs"]["result"]
        self.assertEqual("Oracle freshness result", result["name"])
        self.assertEqual(["changes", "oracle"], result["needs"])
        self.assertEqual("always()", result["if"])
        # Mirror the gate job: the job's only `if:` is the `always()`
        # above, its sole step may not add one of its own, and nothing
        # may continue on error — a rollup that could skip or swallow
        # its only step would report a pass it never decided.
        self.assertNotIn("continue-on-error", result)
        self.assertEqual(1, len(result["steps"]))
        for step in result["steps"]:
            self.assertNotIn("continue-on-error", step)
            self.assertNotIn("if", step)
        step = result["steps"][0]
        self.assertEqual(
            "${{ needs.changes.result }}", step["env"]["CHANGES_RESULT"]
        )
        self.assertEqual(
            "${{ needs.changes.outputs.oracle }}",
            step["env"]["ORACLE_CHANGED"],
        )
        self.assertEqual(
            "${{ needs.oracle.result }}", step["env"]["ORACLE_RESULT"]
        )
        # Mirrors `CI (Rust) result`: a skip passes only on an explicit
        # `oracle=false`, and every other non-success is a failure.
        self.assertIn(
            'if [ "$CHANGES_RESULT" != "success" ]; then', step["run"]
        )
        self.assertIn('case "$ORACLE_RESULT" in', step["run"])
        self.assertIn("success)", step["run"])
        self.assertIn('"$ORACLE_CHANGED" != "false"', step["run"])
        self.assertIn("exit 1", step["run"])


class OracleRegenWorkflowTest(unittest.TestCase):
    def setUp(self) -> None:
        self.workflow = _workflow("oracle-regen.yml")
        self.job = self.workflow["jobs"]["regen"]

    def test_regeneration_is_manual_and_read_only(self) -> None:
        # PyYAML reads the `on:` key as the boolean True (YAML 1.1).
        self.assertEqual({"workflow_dispatch": None}, self.workflow[True])
        self.assertEqual({"contents": "read"}, self.workflow["permissions"])

    def test_regeneration_uses_the_gate_environment(self) -> None:
        gate_job = _workflow("oracle-ci.yml")["jobs"]["oracle"]
        self.assertEqual(_canonical_pair(gate_job), _canonical_pair(self.job))
        self.assertEqual(_uv_pin(gate_job), _uv_pin(self.job))

    def test_regeneration_rerecords_every_probe_expectation(self) -> None:
        step = next(
            step
            for step in self.job["steps"]
            if "probe_steps.py" in str(step.get("run", ""))
        )
        self.assertEqual("python", step["working-directory"])
        for probe, expected in verify.PROBES:
            with self.subTest(probe=probe):
                self.assertIn(
                    "TERMPROOF_PYTHON_REPO=$PWD uv run python", step["run"]
                )
                self.assertIn(f"../conformance/{probe}", step["run"])
                self.assertIn(
                    f"> ../conformance/corpus/{expected}", step["run"]
                )

    def test_the_regenerated_corpus_is_verified_in_the_same_run(
        self,
    ) -> None:
        runs = [str(step.get("run", "")) for step in self.job["steps"]]
        self.assertTrue(
            any(
                "python3 conformance/verify_oracle.py --strict-environment"
                in run
                for run in runs
            ),
            "regen must self-verify the corpus it just recorded",
        )

    def test_the_regenerated_corpus_is_one_artifact_and_never_pushed(
        self,
    ) -> None:
        uploads = [
            step
            for step in self.job["steps"]
            if str(step.get("uses", "")).startswith(
                "actions/upload-artifact@"
            )
        ]
        self.assertEqual(1, len(uploads))
        self.assertEqual("oracle-corpus", uploads[0]["with"]["name"])
        self.assertEqual(
            "conformance/corpus/*.expected.json", uploads[0]["with"]["path"]
        )
        self.assertEqual("error", uploads[0]["with"]["if-no-files-found"])
        runs = "\n".join(str(step.get("run", "")) for step in self.job["steps"])
        self.assertNotIn("git push", runs)
        self.assertNotIn("gh pr ", runs)


if __name__ == "__main__":
    unittest.main()
