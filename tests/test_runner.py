from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

from tui_verifier.config import VerifierConfig
from tui_verifier.models import CommandSpec, Recipe
from tui_verifier.runner import VerificationRunner


class RunnerTest(unittest.TestCase):
    def test_run_records_cast_and_asserts_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            recipe = Recipe(
                name="hello",
                command=CommandSpec(
                    argv=[sys.executable, "-c", "print('hello tui verifier')"]
                ),
                steps=[
                    {
                        "action": "wait_for_text",
                        "text": "hello tui verifier",
                        "timeout_seconds": 5,
                    }
                ],
                assertions=[
                    {
                        "type": "output_contains",
                        "value": "hello tui verifier",
                    }
                ],
            )
            result = VerificationRunner().run(recipe, Path(tmp), render_video=False)
            self.assertTrue(result.passed)
            self.assertTrue(Path(result.artifacts["cast"]).exists())
            self.assertTrue(Path(result.artifacts["screenshot"]).exists())
            self.assertTrue(Path(result.artifacts["screen_text"]).exists())

    def test_run_process_mode_records_cast(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            recipe = Recipe(
                name="process",
                command=CommandSpec(
                    argv=[sys.executable, "-c", "print('hello process')"],
                    pty=False,
                ),
                steps=[
                    {
                        "action": "wait_for_text",
                        "text": "hello process",
                    }
                ],
                assertions=[
                    {
                        "type": "output_contains",
                        "value": "hello process",
                    }
                ],
            )
            result = VerificationRunner().run(recipe, Path(tmp), render_video=False)
            self.assertTrue(result.passed)
            self.assertTrue(Path(result.artifacts["cast"]).exists())

    def test_runner_accepts_config(self) -> None:
        config = VerifierConfig.builtin()
        runner = VerificationRunner(config=config)
        self.assertIs(runner.config, config)
        self.assertIn("wait_for_text", runner.step_registry.names())
        self.assertIn("output_contains", runner.assertion_registry.names())

    def test_runner_defaults_to_builtin_config(self) -> None:
        runner = VerificationRunner()
        self.assertIsNotNone(runner.config)
        self.assertIn("wait_for_text", runner.step_registry.names())
