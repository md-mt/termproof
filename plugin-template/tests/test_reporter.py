from __future__ import annotations

import json
import unittest

from termproof.models import AssertionResult, RunResult, StepResult

from termproof_my_plugin.reporters import JsonSummaryReporter


class JsonSummaryReporterTest(unittest.TestCase):
    def test_generates_valid_json(self):
        results = [
            RunResult(
                recipe_name="demo",
                passed=True,
                exit_code=0,
                duration_seconds=1.23,
                priority="P1",
                execution="scripted",
                renderer="default",
                score=1.0,
                steps=[StepResult("s1", True, "ok", "screen")],
                assertions=[AssertionResult("a1", True, "ok")],
                artifacts={"cast": "/tmp/cast"},
            )
        ]
        output = JsonSummaryReporter().generate(results)
        data = json.loads(output)
        self.assertEqual(1, data["summary"]["total"])
        self.assertEqual(1, data["summary"]["passed"])
        self.assertEqual("demo", data["results"][0]["recipe"])

    def test_summary_counts_failures(self):
        results = [
            RunResult(
                recipe_name="pass-r",
                passed=True,
                exit_code=0,
                duration_seconds=0.5,
                priority="P0",
                execution="scripted",
                renderer="default",
                score=1.0,
                steps=[],
                assertions=[],
                artifacts={},
            ),
            RunResult(
                recipe_name="fail-r",
                passed=False,
                exit_code=1,
                duration_seconds=0.2,
                priority="P1",
                execution="scripted",
                renderer="default",
                score=0.0,
                steps=[],
                assertions=[],
                artifacts={},
            ),
        ]
        data = json.loads(JsonSummaryReporter().generate(results))
        self.assertEqual(2, data["summary"]["total"])
        self.assertEqual(1, data["summary"]["passed"])
        self.assertEqual(1, data["summary"]["failed"])


if __name__ == "__main__":
    unittest.main()
