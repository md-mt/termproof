from __future__ import annotations

import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from termproof.cli import main


class DemoCommandTest(unittest.TestCase):
    def test_demo_creates_recipe_and_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "demo_out"
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                code = main(["demo", "--out", str(out), "--no-open"])
            # demo should succeed exit code 0
            self.assertEqual(0, code, f"stdout: {buf.getvalue()}")
            self.assertTrue(out.exists(), "out dir should exist")
            # should have report
            self.assertTrue((out / "latest-report.md").exists() or any(out.rglob("*.md")))
            output = buf.getvalue()
            # should mention evidence
            self.assertIn("evidence", output.lower() or "report" in output.lower())

    def test_demo_exercises_all_steps_and_assertions(self):
        # check that demo_tui exists and recipe covers all step and assertion types
        from termproof import demo as demo_module
        recipe = demo_module.build_demo_recipe(out_dir=Path("/tmp/demo_test"))
        step_actions = {s["action"] for s in recipe.steps}
        assertion_types = {a["type"] for a in recipe.assertions}
        # must include every built-in step
        for expected in ["wait_for_text", "wait_for_idle", "send_text", "send_line", "press", "sleep", "wait_for_regex"]:
            self.assertIn(expected, step_actions, f"missing step {expected}")
        for expected in ["output_contains", "output_not_contains", "screen_contains", "screen_not_contains", "exit_code", "file_exists", "file_contains"]:
            self.assertIn(expected, assertion_types, f"missing assertion {expected}")


if __name__ == "__main__":
    unittest.main()
