"""The documented required-check names must be names a workflow can produce.

`rust/docs/governance.md` §5 is the ruleset contract: the exact check names a
`main` ruleset requires. The document says so itself — "Renaming a job silently
un-gates the ruleset, and this list is the contract" — and then asks for the
table to be edited by hand in the same PR as any rename.

Nothing enforced that. A rename with a forgotten table edit produces a ruleset
naming a check that never reports, and GitHub does not complain: a required
check that never arrives is indistinguishable from one still running, so
merges block or, if the ruleset is later relaxed, the gate is simply gone. The
consolidation renamed every workflow and this branch renamed most of the jobs,
so the table has already been wrong once.

This walks the table and resolves every row against the workflows, expanding
matrix legs the way GitHub does when it names a check.

It checks the direction that fails silently: a documented name that no job can
produce. The reverse — a job missing from the table — is a deliberate choice
the document explains under "Not required, and why", so it is not asserted.
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
GOVERNANCE = REPO_ROOT / "rust" / "docs" / "governance.md"
WORKFLOWS = REPO_ROOT / ".github" / "workflows"

#: `| `check` | `workflow` | `job` (optional note) |`
ROW = re.compile(
    r"^\|\s*`(?P<check>[^`]+)`\s*\|\s*`(?P<workflow>[^`]+)`\s*\|\s*`(?P<job>[^`]+)`"
)

#: `${{ matrix.python-version }}`
MATRIX_REF = re.compile(r"\$\{\{\s*matrix\.([A-Za-z0-9_-]+)\s*\}\}")


def _documented_rows() -> list[tuple[str, str, str]]:
    text = GOVERNANCE.read_text(encoding="utf-8")
    section = text.split("## 5. Required checks", 1)[1].split("\n## ", 1)[0]
    return [
        (m.group("check"), m.group("workflow"), m.group("job"))
        for line in section.splitlines()
        if (m := ROW.match(line))
    ]


def _workflows_by_name() -> dict[str, dict]:
    loaded = {}
    for path in sorted(WORKFLOWS.glob("*.yml")):
        workflow = yaml.safe_load(path.read_text(encoding="utf-8"))
        loaded[workflow["name"]] = workflow
    return loaded


def _matrix_values(job: dict, key: str) -> list[str]:
    """Every value `matrix.<key>` can take, across both matrix spellings."""
    matrix = job.get("strategy", {}).get("matrix", {})
    values = [str(v) for v in matrix.get(key, [])]
    for entry in matrix.get("include", []):
        if key in entry:
            values.append(str(entry[key]))
    return values


def _substitute(name: str, key: str, value: str) -> str:
    """Replace `${{ matrix.<key> }}` with `value`, leaving other refs alone.

    A named function rather than a closure: a lambda here would capture the
    loop variables it reads rather than their values at definition time
    (ruff B023), which is only correct by accident when the loop body runs
    eagerly.
    """
    return MATRIX_REF.sub(
        lambda m: value if m.group(1) == key else m.group(0), name
    )


def _check_names(job_id: str, job: dict) -> set[str]:
    """The check names GitHub reports for a job, matrix legs expanded."""
    template = job.get("name", job_id)
    refs = MATRIX_REF.findall(template)
    if not refs:
        return {template}
    names = {template}
    for ref in refs:
        values = _matrix_values(job, ref)
        names = {
            _substitute(name, ref, value) for name in names for value in values
        }
    return names


class RequiredCheckNamesTest(unittest.TestCase):
    def test_the_table_is_not_empty(self) -> None:
        """Guard the guard: a table format change must fail, not skip."""
        self.assertGreaterEqual(len(_documented_rows()), 10)

    def test_every_documented_check_resolves_to_a_real_job(self) -> None:
        workflows = _workflows_by_name()
        problems = []
        for check, workflow_name, job_id in _documented_rows():
            workflow = workflows.get(workflow_name)
            if workflow is None:
                problems.append(
                    f"{check!r}: no workflow named {workflow_name!r} "
                    f"(have: {', '.join(sorted(workflows))})"
                )
                continue
            job = workflow["jobs"].get(job_id)
            if job is None:
                problems.append(
                    f"{check!r}: {workflow_name!r} has no job {job_id!r} "
                    f"(have: {', '.join(sorted(workflow['jobs']))})"
                )
                continue
            produced = _check_names(job_id, job)
            if check not in produced:
                problems.append(
                    f"{check!r}: {workflow_name!r} job {job_id!r} reports "
                    f"{sorted(produced)}"
                )
        self.assertEqual(
            [],
            problems,
            "governance.md §5 names checks no workflow produces; a ruleset "
            "requiring these would wait forever:\n" + "\n".join(problems),
        )

    def test_every_matrix_leg_of_a_documented_job_is_documented(self) -> None:
        """A matrix leg left out of the table is an ungated platform.

        `CI (Rust)` gained a macOS leg once already. Requiring only the Linux
        one would leave macOS able to fail a merge into `main` silently.
        """
        workflows = _workflows_by_name()
        documented = {check for check, _, _ in _documented_rows()}
        missing = []
        for check, workflow_name, job_id in _documented_rows():
            job = workflows.get(workflow_name, {}).get("jobs", {}).get(job_id)
            if job is None:
                continue
            for name in _check_names(job_id, job):
                if name not in documented:
                    missing.append(f"{workflow_name} / {job_id}: {name!r}")
        self.assertEqual(
            [],
            sorted(set(missing)),
            "these matrix legs belong to a required job but are not in the "
            "table:\n" + "\n".join(sorted(set(missing))),
        )


if __name__ == "__main__":
    unittest.main()
