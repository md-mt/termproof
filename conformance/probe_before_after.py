#!/usr/bin/env python3
"""Oracle half of the before/after differential harness.

Drives the Python :mod:`termproof.before_after` over ``corpus/before_after_cases.json``
and records, for each case, the deltas it computed — every field, under the
name it carries — and the markdown it rendered.

It exists because these two modules were *not* two bindings of one thing. They
were separate implementations that disagreed on the delta field names, on both
markdown forms and on the order the deltas came out in, and nothing failed:
each side's unit tests asserted its own wording, and no test had ever run both
(#204). Python was changed to match Rust, whose ordering rule is the documented
one, and this is what holds the two together from here.

Both halves of the recording matter and for different reasons. The **deltas**
are the API a consumer's own reporter reads, so the field names are the thing
that decides whether upstream can be swapped in for a local copy. The
**markdown** is the report a human reviewer reads, so a divergence there is
visible in published output rather than only in a type signature.

The empty case is recorded deliberately. "No deltas" is the most common outcome
of a before/after run, so it is the string most consumers see most often, and it
is the one the two implementations worded most differently.

Regenerate deliberately::

    cd /path/to/termproof/python
    TERMPROOF_PYTHON_REPO=$PWD uv run python \\
        ../conformance/probe_before_after.py \\
        > ../conformance/corpus/before_after.expected.json
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.environ.get("TERMPROOF_PYTHON_REPO", str(Path(__file__).parent.parent / "python")))

from termproof.before_after import build_before_after  # noqa: E402
from termproof.models import RunResult  # noqa: E402

CASES = Path(__file__).parent / "corpus" / "before_after_cases.json"


def _result(spec: dict[str, object]) -> RunResult:
    """A ``RunResult`` carrying only the three fields this layer reads.

    The rest are filled with fixed values rather than left out: the comparison
    reads ``recipe_name``, ``renderer`` and ``passed`` and nothing else, so
    anything varying here would be measuring a different module.
    """
    passed = bool(spec["passed"])
    return RunResult(
        recipe_name=str(spec["recipe"]),
        passed=passed,
        exit_code=0 if passed else 1,
        duration_seconds=0.0,
        priority="P0",
        execution="scripted",
        renderer=str(spec["renderer"]),
        score=1.0 if passed else 0.0,
        steps=[],
        assertions=[],
        artifacts={},
    )


def run(case: dict[str, object]) -> dict[str, object]:
    before = [_result(spec) for spec in case["before"]]  # type: ignore[union-attr]
    after = [_result(spec) for spec in case["after"]]  # type: ignore[union-attr]
    result = build_before_after(before, after)
    return {
        "name": case["name"],
        # A list, not a set or a mapping: the order is part of what is compared.
        "deltas": [
            {
                "recipe": delta.recipe,
                "renderer": delta.renderer,
                "before_outcome": delta.before_outcome,
                "after_outcome": delta.after_outcome,
                "explanation": delta.explanation(),
            }
            for delta in result.deltas
        ],
        "markdown": result.to_markdown(),
    }


def main() -> None:
    cases = json.loads(CASES.read_text(encoding="utf-8"))
    json.dump([run(case) for case in cases], sys.stdout, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
