"""The canonical oracle gate and its re-recording workflow stay one environment.

Issue #172: the recorded expectations in `conformance/corpus/` encode
behaviour owned partly by the machine that observed it, so the recording
environment is pinned — the `ubuntu-24.04` runner, CPython 3.13, and
`python/uv.lock` — and stated in `conformance/README.md`. Two workflow
surfaces carry that pin: the `oracle` job in `python-ci.yml`, which fails
a pull request when the corpus does not reproduce under
`--strict-environment`, and the manual `oracle-regen.yml`, which is the
only way expectations are re-recorded.

The pin is only worth having if the two cannot drift apart or quietly
soften — a gate that gained `continue-on-error`, or a regen workflow that
floated to `ubuntu-latest`, would keep every other check green while the
corpus stopped meaning what it claims. That is what this asserts. The
probe-to-expectation list is read from `verify_oracle.PROBES` rather than
repeated, so a new probe that the regen workflow forgets fails here.
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
CANONICAL_PYTHON = "3.13"


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


class OracleGateJobTest(unittest.TestCase):
    def setUp(self) -> None:
        self.workflow = _workflow("python-ci.yml")
        self.job = self.workflow["jobs"]["oracle"]

    def test_the_gate_pins_the_canonical_environment(self) -> None:
        self.assertEqual((CANONICAL_RUNNER, CANONICAL_PYTHON), _canonical_pair(self.job))

    def test_the_gate_runs_the_strict_check_from_the_repository_root(self) -> None:
        step = next(
            step
            for step in self.job["steps"]
            if "verify_oracle.py" in str(step.get("run", ""))
        )
        self.assertIn(
            "python3 conformance/verify_oracle.py --strict-environment", step["run"]
        )
        # `python-ci.yml` defaults every `run` step to `python/`; the
        # checker is documented from the root, so the override is part of
        # running the documented command at all.
        self.assertEqual("${{ github.workspace }}", step["working-directory"])

    def test_the_gate_cannot_pass_by_being_ignored(self) -> None:
        self.assertNotIn("continue-on-error", self.job)
        for step in self.job["steps"]:
            self.assertNotIn("continue-on-error", step)
        self.assertIn(self.job.get("permissions"), (None, {"contents": "read"}))
        self.assertEqual("read", self.workflow["permissions"]["contents"])


class OracleRegenWorkflowTest(unittest.TestCase):
    def setUp(self) -> None:
        self.workflow = _workflow("oracle-regen.yml")
        self.job = self.workflow["jobs"]["regen"]

    def test_regeneration_is_manual_and_read_only(self) -> None:
        # PyYAML reads the `on:` key as the boolean True (YAML 1.1).
        self.assertEqual({"workflow_dispatch": None}, self.workflow[True])
        self.assertEqual({"contents": "read"}, self.workflow["permissions"])

    def test_regeneration_uses_the_gate_environment(self) -> None:
        gate_job = _workflow("python-ci.yml")["jobs"]["oracle"]
        self.assertEqual(_canonical_pair(gate_job), _canonical_pair(self.job))

    def test_regeneration_rerecords_every_probe_expectation(self) -> None:
        step = next(
            step for step in self.job["steps"] if "probe_steps.py" in str(step.get("run", ""))
        )
        self.assertEqual("python", step["working-directory"])
        for probe, expected in verify.PROBES:
            with self.subTest(probe=probe):
                self.assertIn("TERMPROOF_PYTHON_REPO=$PWD uv run python", step["run"])
                self.assertIn(f"../conformance/{probe}", step["run"])
                self.assertIn(f"> ../conformance/corpus/{expected}", step["run"])

    def test_the_regenerated_corpus_is_one_artifact_and_never_pushed(self) -> None:
        uploads = [
            step
            for step in self.job["steps"]
            if str(step.get("uses", "")).startswith("actions/upload-artifact@")
        ]
        self.assertEqual(1, len(uploads))
        self.assertEqual("oracle-corpus", uploads[0]["with"]["name"])
        self.assertEqual(
            "conformance/corpus/*.expected.json", uploads[0]["with"]["path"]
        )
        runs = "\n".join(str(step.get("run", "")) for step in self.job["steps"])
        self.assertNotIn("git push", runs)
        self.assertNotIn("gh pr ", runs)


if __name__ == "__main__":
    unittest.main()
