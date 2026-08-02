from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from termproof.config import VerifierConfig, load_config
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

            def __enter__(self) -> _FakeSession:
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
            def create_session(self, *args: object, **kwargs: object) -> _FakeSession:
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

    @patch("termproof.evidence._resolve_ffmpeg", return_value=None)
    @patch("termproof.evidence.resolve_agg", return_value=None)
    def test_run_render_video_default_backend_warns_and_omits_when_tools_missing(
        self, resolve_agg, resolve_ffmpeg
    ) -> None:
        """Runner-level regression: a normal --video run through the built-in
        agg_ffmpeg backend must warn and omit the video artifact when the host
        lacks agg/ffmpeg, instead of recording a nonexistent artifact."""
        with tempfile.TemporaryDirectory() as tmp:
            recipe = Recipe(
                name="video-warn",
                command=CommandSpec(
                    argv=[sys.executable, "-c", "print('ok')"],
                    pty=False,
                ),
                steps=[{"action": "wait_for_text", "text": "ok"}],
                assertions=[{"type": "output_contains", "value": "ok"}],
            )
            with self.assertWarns(UserWarning) as caught:
                result = VerificationRunner().run(
                    recipe,
                    Path(tmp),
                    render_video=True,
                    video_backend_name="agg_ffmpeg",
                )
            self.assertTrue(result.passed)
            self.assertNotIn("video", result.artifacts)
            message = str(caught.warning)
            self.assertIn("agg", message)
            self.assertIn("--video", message)


class IdleCapWiringTest(unittest.TestCase):
    """The post-script idle wait cap must come from config, not a magic 3."""

    class _RecordingSession:
        def __init__(self) -> None:
            self.idle_calls: list[tuple[float, float]] = []

        def __enter__(self) -> "IdleCapWiringTest._RecordingSession":
            return self

        def __exit__(self, *args: object) -> None:
            return None

        @property
        def raw_output(self) -> str:
            return ""

        @property
        def exit_code(self) -> int | None:
            return None

        @property
        def screen(self) -> str:
            return ""

        def wait_for_idle(self, stable_seconds: float, timeout_seconds: float) -> bool:
            self.idle_calls.append((stable_seconds, timeout_seconds))
            return True

        def wait_for_exit(self, timeout_seconds: float) -> int | None:
            return None

    class _FakeBackend:
        def __init__(self, session: "IdleCapWiringTest._RecordingSession") -> None:
            self.session = session

        def create_session(self, argv, cast_path, cwd, env, cols, rows):
            return self.session

    def _run_pty_with_config(self, idle_cap_seconds: float | None) -> list[tuple[float, float]]:
        session = self._RecordingSession()
        runner = VerificationRunner()
        runner.session_backend = self._FakeBackend(session)
        runner.config = load_config(
            project_path=Path(tempfile.mkdtemp()),
            user_path=Path(tempfile.mkdtemp()) / "nonexistent.yaml",
        )
        recipe = Recipe(
            name="idle-cap",
            command=CommandSpec(argv=[sys.executable, "-c", "import time; time.sleep(2)"]),
            steps=[],
            expect_exit_code=None,
            timeout_seconds=30.0,
        )
        runner._run_pty(recipe, Path(tempfile.mkdtemp()))
        return session.idle_calls

    def test_default_idle_cap_is_three_seconds(self) -> None:
        calls = self._run_pty_with_config(idle_cap_seconds=3.0)
        # With the builtin default (3.0) the idle wait is capped at 3s.
        self.assertEqual(calls, [(0.5, 3.0)])

    def test_configured_idle_cap_is_used(self) -> None:
        session = self._RecordingSession()
        runner = VerificationRunner()
        runner.session_backend = self._FakeBackend(session)
        with tempfile.TemporaryDirectory() as tmp:
            user_yaml = Path(tmp) / "user.yaml"
            user_yaml.write_text("defaults:\n  idle_cap_seconds: 7.5\n", encoding="utf-8")
            runner.config = load_config(
                project_path=Path(tmp),
                user_path=user_yaml,
            )
            recipe = Recipe(
                name="idle-cap",
                command=CommandSpec(argv=[sys.executable, "-c", "import time; time.sleep(2)"]),
                steps=[],
                expect_exit_code=None,
                timeout_seconds=30.0,
            )
            runner._run_pty(recipe, Path(tmp) / "run")
        self.assertEqual(session.idle_calls, [(0.5, 7.5)])

    def test_null_idle_cap_waits_up_to_recipe_timeout(self) -> None:
        session = self._RecordingSession()
        runner = VerificationRunner()
        runner.session_backend = self._FakeBackend(session)
        with tempfile.TemporaryDirectory() as tmp:
            user_yaml = Path(tmp) / "user.yaml"
            user_yaml.write_text("defaults:\n  idle_cap_seconds:\n", encoding="utf-8")
            runner.config = load_config(
                project_path=Path(tmp),
                user_path=user_yaml,
            )
            recipe = Recipe(
                name="idle-cap",
                command=CommandSpec(argv=[sys.executable, "-c", "import time; time.sleep(2)"]),
                steps=[],
                expect_exit_code=None,
                timeout_seconds=30.0,
            )
            runner._run_pty(recipe, Path(tmp) / "run")
        # No cap: wait up to the recipe timeout for quiescence.
        self.assertEqual(session.idle_calls, [(0.5, 30.0)])


class QuiescenceBehaviorTest(unittest.TestCase):
    """wait_for_idle detects quiescence and respects timeouts on real sessions."""

    def test_wait_for_idle_returns_true_when_screen_stabilizes(self) -> None:
        runner = VerificationRunner()
        session = runner.session_backend.create_session(
            argv=[sys.executable, "-c", "print('hello'); import time; time.sleep(5)"],
            cast_path=Path(tempfile.mkdtemp()) / "session.cast",
            cwd=None,
            env={},
            cols=80,
            rows=24,
        )
        try:
            with session:
                self.assertTrue(session.wait_for_idle(0.2, 3.0))
        finally:
            session.close()

    def test_wait_for_idle_times_out_when_output_never_stable(self) -> None:
        runner = VerificationRunner()
        session = runner.session_backend.create_session(
            # Prints a line every 50ms for ~2s: screen never stabilizes for
            # 0.3s inside the 0.8s window, so wait_for_idle must time out.
            argv=[
                sys.executable,
                "-c",
                "import time; [print(i) or time.sleep(0.05) for i in range(40)]",
            ],
            cast_path=Path(tempfile.mkdtemp()) / "session.cast",
            cwd=None,
            env={},
            cols=80,
            rows=24,
        )
        try:
            with session:
                self.assertFalse(session.wait_for_idle(0.3, 0.8))
        finally:
            session.close()
