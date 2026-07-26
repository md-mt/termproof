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

    # -- process-mode (pty=False) timing / streaming tests -----------------

    def test_wait_for_regex_process_mode_matches_output(self):
        """wait_for_regex must match in process mode (pty=False)."""
        with tempfile.TemporaryDirectory() as tmp:
            recipe = Recipe(
                name="regex-process",
                command=CommandSpec(
                    argv=[sys.executable, "-c", "print('version 3.1.4')"],
                    pty=False,
                ),
                steps=[
                    {"action": "wait_for_regex", "pattern": r"version \d+\.\d+\.\d+", "timeout_seconds": 5},
                ],
                assertions=[{"type": "output_contains", "value": "version"}],
            )
            result = VerificationRunner().run(recipe, Path(tmp), render_video=False)
            self.assertTrue(result.passed, f"steps: {result.steps}")
            self.assertIn("3.1.4", result.steps[0].detail or "")

    def test_wait_for_regex_process_mode_fails_on_missing_pattern(self):
        """wait_for_regex in process mode fails when regex does not match."""
        with tempfile.TemporaryDirectory() as tmp:
            recipe = Recipe(
                name="regex-process-miss",
                command=CommandSpec(
                    argv=[sys.executable, "-c", "print('nothing here')"],
                    pty=False,
                ),
                steps=[
                    {"action": "wait_for_regex", "pattern": r"never-zzz-\d+", "timeout_seconds": 2},
                ],
                assertions=[],
            )
            result = VerificationRunner().run(recipe, Path(tmp), render_video=False)
            self.assertFalse(result.passed)

    def test_wait_for_regex_process_mode_captures_named_groups(self):
        """Named groups are captured in process-mode detail."""
        with tempfile.TemporaryDirectory() as tmp:
            recipe = Recipe(
                name="regex-process-groups",
                command=CommandSpec(
                    argv=[sys.executable, "-c", "print('user: bob id: 77')"],
                    pty=False,
                ),
                steps=[
                    {"action": "wait_for_regex", "pattern": r"user: (?P<user>\w+) id: (?P<id>\d+)", "timeout_seconds": 5},
                ],
                assertions=[{"type": "output_contains", "value": "bob"}],
            )
            result = VerificationRunner().run(recipe, Path(tmp), render_video=False)
            self.assertTrue(result.passed)
            detail = result.steps[0].detail or ""
            self.assertIn("bob", detail)
            self.assertIn("77", detail)

    def test_wait_for_regex_zero_timeout_fails_fast(self):
        """Zero timeout_seconds must produce an immediate failure, not hang."""
        from termproof.builtin_steps import WaitForRegex
        import unittest.mock as mock
        step_action = WaitForRegex()
        fake_session = mock.Mock()
        fake_session.screen = "some screen"
        fake_session.raw_output = "some output"
        step = {"pattern": r"\d+", "timeout_seconds": 0}
        result = step_action.execute(fake_session, step, 1)
        self.assertFalse(result.passed)
        self.assertIn("timeout_seconds must be", result.detail or "")

    def test_wait_for_regex_negative_timeout_fails_fast(self):
        """Negative timeout_seconds must produce an immediate failure."""
        from termproof.builtin_steps import WaitForRegex
        import unittest.mock as mock
        step_action = WaitForRegex()
        fake_session = mock.Mock()
        fake_session.screen = "screen"
        step = {"pattern": r"\d+", "timeout_seconds": -1}
        result = step_action.execute(fake_session, step, 1)
        self.assertFalse(result.passed)
        self.assertIn("timeout_seconds must be", result.detail or "")

    def test_wait_for_regex_nan_timeout_fails_fast(self):
        """NaN timeout_seconds must produce an immediate failure, not hang."""
        from termproof.builtin_steps import WaitForRegex
        import unittest.mock as mock
        step_action = WaitForRegex()
        fake_session = mock.Mock()
        fake_session.screen = ""
        fake_session.raw_output = ""
        step = {"pattern": r"\d+", "timeout_seconds": float("nan")}
        result = step_action.execute(fake_session, step, 1)
        self.assertFalse(result.passed)
        self.assertIn("timeout", result.detail.lower())

    def test_wait_for_regex_infinity_timeout_fails_fast(self):
        """Inf timeout_seconds must produce an immediate failure."""
        from termproof.builtin_steps import WaitForRegex
        import unittest.mock as mock
        step_action = WaitForRegex()
        fake_session = mock.Mock()
        fake_session.screen = ""
        fake_session.raw_output = ""
        step = {"pattern": r"\d+", "timeout_seconds": float("inf")}
        result = step_action.execute(fake_session, step, 1)
        self.assertFalse(result.passed)
        self.assertIn("timeout", result.detail.lower())

    def test_wait_for_regex_non_string_pattern_fails_fast(self):
        """Non-string pattern (e.g. dict/list) must produce immediate failure."""
        from termproof.builtin_steps import WaitForRegex
        import unittest.mock as mock
        step_action = WaitForRegex()
        fake_session = mock.Mock()
        fake_session.screen = "screen"
        for bad_pattern in [42, {"key": "val"}, ["list"], True, None]:
            with self.subTest(pattern=bad_pattern):
                step = {"pattern": bad_pattern, "timeout_seconds": 1}
                result = step_action.execute(fake_session, step, 1)
                self.assertFalse(result.passed)
                self.assertIn("pattern", result.detail.lower())

    def test_wait_for_regex_non_numeric_timeout_fails_fast(self):
        """Non-numeric timeout_seconds must produce immediate failure."""
        from termproof.builtin_steps import WaitForRegex
        import unittest.mock as mock
        step_action = WaitForRegex()
        fake_session = mock.Mock()
        fake_session.screen = "screen"
        step = {"pattern": r"\d+", "timeout_seconds": "fast"}
        result = step_action.execute(fake_session, step, 1)
        self.assertFalse(result.passed)
        self.assertIn("timeout", result.detail.lower())

    def test_wait_for_regex_no_synthetic_boundary_match(self):
        """Pattern that would only match across a synthetic boundary must fail."""
        with tempfile.TemporaryDirectory() as tmp:
            # Output X in screen, Y in raw_output. A pattern matching
            # "X\nY" should NOT succeed because there is no real boundary.
            recipe = Recipe(
                name="no-boundary",
                command=CommandSpec(
                    argv=[sys.executable, "-c", "import sys; sys.stdout.write('FIRST'); sys.stderr.write('SECOND\\n')"],
                    pty=False,
                ),
                steps=[
                    {"action": "wait_for_regex", "pattern": r"FIRST.SECOND", "timeout_seconds": 5},
                ],
                assertions=[],
            )
            result = VerificationRunner().run(recipe, Path(tmp), render_video=False)
            # FIRST and SECOND are on separate streams; a DOTALL regex
            # crossing the concatenation boundary would be a false positive.
            self.assertFalse(result.passed, f"should not match across synthetic boundary; steps={result.steps}")

    # -- process-mode timing / streaming regression tests (CTO required) ---

    def test_process_mode_streaming_match_before_process_exit(self):
        """Command emits match at ~0s then sleeps 5s; step must observe match before exit."""
        import time as _time
        with tempfile.TemporaryDirectory() as tmp:
            recipe = Recipe(
                name="streaming-fast-match",
                command=CommandSpec(
                    argv=[
                        sys.executable, "-c",
                        "import sys, time; sys.stdout.write('EARLY\\n'); sys.stdout.flush(); time.sleep(5)",
                    ],
                    pty=False,
                ),
                steps=[
                    # timeout must exceed asciinema startup (~1.2s) so match is found
                    {"action": "wait_for_regex", "pattern": r"EARLY", "timeout_seconds": 3},
                ],
                assertions=[],
                expect_exit_code=None,
            )
            t0 = _time.monotonic()
            result = VerificationRunner().run(recipe, Path(tmp), render_video=False)
            elapsed = _time.monotonic() - t0
            self.assertTrue(result.passed, f"steps: {result.steps}")
            # Step finds match at ~1.2s (asciinema startup), then ~5s sleep for exit.
            self.assertLess(elapsed, 7.0, f"match should be observed before process sleep ends; elapsed={elapsed:.3f}s")
            self.assertIn("EARLY", result.steps[0].detail or "")

    def test_process_mode_step_deadline_fails_before_process_exit(self):
        """Step deadline 0.15s; match at ~1.5s (asciinema startup + 0.3s sleep). Step must fail on deadline."""
        import time as _time
        with tempfile.TemporaryDirectory() as tmp:
            recipe = Recipe(
                name="deadline-before-exit",
                command=CommandSpec(
                    argv=[
                        sys.executable, "-c",
                        "import time; time.sleep(0.3); print('TOO LATE')",
                    ],
                    pty=False,
                ),
                steps=[
                    # Step deadline is tight — output won't appear until ~1.5s
                    {"action": "wait_for_regex", "pattern": r"TOO LATE", "timeout_seconds": 0.15},
                ],
                assertions=[],
                expect_exit_code=None,
                timeout_seconds=5,  # overall cap: asciinema startup + 0.3s sleep + buffer
            )
            t0 = _time.monotonic()
            result = VerificationRunner().run(recipe, Path(tmp), render_video=False)
            elapsed = _time.monotonic() - t0
            self.assertFalse(result.passed, f"step should fail on deadline; steps={result.steps}")
            # Step fails at 0.15s deadline, then ~1.5s post-step teardown (asciinema overhead + process exit at 0.3s).
            self.assertLess(elapsed, 3.0, f"step should fail fast on deadline, elapsed={elapsed:.3f}s")
            self.assertIn("timed out", (result.steps[0].detail or "").lower())

    def test_process_mode_invalid_regex_fails_immediately(self):
        """Invalid regex must fail before any polling/waiting."""
        import time as _time
        with tempfile.TemporaryDirectory() as tmp:
            recipe = Recipe(
                name="invalid-regex-fast",
                command=CommandSpec(
                    argv=[sys.executable, "-c", "print('hello')"],
                    pty=False,
                ),
                steps=[
                    {"action": "wait_for_regex", "pattern": "[invalid", "timeout_seconds": 5},
                ],
                assertions=[],
                expect_exit_code=None,
                timeout_seconds=5,
            )
            t0 = _time.monotonic()
            result = VerificationRunner().run(recipe, Path(tmp), render_video=False)
            elapsed = _time.monotonic() - t0
            self.assertFalse(result.passed, f"invalid regex must fail; steps={result.steps}")
            # Immediate fail (no polling), then ~1.2s asciinema teardown.
            self.assertLess(elapsed, 3.0, f"invalid regex must fail without waiting; elapsed={elapsed:.3f}s")
            self.assertIn("invalid", (result.steps[0].detail or "").lower())

    # -- observable process-mode ordering proof ---------------------------------

    def test_process_mode_regex_match_before_next_action_observable(self):
        """Observable proof: step1 regex match must succeed BEFORE process reaches
        the late output that step2 waits for and misses.

        Process: prints 'HIT_NOW' at ~0s, sleeps 3s, prints 'TOO_LATE'.
        Step1: matches 'HIT_NOW' with 2s timeout → passes.
        Step2: waits for text 'TOO_LATE' with 0.5s timeout → fails (process still sleeping).
        If step1 had waited for process exit, it would see 'TOO_LATE' and step2 would pass.
        The fact that step2 FAILS proves step1 returned BEFORE the process reached 'TOO_LATE'.
        """
        with tempfile.TemporaryDirectory() as tmp:
            recipe = Recipe(
                name="observable-order-proof",
                command=CommandSpec(
                    argv=[
                        sys.executable, "-c",
                        "import sys, time; sys.stdout.write('HIT_NOW\\n'); sys.stdout.flush(); time.sleep(3); print('TOO_LATE')",
                    ],
                    pty=False,
                ),
                steps=[
                    {"name": "step1: match early output", "action": "wait_for_regex", "pattern": r"HIT_NOW", "timeout_seconds": 2},
                    {"name": "step2: fail on late output", "action": "wait_for_text", "text": "TOO_LATE", "timeout_seconds": 0.5},
                ],
                assertions=[{"type": "output_contains", "value": "HIT_NOW"}],
                expect_exit_code=None,
                timeout_seconds=10,
            )
            result = VerificationRunner().run(recipe, Path(tmp), render_video=False)
            # step1 must pass (matched early output)
            self.assertTrue(result.steps[0].passed, f"step1 should match HIT_NOW before process exit; steps={result.steps}")
            # step2 must fail (TOO_LATE hasn't appeared yet = step1 returned BEFORE process got there)
            self.assertFalse(result.steps[1].passed, f"step2 must fail waiting for TOO_LATE, proving step1 returned before process reached that point; steps={result.steps}")


if __name__ == "__main__":
    unittest.main()
