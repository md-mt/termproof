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
    def test_matches_screen(self):
        sess = _fake_session(screen="Dashboard 10/20 ready")
        step = {"pattern": r"Dashboard \d+/\d+", "timeout_seconds": 0.1}
        result = WaitForRegex().execute(sess, step, 1)
        self.assertTrue(result.passed)
        self.assertIn("matched", result.detail)

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

    def test_times_out_when_no_match(self):
        sess = _fake_session(screen="nope", raw="nope")
        step = {"pattern": "never", "timeout_seconds": 0.05, "poll_seconds": 0.01}
        result = WaitForRegex().execute(sess, step, 1)
        self.assertFalse(result.passed)

    def test_ignore_case_flag(self):
        sess = _fake_session(screen="HELLO")
        step = {"pattern": "hello", "ignore_case": True, "timeout_seconds": 0.1}
        result = WaitForRegex().execute(sess, step, 1)
        self.assertTrue(result.passed)


if __name__ == "__main__":
    unittest.main()
