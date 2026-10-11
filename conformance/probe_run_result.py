#!/usr/bin/env python3
"""Oracle half of the run-result differential harness.

Records what the Python :meth:`termproof.models.RunResult.to_dict` emits for a
fixed scenario — the document ``write_result_files`` writes as ``result.json``
and the run cache and CI evidence read back. The Rust half transcribes the
same scenario and compares the serialised documents.

The scenario is code, not a corpus of cases, as with the evidence manifest:
there is one document shape to compare and it is built by constructing the
model rather than by replaying data. Two results cover the shapes a single
one cannot: a populated run, whose nested step and assertion documents are
compared along with the top level, and an empty one, which is where
``exit_code`` is ``null`` and every list is empty.

This half records the Python document as it is. The one known divergence —
Rust writes a ``result_version`` key and Python writes none (#209) — is **not**
recorded here: it is a named allowance in the Rust test, so the checked-in
expectation stays the oracle's testimony and the allowance has to be edited
deliberately, in code, if either side changes.

Regenerate deliberately::

    cd /path/to/termproof/python
    TERMPROOF_PYTHON_REPO=$PWD uv run python \\
        ../conformance/probe_run_result.py \\
        > ../conformance/corpus/run_result.expected.json
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.environ.get("TERMPROOF_PYTHON_REPO", str(Path(__file__).parent.parent / "python")))

from termproof.models import AssertionResult, RunResult, StepResult  # noqa: E402


def scenario() -> list[RunResult]:
    """The fixed scenario. Keep in step with differential_run_result.rs."""
    return [
        RunResult(
            recipe_name="login",
            passed=False,
            exit_code=1,
            duration_seconds=1.25,
            priority="P0",
            execution="scripted",
            renderer="default",
            score=0.0,
            steps=[
                StepResult(
                    name="menu-open",
                    passed=True,
                    detail="screen contains 'MENU'",
                    screen="MENU\nitem one",
                )
            ],
            assertions=[
                AssertionResult(
                    name="screen_contains",
                    passed=False,
                    detail="menu missing",
                )
            ],
            artifacts={"screenshot": "/tmp/evidence/final.png"},
        ),
        RunResult(
            recipe_name="empty",
            passed=True,
            exit_code=None,
            duration_seconds=0.0,
            priority="P2",
            execution="scripted",
            renderer="default",
            score=1.0,
            steps=[],
            assertions=[],
            artifacts={},
        ),
    ]


def main() -> None:
    json.dump([result.to_dict() for result in scenario()], sys.stdout, indent=2, sort_keys=True)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
