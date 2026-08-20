from __future__ import annotations

import unittest

from termproof.models import (
    AssertionResult,
    RunResult,
    StepResult,
    assertion_map,
    score_from,
    score_from_assertions,
)


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


class ScoreFromTest(unittest.TestCase):
    def test_an_empty_assertion_map_scores_one_not_zero(self) -> None:
        # The contract decision this function exists to make once: see the
        # RunResult docstring.
        self.assertEqual(1.0, score_from({}))

    def test_a_map_scores_the_fraction_that_held(self) -> None:
        self.assertEqual(1.0, score_from(assertion_map([("a", True), ("b", True)])))
        self.assertEqual(0.0, score_from(assertion_map([("a", False), ("b", False)])))
        self.assertEqual(0.5, score_from(assertion_map([("a", True), ("b", False)])))
        self.assertEqual(
            2.0 / 3.0,
            score_from(assertion_map([("a", True), ("b", True), ("c", False)])),
        )

    def test_the_order_the_pairs_arrived_in_cannot_move_the_score(self) -> None:
        forwards = assertion_map([("a", True), ("b", False), ("c", False)])
        backwards = assertion_map([("c", False), ("b", False), ("a", True)])
        self.assertEqual(score_from(forwards), score_from(backwards))

    def test_a_repeated_name_is_one_assertion_and_the_last_value_wins(self) -> None:
        mapping = assertion_map([("a", True), ("a", False)])
        self.assertEqual(1, len(mapping))
        self.assertEqual(0.0, score_from(mapping))

    def test_the_list_and_the_map_score_the_same_assertions_alike(self) -> None:
        # One rule, two shapes: the list keeps duplicates, so this is only
        # stated for distinct names.
        cases: list[list[tuple[str, bool]]] = [
            [],
            [("a", True)],
            [("a", False), ("b", False)],
            [("a", True), ("b", False), ("c", True)],
        ]
        for case in cases:
            with self.subTest(case=case):
                results = [AssertionResult(name, passed, "") for name, passed in case]
                self.assertEqual(
                    score_from_assertions(results),
                    score_from(assertion_map(case)),
                )


if __name__ == "__main__":
    unittest.main()
