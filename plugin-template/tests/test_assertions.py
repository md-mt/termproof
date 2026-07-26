from __future__ import annotations

import unittest

from termproof.models import CommandSpec, Recipe

from termproof_my_plugin.assertions import DurationUnder, ScreenCount


class DurationUnderTest(unittest.TestCase):
    def test_missing_value(self):
        recipe = Recipe(name="r", command=CommandSpec(argv=["echo", "hi"]))
        result = DurationUnder().evaluate(recipe, {}, "screen", "raw", 0)
        self.assertFalse(result.passed)

    def test_invalid_budget(self):
        recipe = Recipe(name="r", command=CommandSpec(argv=["echo", "hi"]))
        result = DurationUnder().evaluate(recipe, {"value": "nope"}, "screen", "raw", 0)
        self.assertFalse(result.passed)

    def test_budget_without_timing_file_passes_soft(self):
        recipe = Recipe(name="r", command=CommandSpec(argv=["echo", "hi"]))
        result = DurationUnder().evaluate(recipe, {"value": 10}, "screen", "raw", 0)
        self.assertTrue(result.passed)

    def test_screen_count_missing_pattern(self):
        recipe = Recipe(name="r", command=CommandSpec(argv=["echo", "hi"]))
        result = ScreenCount().evaluate(recipe, {}, "screen", "raw", 0)
        self.assertFalse(result.passed)

    def test_screen_count_max_enforced(self):
        recipe = Recipe(name="r", command=CommandSpec(argv=["echo", "hi"]))
        result = ScreenCount().evaluate(recipe, {"pattern": "TODO", "max": 0}, "TODO TODO", "raw", 0)
        self.assertFalse(result.passed)

    def test_screen_count_min_max_ok(self):
        recipe = Recipe(name="r", command=CommandSpec(argv=["echo", "hi"]))
        result = ScreenCount().evaluate(recipe, {"pattern": "OK", "min": 1, "max": 2}, "OK OK", "raw", 0)
        self.assertTrue(result.passed)

    def test_screen_count_invalid_regex(self):
        recipe = Recipe(name="r", command=CommandSpec(argv=["echo", "hi"]))
        result = ScreenCount().evaluate(recipe, {"pattern": "[bad"}, "screen", "raw", 0)
        self.assertFalse(result.passed)


if __name__ == "__main__":
    unittest.main()
