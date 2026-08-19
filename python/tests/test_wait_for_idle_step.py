from __future__ import annotations

import unittest
from unittest.mock import Mock

from termproof.builtin_steps import WaitForIdle


class WaitForIdleStepDetailTest(unittest.TestCase):
    """The failure detail distinguishes a silent session from an unsettled one."""

    def _failure_detail(self, raw_output: str) -> str:
        session = Mock()
        session.screen = ""
        # No grid: this fake models a session that cannot report one, so the
        # step falls back to the screen text exactly as it did before.
        session.screen_attributed = None
        session.raw_output = raw_output
        session.wait_for_idle.return_value = False
        return WaitForIdle().execute(session, {"stable_seconds": 0.5}, 1).detail

    def test_detail_reports_no_output_when_session_was_silent(self) -> None:
        self.assertEqual(
            self._failure_detail(""), "no output observed from the session"
        )

    def test_detail_reports_idle_timeout_when_output_never_settled(self) -> None:
        self.assertEqual(self._failure_detail("busy"), "timed out waiting for idle")

    def test_detail_reports_stable_window_on_success(self) -> None:
        session = Mock()
        session.screen = ""
        session.screen_attributed = None
        session.raw_output = "hello"
        session.wait_for_idle.return_value = True
        result = WaitForIdle().execute(session, {"stable_seconds": 0.5}, 1)
        self.assertTrue(result.passed)
        self.assertEqual(result.detail, "stable for 0.5s")
