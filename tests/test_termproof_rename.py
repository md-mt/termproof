from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class TermProofRenameTest(unittest.TestCase):
    def test_termproof_is_the_public_import_package(self) -> None:
        from termproof import VerificationRunner

        self.assertTrue(callable(VerificationRunner))

    def test_config_cascades_legacy_paths_before_termproof_paths(self) -> None:
        from termproof.config import load_config

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            home = root / "home"
            project = root / "project"
            legacy_user = home / ".config" / "tui-verifier"
            current_user = home / ".config" / "termproof"
            legacy_project = project / ".tui-verifier"
            current_project = project / ".termproof"
            for directory in (
                legacy_user,
                current_user,
                legacy_project,
                current_project,
            ):
                directory.mkdir(parents=True)

            (legacy_user / "config.yaml").write_text(
                "defaults:\n  timeout_seconds: 10\n  rows: 40\n",
                encoding="utf-8",
            )
            (current_user / "config.yaml").write_text(
                "defaults:\n  timeout_seconds: 20\n",
                encoding="utf-8",
            )
            (legacy_project / "config.yaml").write_text(
                "defaults:\n  cols: 110\n",
                encoding="utf-8",
            )
            (current_project / "config.yaml").write_text(
                "defaults:\n  cols: 120\n",
                encoding="utf-8",
            )

            with patch("termproof.config.Path.home", return_value=home):
                config = load_config(project_path=project)

            self.assertEqual(20.0, config.defaults.timeout_seconds)
            self.assertEqual(40, config.defaults.rows)
            self.assertEqual(120, config.defaults.cols)

    def test_legacy_plugin_references_resolve_through_compatibility_alias(self) -> None:
        from termproof.config import VerifierConfig
        from termproof.runner import VerificationRunner

        config = VerifierConfig.builtin()
        config.steps["legacy_sleep"] = "tui_verifier.builtin_steps:Sleep"

        runner = VerificationRunner(config=config)

        self.assertEqual("Sleep", type(runner.step_registry.get("legacy_sleep")).__name__)


if __name__ == "__main__":
    unittest.main()
