from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

from termproof.config import VerifierConfig
from termproof.models import CommandSpec, Recipe
from termproof.runner import VerificationRunner


class WaitForRegexStepTest(unittest.TestCase):
    def test_wait_for_regex_matches_literal_text(self):
        with tempfile.TemporaryDirectory() as tmp:
            recipe = Recipe(
                name="regex-literal",
                command=CommandSpec(argv=[sys.executable, "-c", "print('hello version 1.2.3')"]),
                steps=[
                    {"action": "wait_for_regex", "pattern": r"version \d+\.\d+\.\d+", "timeout_seconds": 5}
                ],
                assertions=[{"type": "output_contains", "value": "version"}],
            )
            result = VerificationRunner().run(recipe, Path(tmp), render_video=False)
            self.assertTrue(result.passed, f"steps: {result.steps}")
            self.assertIn("1.2.3", result.steps[0].detail or "")

    def test_wait_for_regex_captures_groups(self):
        with tempfile.TemporaryDirectory() as tmp:
            recipe = Recipe(
                name="regex-groups",
                command=CommandSpec(argv=[sys.executable, "-c", "print('user: alice id: 42')"]),
                steps=[
                    {"action": "wait_for_regex", "pattern": r"user: (?P<user>\w+) id: (?P<id>\d+)", "timeout_seconds": 5}
                ],
                assertions=[{"type": "output_contains", "value": "alice"}],
            )
            result = VerificationRunner().run(recipe, Path(tmp), render_video=False)
            self.assertTrue(result.passed)
            # evidence should include groups
            detail = result.steps[0].detail
            self.assertIn("alice", detail)
            self.assertIn("42", detail)

    def test_wait_for_regex_invalid_pattern_fails_fast(self):
        from termproof.builtin_steps import WaitForRegex
        step_action = WaitForRegex()
        # invalid regex should raise during validation or return failed result
        import unittest.mock as mock
        fake_session = mock.Mock()
        fake_session.screen = "some screen"
        fake_session.raw_output = "some output"
        # We want this to raise or produce failed StepResult with clear message about invalid regex
        # spec says "validated regex" so should not silently pass nor crash with raw re.error
        step = {"pattern": "[invalid", "timeout_seconds": 1}
        try:
            result = step_action.execute(fake_session, step, 1)
            # if it doesn't raise, it should be failed with detail mentioning invalid regex
            self.assertFalse(result.passed)
            self.assertIn("invalid", result.detail.lower())
        except ValueError as e:
            # also acceptable: raise ValueError with clear message
            self.assertIn("invalid", str(e).lower())

    def test_wait_for_regex_timeout(self):
        with tempfile.TemporaryDirectory() as tmp:
            recipe = Recipe(
                name="regex-timeout",
                command=CommandSpec(argv=[sys.executable, "-c", "import time; print('hello'); time.sleep(2)"]),
                steps=[
                    {"action": "wait_for_regex", "pattern": r"never-matching-xyz-\d+", "timeout_seconds": 0.5}
                ],
                assertions=[],
            )
            result = VerificationRunner().run(recipe, Path(tmp), render_video=False)
            self.assertFalse(result.passed)

    def test_wait_for_regex_registered_in_builtin(self):
        config = VerifierConfig.builtin()
        self.assertIn("wait_for_regex", config.steps)


if __name__ == "__main__":
    unittest.main()
