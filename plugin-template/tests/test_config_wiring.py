from __future__ import annotations

import tempfile
import textwrap
import unittest
from pathlib import Path

from termproof.config import load_config


class PluginConfigWiringTest(unittest.TestCase):
    def test_plugin_classes_loadable_via_config(self):
        with tempfile.TemporaryDirectory() as tmp:
            proj = Path(tmp)
            cfg_dir = proj / ".termproof"
            cfg_dir.mkdir()
            (cfg_dir / "config.yaml").write_text(
                textwrap.dedent("""
                steps:
                  wait_for_regex: termproof_my_plugin.steps:WaitForRegex
                assertions:
                  screen_count: termproof_my_plugin.assertions:ScreenCount
                reporters:
                  json_summary: termproof_my_plugin.reporters:JsonSummaryReporter
                """),
                encoding="utf-8",
            )
            cfg = load_config(project_path=proj)
            self.assertIn("wait_for_regex", cfg.steps)
            self.assertIn("screen_count", cfg.assertions)
            self.assertIn("json_summary", cfg.reporters)

            from termproof.runner import VerificationRunner

            runner = VerificationRunner(config=cfg)
            self.assertIn("wait_for_regex", runner.step_registry.names())
            self.assertIn("screen_count", runner.assertion_registry.names())
            self.assertIn("json_summary", runner.reporter_registry.names())


if __name__ == "__main__":
    unittest.main()
