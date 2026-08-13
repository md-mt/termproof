from __future__ import annotations

import unittest

from termproof_my_plugin.assertions import ScreenCount
from termproof_my_plugin.step_assertions import StepScreenMatches

from termproof.models import CommandSpec, Recipe, StepResult


def _recipe(name: str = "r") -> Recipe:
    return Recipe(name=name, command=CommandSpec(argv=["echo", "hi"]))


def _steps() -> list[StepResult]:
    return [
        StepResult("open dashboard", True, "", "Dashboard READY 3/3"),
        StepResult("quit", True, "", "bye"),
    ]


class StepScreenMatchesTest(unittest.TestCase):
    # --- happy path --------------------------------------------------------------
    def test_matches_the_named_step_screen(self):
        r = StepScreenMatches().evaluate(
            _recipe(),
            {"step": "open dashboard", "pattern": r"Dashboard .* \d+/\d+"},
            "bye",
            "",
            0,
            steps=_steps(),
        )
        self.assertTrue(r.passed)

    def test_final_screen_is_not_what_is_read(self):
        r = StepScreenMatches().evaluate(
            _recipe(),
            {"step": "quit", "pattern": "Dashboard"},
            "Dashboard READY 3/3",
            "",
            0,
            steps=_steps(),
        )
        self.assertFalse(r.passed)

    # --- missing fields ----------------------------------------------------------
    def test_missing_step(self):
        r = StepScreenMatches().evaluate(
            _recipe(), {"pattern": "OK"}, "", "", 0, steps=_steps()
        )
        self.assertFalse(r.passed)
        self.assertIn("'step'", r.detail)

    def test_missing_pattern(self):
        r = StepScreenMatches().evaluate(
            _recipe(), {"step": "quit"}, "", "", 0, steps=_steps()
        )
        self.assertFalse(r.passed)
        self.assertIn("'pattern'", r.detail)

    def test_invalid_regex(self):
        r = StepScreenMatches().evaluate(
            _recipe(), {"step": "quit", "pattern": "[bad"}, "", "", 0, steps=_steps()
        )
        self.assertFalse(r.passed)
        self.assertIn("invalid regex", r.detail)

    # --- unknown step ------------------------------------------------------------
    def test_unknown_step_reports_the_steps_that_ran(self):
        r = StepScreenMatches().evaluate(
            _recipe(), {"step": "typo", "pattern": "OK"}, "", "", 0, steps=_steps()
        )
        self.assertFalse(r.passed)
        self.assertIn("'open dashboard'", r.detail)

    # --- older TermProof ---------------------------------------------------------
    def test_runs_when_the_caller_does_not_pass_steps(self):
        """A TermProof without per-step screens calls with five arguments."""
        r = StepScreenMatches().evaluate(
            _recipe(), {"step": "quit", "pattern": "OK"}, "bye", "", 0
        )
        self.assertFalse(r.passed)
        self.assertIn("unavailable", r.detail)


class OptInIsExplicitTest(unittest.TestCase):
    """An assertion opts in by declaring ``steps``; the other one still works.

    ``ScreenCount`` is written against the original assertion signature and is
    deliberately left that way, so this pins that both styles coexist in one
    plugin.
    """

    def test_screen_count_takes_no_steps(self):
        import inspect

        self.assertNotIn(
            "steps", inspect.signature(ScreenCount.evaluate).parameters
        )
        r = ScreenCount().evaluate(_recipe(), {"pattern": "OK", "min": 1}, "OK", "", 0)
        self.assertTrue(r.passed)

    def test_step_screen_matches_declares_steps_as_optional(self):
        import inspect

        steps = inspect.signature(StepScreenMatches.evaluate).parameters["steps"]
        self.assertIs(inspect.Parameter.KEYWORD_ONLY, steps.kind)
        self.assertIsNone(steps.default)


if __name__ == "__main__":
    unittest.main()
