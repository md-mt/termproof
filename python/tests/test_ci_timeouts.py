"""Every CI job is bounded, and every package install inside one is bounded.

Issue #183: a quiet Ubuntu mirror stalled `apt-get install ffmpeg` in three
jobs of one run. Nothing carried a ``timeout-minutes``, so all three ran to
GitHub's six-hour ceiling — 18 job-hours from one commit — and surfaced as
`cancelled` with no test output, which reads as a broken pull request rather
than as infrastructure.

The fix is only durable if a new job cannot be added without a bound, which is
what this asserts. It is a structural contract, not a performance budget: the
numbers below are deliberately far above the observed maximum, because a
timeout tight enough to trip on ordinary variance would swap one flake for
another.

Measured on 404 successful job runs sampled from CI history (minutes):

    workflow               job                          median    p95     max
    CI (Python)            Stdlib-only modules             0.1    0.2     0.2
    CI (Python)            Lint, type-check, drift         0.2    0.3     0.3
    CI (Python)            Unit tests and coverage         2.5   27.3    44.9
    CI (Python)            Build, verify TUI evidence      3.5   10.3    18.9
    CI (Python)            Bundled-agg wheel               0.3    0.4     0.4
    CI (Rust)              Lint, type-check and test      10.4   12.8    13.3
    Docker Image (Python)  Build and publish              1.0    4.5     4.6
    Docker Image (Rust)    Build, smoke-test, publish     3.0    3.6     3.8
    Docs site              Build VitePress docs           0.3    0.4     0.4
    Publish crates (Rust)  Gate                           3.2    3.5     3.5
    Security (Rust)        Public API compatibility       1.1    1.1     1.2

The two outliers are exactly the two jobs that ran `apt-get`: their tails are
the mirror, not the work. With the mirror off the critical path the unit-test
job's own steps total under two minutes, so 20 is roughly a tenfold headroom.
"""

from __future__ import annotations

import unittest
from pathlib import Path

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
WORKFLOWS = REPO_ROOT / ".github" / "workflows"

# Commands that reach a package index, registry or mirror. These are the steps
# that stall, so they carry their own bound as well as the job's.
INSTALL_MARKERS = (
    "apt-get",
    "cargo install",
    "npm ci",
    "npm install",
    "uv sync",
    "uv pip install",
    "pip install",
)

# A job bound has to leave room for the slowest legitimate run. Anything under
# this is likely a budget mistaken for a backstop.
MIN_JOB_TIMEOUT_MINUTES = 10
# And anything over this is not really a bound: the point is to fail in
# minutes, not to shave an hour off the six-hour ceiling.
MAX_JOB_TIMEOUT_MINUTES = 60


def _workflows() -> list[tuple[str, dict]]:
    return [
        (path.name, yaml.safe_load(path.read_text(encoding="utf-8")))
        for path in sorted(WORKFLOWS.glob("*.yml"))
    ]


class EveryJobIsBoundedTest(unittest.TestCase):
    def test_every_job_declares_a_timeout(self) -> None:
        unbounded = [
            f"{name}:{job_name}"
            for name, doc in _workflows()
            for job_name, job in (doc.get("jobs") or {}).items()
            if job.get("timeout-minutes") is None
        ]
        self.assertEqual(
            [],
            unbounded,
            "these jobs run to GitHub's six-hour ceiling when a step stalls (#183); "
            "give each a `timeout-minutes`",
        )

    def test_job_timeouts_are_backstops_not_budgets(self) -> None:
        for name, doc in _workflows():
            for job_name, job in (doc.get("jobs") or {}).items():
                with self.subTest(workflow=name, job=job_name):
                    minutes = job["timeout-minutes"]
                    self.assertIsInstance(minutes, int)
                    self.assertGreaterEqual(minutes, MIN_JOB_TIMEOUT_MINUTES)
                    self.assertLessEqual(minutes, MAX_JOB_TIMEOUT_MINUTES)

    def test_every_package_install_step_is_bounded(self) -> None:
        """A step bound is what makes a stall fail in minutes rather than hours.

        The job bound alone would still let one stalled install consume the
        whole job, and — because `retry.sh` needs somewhere to stand — the
        install steps are the ones worth naming individually.
        """
        unbounded = []
        for name, doc in _workflows():
            for job_name, job in (doc.get("jobs") or {}).items():
                for step in job.get("steps") or []:
                    run = step.get("run") or ""
                    if not any(marker in run for marker in INSTALL_MARKERS):
                        continue
                    if step.get("timeout-minutes") is None:
                        unbounded.append(f"{name}:{job_name}:{step.get('name')}")
        self.assertEqual([], unbounded, "unbounded package-install steps (#183)")


class RetriedInstallsUseTheHelperTest(unittest.TestCase):
    """`cargo install` compiles from a git checkout, so it can stall too.

    Each one goes through `retry.sh`, which bounds every *attempt*. A bare
    `timeout-minutes:` on the step cannot do that: the first attempt would eat
    the whole budget and the step would die having never retried.
    """

    def test_cargo_installs_are_retried(self) -> None:
        for name, doc in _workflows():
            for job_name, job in (doc.get("jobs") or {}).items():
                for step in job.get("steps") or []:
                    run = step.get("run") or ""
                    if "cargo install" not in run:
                        continue
                    with self.subTest(workflow=name, job=job_name):
                        self.assertIn("retry.sh", run)

    def test_the_retry_helper_exists_and_is_executable(self) -> None:
        helper = REPO_ROOT / ".github" / "scripts" / "retry.sh"
        self.assertTrue(helper.is_file(), helper)
        self.assertTrue(helper.stat().st_mode & 0o111, f"{helper} is not executable")


if __name__ == "__main__":
    unittest.main()
