from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from termproof_my_plugin.steps import WaitForRegex


def _fake_session(screen="hello world", raw="raw log", alive=False):
    sess = MagicMock()
    sess.screen = screen
    sess.raw_output = raw
    sess.is_alive.return_value = alive
    sess.read_available = MagicMock()
    return sess


class WaitForRegexTest(unittest.TestCase):
    # --- basic happy path ------------------------------------------------------
    def test_matches_screen(self):
        sess = _fake_session(screen="Dashboard 10/20 ready")
        step = {"pattern": r"Dashboard \d+/\d+", "timeout_seconds": 0.1}
        result = WaitForRegex().execute(sess, step, 1)
        self.assertTrue(result.passed)
        self.assertIn("matched", result.detail)

    def test_matches_raw_output(self):
        sess = _fake_session(screen="nope", raw="Dashboard 10/20 ready")
        step = {"pattern": r"Dashboard \d+/\d+", "timeout_seconds": 0.1}
        result = WaitForRegex().execute(sess, step, 1)
        self.assertTrue(result.passed)

    def test_ignore_case_flag(self):
        sess = _fake_session(screen="HELLO")
        step = {"pattern": "hello", "ignore_case": True, "timeout_seconds": 0.1}
        result = WaitForRegex().execute(sess, step, 1)
        self.assertTrue(result.passed)

    def test_multiline_flag(self):
        sess = _fake_session(screen="line1\nline2")
        step = {"pattern": "^line2$", "multiline": True, "timeout_seconds": 0.1}
        result = WaitForRegex().execute(sess, step, 1)
        self.assertTrue(result.passed)

    def test_dotall_flag(self):
        sess = _fake_session(screen="a\nb")
        step = {"pattern": "a.b", "dotall": True, "timeout_seconds": 0.1}
        result = WaitForRegex().execute(sess, step, 1)
        self.assertTrue(result.passed)

    # --- search_raw_output=false on live path ----------------------------------
    def test_search_raw_false_does_not_match_raw(self):
        # raw has the match, screen does not; with search_raw=False it should NOT match
        sess = _fake_session(screen="nope", raw="Dashboard 10/20 ready")
        step = {
            "pattern": r"Dashboard \d+/\d+",
            "search_raw_output": False,
            "timeout_seconds": 0.1,
        }
        result = WaitForRegex().execute(sess, step, 1)
        self.assertFalse(result.passed)
        self.assertIn("timed out", result.detail)

    def test_search_raw_false_matches_screen_only(self):
        sess = _fake_session(screen="match here", raw="also match here")
        step = {
            "pattern": "match here",
            "search_raw_output": False,
            "timeout_seconds": 0.1,
        }
        result = WaitForRegex().execute(sess, step, 1)
        self.assertTrue(result.passed)

    # --- search_raw_output=false on process-exit path --------------------------
    def test_exit_path_honors_search_raw_false(self):
        # Session is alive on first check, then dies. Screen never matches.
        # With search_raw=False, raw output should NOT be searched at exit.
        sess = _fake_session(
            screen="nope", raw="Dashboard 10/20 ready", alive=True
        )
        sess.is_alive.side_effect = [True, False]  # alive, then dead
        step = {
            "pattern": r"Dashboard \d+/\d+",
            "search_raw_output": False,
            "timeout_seconds": 0.05,
            "poll_seconds": 0.01,
        }
        result = WaitForRegex().execute(sess, step, 1)
        self.assertFalse(result.passed)
        self.assertIn("timed out", result.detail)

    def test_exit_path_matches_screen_when_dead(self):
        # Session is alive on first check (screen doesn't match), then dies.
        # read_available(poll) on first iteration changes nothing.
        # After exit, read_available(0) updates screen to show match.
        sess = _fake_session(
            screen="waiting...", raw="junk", alive=True
        )
        sess.is_alive.side_effect = [True, False]  # alive, then dead
        # Make read_available(0) update the screen on exit
        def _read_available(timeout):
            if timeout == 0:
                sess.screen = "Dashboard 10/20 ready"
        sess.read_available.side_effect = _read_available
        step = {
            "pattern": r"Dashboard \d+/\d+",
            "search_raw_output": False,
            "timeout_seconds": 0.05,
            "poll_seconds": 0.01,
        }
        result = WaitForRegex().execute(sess, step, 1)
        self.assertTrue(result.passed)
        self.assertIn("matched after process exit", result.detail)

    def test_exit_path_with_search_raw_true_matches_raw(self):
        # Session is alive on first check (raw doesn't match), then dies.
        # After exit, read_available(0) updates raw_output to show match.
        sess = _fake_session(
            screen="nope", raw="nope nope", alive=True
        )
        sess.is_alive.side_effect = [True, False]  # alive, then dead
        def _read_available(timeout):
            if timeout == 0:
                sess.raw_output = "Dashboard 10/20 done"
        sess.read_available.side_effect = _read_available
        step = {
            "pattern": r"Dashboard \d+/\d+",
            "search_raw_output": True,
            "timeout_seconds": 0.05,
            "poll_seconds": 0.01,
        }
        result = WaitForRegex().execute(sess, step, 1)
        self.assertTrue(result.passed)
        self.assertIn("matched after process exit", result.detail)

    # --- errors ----------------------------------------------------------------
    def test_invalid_regex_fails(self):
        sess = _fake_session()
        step = {"pattern": "[invalid", "timeout_seconds": 0.1}
        result = WaitForRegex().execute(sess, step, 1)
        self.assertFalse(result.passed)
        self.assertIn("invalid regex", result.detail)

    def test_missing_pattern(self):
        sess = _fake_session()
        result = WaitForRegex().execute(sess, {}, 1)
        self.assertFalse(result.passed)
        self.assertIn("missing", result.detail)

    def test_non_string_pattern(self):
        sess = _fake_session()
        step = {"pattern": 42, "timeout_seconds": 0.1}
        result = WaitForRegex().execute(sess, step, 1)
        self.assertFalse(result.passed)
        self.assertIn("must be a string", result.detail)

    def test_times_out_when_no_match(self):
        sess = _fake_session(screen="nope", raw="nope")
        step = {"pattern": "never", "timeout_seconds": 0.05, "poll_seconds": 0.01}
        result = WaitForRegex().execute(sess, step, 1)
        self.assertFalse(result.passed)
        self.assertIn("timed out", result.detail)

    # --- invalid numeric controls ----------------------------------------------
    def test_invalid_timeout(self):
        sess = _fake_session()
        step = {"pattern": "x", "timeout_seconds": "bad"}
        result = WaitForRegex().execute(sess, step, 1)
        self.assertFalse(result.passed)
        self.assertIn("invalid timeout_seconds", result.detail)

    def test_negative_timeout(self):
        sess = _fake_session()
        step = {"pattern": "x", "timeout_seconds": -1}
        result = WaitForRegex().execute(sess, step, 1)
        self.assertFalse(result.passed)
        self.assertIn("must be >= 0", result.detail)

    def test_invalid_poll(self):
        sess = _fake_session()
        step = {"pattern": "x", "poll_seconds": "nope"}
        result = WaitForRegex().execute(sess, step, 1)
        self.assertFalse(result.passed)
        self.assertIn("invalid poll_seconds", result.detail)

    def test_nonpositive_poll(self):
        sess = _fake_session()
        step = {"pattern": "x", "poll_seconds": 0}
        result = WaitForRegex().execute(sess, step, 1)
        self.assertFalse(result.passed)
        self.assertIn("must be > 0", result.detail)

    def test_zero_timeout_immediate(self):
        # zero timeout means deadline is immediate; no match -> timed out
        sess = _fake_session(screen="nope", raw="nope")
        step = {"pattern": "never", "timeout_seconds": 0, "poll_seconds": 0.01}
        result = WaitForRegex().execute(sess, step, 1)
        self.assertFalse(result.passed)
        self.assertIn("timed out", result.detail)


if __name__ == "__main__":
    unittest.main()
