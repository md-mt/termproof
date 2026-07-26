from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from termproof.scaffold import write_recipe_pack


class ScaffoldTest(unittest.TestCase):
    def test_write_recipe_pack_creates_generic_recipe(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            recipe_path = write_recipe_pack(
                Path(tmp),
                "demo-tui",
                "python3 -m demo",
                pty=True,
                priority="P1",
                cols=120,
                rows=40,
            )
            recipe = json.loads(recipe_path.read_text(encoding="utf-8"))
            self.assertEqual("demo-tui", recipe["name"])
            self.assertEqual(["python3", "-m", "demo"], recipe["command"]["argv"])
            self.assertTrue(recipe["command"]["pty"])
            self.assertEqual("P1", recipe["priority"])
            self.assertTrue((Path(tmp) / "README.md").exists())


if __name__ == "__main__":
    unittest.main()
