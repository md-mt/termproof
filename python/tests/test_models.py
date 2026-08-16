from __future__ import annotations

import unittest

from termproof.models import AssertionResult, RunResult, StepResult


def _result() -> RunResult:
    return RunResult(
        recipe_name="demo",
        passed=True,
        exit_code=0,
        duration_seconds=1.25,
        priority="P1",
        execution="scripted",
        renderer="default",
        score=1.0,
        steps=[StepResult("step", True, "detail", "screen")],
        assertions=[AssertionResult("assert", True, "detail")],
        artifacts={"screenshot": "final.svg"},
    )


class RunResultSerializationTest(unittest.TestCase):
    def test_to_dict_matches_expected_shape(self) -> None:
        self.assertEqual(
            {
                "recipe_name": "demo",
                "passed": True,
                "exit_code": 0,
                "duration_seconds": 1.25,
                "priority": "P1",
                "execution": "scripted",
                "renderer": "default",
                "score": 1.0,
                "steps": [
                    {"name": "step", "passed": True, "detail": "detail", "screen": "screen"}
                ],
                "assertions": [{"name": "assert", "passed": True, "detail": "detail"}],
                "artifacts": {"screenshot": "final.svg"},
            },
            _result().to_dict(),
        )

    def test_round_trip_is_lossless(self) -> None:
        result = _result()
        self.assertEqual(result, RunResult.from_dict(result.to_dict()))

    def test_from_dict_defaults_missing_exit_code_to_none(self) -> None:
        data = _result().to_dict()
        data.pop("exit_code")
        self.assertIsNone(RunResult.from_dict(data).exit_code)

    def test_from_dict_defaults_missing_collections(self) -> None:
        data = _result().to_dict()
        del data["steps"]
        del data["assertions"]
        del data["artifacts"]
        restored = RunResult.from_dict(data)
        self.assertEqual([], restored.steps)
        self.assertEqual([], restored.assertions)
        self.assertEqual({}, restored.artifacts)


if __name__ == "__main__":
    unittest.main()
