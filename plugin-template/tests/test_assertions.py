from __future__ import annotations

import unittest

from termproof.models import CommandSpec, Recipe

from termproof_my_plugin.assertions import ScreenCount


def _recipe(name: str = "r") -> Recipe:
    return Recipe(name=name, command=CommandSpec(argv=["echo", "hi"]))


class ScreenCountTest(unittest.TestCase):
    # --- basic happy path ------------------------------------------------------
    def test_matches_between_min_and_max(self):
        r = ScreenCount().evaluate(
            _recipe(), {"pattern": "OK", "min": 1, "max": 2}, "OK OK", "", 0
        )
        self.assertTrue(r.passed)

    def test_exactly_min(self):
        r = ScreenCount().evaluate(
            _recipe(), {"pattern": "OK", "min": 2}, "OK OK", "", 0
        )
        self.assertTrue(r.passed)

    def test_exactly_max(self):
        r = ScreenCount().evaluate(
            _recipe(), {"pattern": "OK", "max": 2}, "OK OK", "", 0
        )
        self.assertTrue(r.passed)

    # --- failures ---------------------------------------------------------------
    def test_below_min(self):
        r = ScreenCount().evaluate(
            _recipe(), {"pattern": "OK", "min": 3}, "OK OK", "", 0
        )
        self.assertFalse(r.passed)

    def test_above_max(self):
        r = ScreenCount().evaluate(
            _recipe(), {"pattern": "OK", "max": 1}, "OK OK", "", 0
        )
        self.assertFalse(r.passed)

    # --- missing pattern --------------------------------------------------------
    def test_missing_pattern(self):
        r = ScreenCount().evaluate(_recipe(), {}, "screen", "", 0)
        self.assertFalse(r.passed)
        self.assertIn("missing", r.detail)

    def test_empty_string_pattern(self):
        r = ScreenCount().evaluate(
            _recipe(), {"pattern": "", "max": 0}, "screen", "", 0
        )
        self.assertFalse(r.passed)
        self.assertIn("missing", r.detail)

    # --- non-string pattern -----------------------------------------------------
    def test_non_string_pattern(self):
        r = ScreenCount().evaluate(
            _recipe(), {"pattern": 123, "max": 0}, "screen", "", 0
        )
        self.assertFalse(r.passed)
        self.assertIn("must be a string", r.detail)

    # --- invalid regex ---------------------------------------------------------
    def test_invalid_regex(self):
        r = ScreenCount().evaluate(
            _recipe(), {"pattern": "[bad", "max": 0}, "screen", "", 0
        )
        self.assertFalse(r.passed)
        self.assertIn("invalid regex", r.detail)

    # --- missing bounds ---------------------------------------------------------
    def test_missing_both_bounds(self):
        r = ScreenCount().evaluate(
            _recipe(), {"pattern": "OK"}, "OK", "", 0
        )
        self.assertFalse(r.passed)
        self.assertIn("at least one", r.detail)

    # --- invalid bound types ----------------------------------------------------
    def test_boolean_min(self):
        r = ScreenCount().evaluate(
            _recipe(), {"pattern": "OK", "min": True}, "OK", "", 0
        )
        self.assertFalse(r.passed)
        self.assertIn("not bool", r.detail)

    def test_boolean_max(self):
        r = ScreenCount().evaluate(
            _recipe(), {"pattern": "OK", "max": False}, "OK", "", 0
        )
        self.assertFalse(r.passed)
        self.assertIn("not bool", r.detail)

    def test_string_min(self):
        r = ScreenCount().evaluate(
            _recipe(), {"pattern": "OK", "min": "nope"}, "OK", "", 0
        )
        self.assertFalse(r.passed)
        self.assertIn("expected integer", r.detail)

    def test_float_max(self):
        r = ScreenCount().evaluate(
            _recipe(), {"pattern": "OK", "max": 2.7}, "OK OK OK", "", 0
        )
        # 2.7 -> int(2.7) = 2, 3 matches > 2 -> fail
        self.assertFalse(r.passed)

    # --- negative bounds --------------------------------------------------------
    def test_negative_min(self):
        r = ScreenCount().evaluate(
            _recipe(), {"pattern": "OK", "min": -1}, "OK", "", 0
        )
        self.assertFalse(r.passed)
        self.assertIn("must be >= 0", r.detail)

    def test_negative_max(self):
        r = ScreenCount().evaluate(
            _recipe(), {"pattern": "OK", "max": -5}, "OK", "", 0
        )
        self.assertFalse(r.passed)
        self.assertIn("must be >= 0", r.detail)

    # --- min > max --------------------------------------------------------------
    def test_min_greater_than_max(self):
        r = ScreenCount().evaluate(
            _recipe(), {"pattern": "OK", "min": 5, "max": 3}, "OK", "", 0
        )
        self.assertFalse(r.passed)
        self.assertIn("min (5) > max (3)", r.detail)

    # --- zero matches -----------------------------------------------------------
    def test_zero_count_min_0(self):
        r = ScreenCount().evaluate(
            _recipe(), {"pattern": "MISSING", "min": 0}, "screen", "", 0
        )
        self.assertTrue(r.passed)

    def test_zero_count_max_0(self):
        r = ScreenCount().evaluate(
            _recipe(), {"pattern": "MISSING", "max": 0}, "screen", "", 0
        )
        self.assertTrue(r.passed)


if __name__ == "__main__":
    unittest.main()
