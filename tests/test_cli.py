from __future__ import annotations

import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from termproof.cli import main


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


if __name__ == "__main__":
    unittest.main()
