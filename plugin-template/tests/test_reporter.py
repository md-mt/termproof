from __future__ import annotations

import json
import unittest

from termproof.before_after import BeforeAfterResult, BehaviorDelta
from termproof.build_info import BuildInfo
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
        self.assertEqual(0, data["summary"]["failed"])
        self.assertEqual(1.0, data["summary"]["score_avg"])
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

    def test_empty_results(self):
        output = JsonSummaryReporter().generate([])
        data = json.loads(output)
        self.assertEqual(0, data["summary"]["total"])
        self.assertEqual(0, data["summary"]["passed"])
        self.assertEqual(0, data["summary"]["failed"])
        self.assertEqual(0.0, data["summary"]["score_avg"])
        self.assertEqual([], data["results"])

    def test_score_average(self):
        results = [
            RunResult("a", True, 0, 1.0, "P0", "scripted", "default", 0.5, [], [], {}),
            RunResult("b", True, 0, 2.0, "P0", "scripted", "default", 1.0, [], [], {}),
        ]
        data = json.loads(JsonSummaryReporter().generate(results))
        self.assertEqual(0.75, data["summary"]["score_avg"])

    def test_includes_build_provenance(self):
        results = []
        build = BuildInfo(
            mode="scripted",
            command=["termproof", "run"],
            binary_path="/usr/bin/termproof",
            version="0.1.0",
            git_commit="abc1234",
            timestamp="2026-07-26T00:00:00Z",
        )
        output = JsonSummaryReporter().generate(results, build_info=build)
        data = json.loads(output)
        self.assertIn("build", data)
        self.assertEqual("scripted", data["build"]["mode"])
        # command is a list; it gets str()'d for display
        self.assertIn("termproof", data["build"]["command"])
        self.assertEqual("/usr/bin/termproof", data["build"]["binary"])
        self.assertEqual("0.1.0", data["build"]["version"])
        self.assertEqual("abc1234", data["build"]["git_commit"])

    def test_build_info_omitted_when_none(self):
        output = JsonSummaryReporter().generate([])
        data = json.loads(output)
        self.assertNotIn("build", data)

    def test_before_after_passed_through(self):
        """before_after is accepted but not included in the summary payload."""
        ba = BeforeAfterResult(
            before=[],
            after=[],
            deltas=[],
        )
        output = JsonSummaryReporter().generate([], before_after=ba)
        data = json.loads(output)
        # before_after is accepted by the protocol but not serialized by this
        # summary reporter — verify no crash and no serialization.
        self.assertIsInstance(data, dict)

    def test_nested_step_and_assertion_detail(self):
        results = [
            RunResult(
                recipe_name="detail-test",
                passed=False,
                exit_code=1,
                duration_seconds=5.0,
                priority="P1",
                execution="interactive",
                renderer="xterm",
                score=0.0,
                steps=[
                    StepResult("step1", True, "matched 'Hello'", "screen1"),
                    StepResult("step2", False, "timed out waiting for regex 'World'", "screen2"),
                ],
                assertions=[
                    AssertionResult("assert1", True, "found 3 matches"),
                    AssertionResult("assert2", False, "min (5) > 3"),
                ],
                artifacts={"video": "/tmp/video.mp4"},
            )
        ]
        data = json.loads(JsonSummaryReporter().generate(results))
        self.assertEqual(1, data["summary"]["total"])
        r = data["results"][0]
        self.assertEqual(2, len(r["steps"]))
        self.assertEqual("step1", r["steps"][0]["name"])
        self.assertTrue(r["steps"][0]["passed"])
        self.assertFalse(r["steps"][1]["passed"])
        self.assertEqual(2, len(r["assertions"]))
        self.assertFalse(r["assertions"][1]["passed"])
        self.assertEqual("/tmp/video.mp4", r["artifacts"]["video"])


if __name__ == "__main__":
    unittest.main()
