from __future__ import annotations

import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from termproof.cli import main
from termproof.models import RunResult


class CliTest(unittest.TestCase):
    def test_init_command_creates_recipe(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with contextlib.redirect_stdout(io.StringIO()):
                exit_code = main(
                    [
                        "init",
                        str(Path(tmp) / "recipes"),
                        "--name",
                        "demo-tui",
                        "--command",
                        "python3 -c 'print(42)'",
                        "--non-pty",
                    ]
                )
            self.assertEqual(0, exit_code)
            self.assertTrue((Path(tmp) / "recipes" / "demo-tui.recipe.json").exists())

    def test_run_config_file_overrides_cascaded_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            recipe_path = root / "recipe.json"
            recipe_path.write_text(
                """{
  "name": "configured-run",
  "command": {"argv": ["python3", "-c", "print('ok')"], "pty": false}
}
""",
                encoding="utf-8",
            )
            config_path = root / "explicit-config.yaml"
            config_path.write_text("defaults:\n  rows: 77\n", encoding="utf-8")
            result = RunResult(
                recipe_name="configured-run",
                passed=True,
                exit_code=0,
                duration_seconds=0.0,
                priority="P2",
                execution="scripted",
                renderer="default",
                score=1.0,
                steps=[],
                assertions=[],
                artifacts={},
            )
            with patch("termproof.cli.VerificationRunner") as runner_class:
                runner = runner_class.return_value
                runner.run.return_value = result
                runner.reporter_registry.get.return_value.generate.return_value = "report"
                with contextlib.redirect_stdout(io.StringIO()):
                    exit_code = main(
                        [
                            "run",
                            str(recipe_path),
                            "--config",
                            str(config_path),
                            "--out",
                            str(root / "out"),
                        ]
                    )

            self.assertEqual(0, exit_code)
            self.assertEqual(
                77, runner_class.call_args.kwargs["config"].defaults.rows
            )


if __name__ == "__main__":
    unittest.main()
