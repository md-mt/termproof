"""Example custom reporter for TermProof.

Implements a JSON summary reporter. Register it in config:

.. code-block:: yaml

   reporters:
     json_summary: termproof_my_plugin.reporters:JsonSummaryReporter
"""

from __future__ import annotations

import json

from termproof.before_after import BeforeAfterResult
from termproof.build_info import BuildInfo
from termproof.models import RunResult


class JsonSummaryReporter:
    """Emit a compact machine-readable summary of all runs.

    CLI usage::

        termproof run recipes/ --reporter json_summary

    Protocol compatibility:
    - Compatible with TermProof >=0.1.0
    - ``name`` attribute must match config ``reporters`` key
    - ``generate(results, build_info, before_after) -> str`` required
    """

    name = "json_summary"

    def generate(
        self,
        results: list[RunResult],
        build_info: BuildInfo | None = None,
        before_after: BeforeAfterResult | None = None,
    ) -> str:
        payload = {
            "summary": {
                "total": len(results),
                "passed": sum(1 for r in results if r.passed),
                "failed": sum(1 for r in results if not r.passed),
                "score_avg": (sum(r.score for r in results) / len(results)) if results else 0.0,
            },
            "results": [
                {
                    "recipe": r.recipe_name,
                    "passed": r.passed,
                    "exit_code": r.exit_code,
                    "duration_seconds": r.duration_seconds,
                    "priority": r.priority,
                    "execution": r.execution,
                    "renderer": r.renderer,
                    "score": r.score,
                    "assertions": [
                        {"name": a.name, "passed": a.passed, "detail": a.detail}
                        for a in r.assertions
                    ],
                    "steps": [
                        {"name": s.name, "passed": s.passed, "detail": s.detail}
                        for s in r.steps
                    ],
                    "artifacts": r.artifacts,
                }
                for r in results
            ],
        }
        if build_info is not None:
            payload["build"] = {
                "mode": build_info.mode,
                "command": build_info.command,
                "binary": str(build_info.binary_path),
                "version": build_info.version,
                "git_commit": str(build_info.git_commit) if build_info.git_commit else None,
            }
        return json.dumps(payload, indent=2) + "\n"
