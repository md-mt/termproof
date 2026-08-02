from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

from termproof.config import VerifierConfig
from termproof.models import CommandSpec, Recipe
from termproof.runner import VerificationRunner


class RunnerTest(unittest.TestCase):
    def test_run_records_cast_and_asserts_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            recipe = Recipe(
                name="hello",
                command=CommandSpec(
                    argv=[sys.executable, "-c", "print('hello termproof')"]
                ),
                steps=[
                    {
                        "action": "wait_for_text",
                        "text": "hello termproof",
                        "timeout_seconds": 5,
                    }
                ],
                assertions=[
                    {
                        "type": "output_contains",
                        "value": "hello termproof",
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

    def test_runner_has_session_backend(self) -> None:
        runner = VerificationRunner()
        self.assertIsNotNone(runner.session_backend)

    def test_session_backend_creates_session(self) -> None:
        runner = VerificationRunner()
        session = runner.session_backend.create_session(
            argv=[sys.executable, "-c", "print('hello')"],
            cast_path=Path(tempfile.mkdtemp()) / "session.cast",
            cwd=None,
            env={},
            cols=80,
            rows=24,
        )
        try:
            with session:
                session.wait_for_text("hello", timeout_seconds=5)
                self.assertIn("hello", session.raw_output)
        finally:
            session.close()

    def test_runner_has_video_backend_registry(self) -> None:
        runner = VerificationRunner()
        self.assertIn("agg_ffmpeg", runner.video_backend_registry.names())

    def test_video_backend_roundtrip(self) -> None:
        """Resolve the agg_ffmpeg backend and verify it renders."""
        runner = VerificationRunner()
        backend = runner.video_backend_registry.get("agg_ffmpeg")
        self.assertIsNotNone(backend)

    def test_run_pty_converts_step_exception_to_failed_result(self) -> None:
        """A PTY step that raises yields a failed StepResult, not an abort.

        Mirrors the process-mode behavior. Uses a fake session backend so the
        test does not need asciinema/ffmpeg to exercise the error-wrapping path.
        """

        class _FakeSession:
            screen = "screen-snapshot"
            raw_output = "raw"
            exit_code = 0

            def __enter__(self) -> "_FakeSession":
                return self

            def __exit__(self, *exc: object) -> bool:
                return False

            def press(self, key: str) -> None:
                # Mirror the real session: unknown key raises KeyError.
                raise KeyError(key.lower())

            def wait_for_exit(self, timeout_seconds: float) -> None:
                return None

            def wait_for_idle(self, stable: float, timeout: float) -> bool:
                return True

        class _FakeBackend:
            def create_session(self, *args: object, **kwargs: object) -> "_FakeSession":
                return _FakeSession()

        with tempfile.TemporaryDirectory() as tmp:
            runner = VerificationRunner()
            runner.session_backend = _FakeBackend()
            recipe = Recipe(
                name="pty-error",
                command=CommandSpec(
                    argv=[sys.executable, "-c", "pass"],
                    pty=True,
                ),
                steps=[{"action": "press", "key": "not-a-real-key"}],
                expect_exit_code=None,
            )
            steps, raw_output, exit_code, screen = runner._run_pty(
                recipe, Path(tmp)
            )
            self.assertEqual(len(steps), 1)
            self.assertFalse(steps[0].passed)
            self.assertIn("not-a-real-key", steps[0].detail)
            self.assertEqual(steps[0].screen, "screen-snapshot")

    def test_runner_run_uses_video_backend(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            recipe = Recipe(
                name="video-test",
                command=CommandSpec(
                    argv=[sys.executable, "-c", "print('ok')"],
                    pty=False,
                ),
                steps=[{"action": "wait_for_text", "text": "ok"}],
                assertions=[{"type": "output_contains", "value": "ok"}],
            )
            result = VerificationRunner().run(
                recipe,
                Path(tmp),
                render_video=False,
                video_backend_name="agg_ffmpeg",
            )
            self.assertTrue(result.passed)
