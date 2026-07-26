from __future__ import annotations

import unittest
from pathlib import Path

from termproof.registry import load_recipes


class ExampleRecipeTest(unittest.TestCase):
    def test_pi_workflow_recipes_load(self) -> None:
        recipes = load_recipes([Path("examples")])
        names = {recipe.name for recipe in recipes}
        self.assertIn("pi-workflow-cli-capability-map", names)
        self.assertIn("pi-workflow-package-lifecycle", names)
        self.assertIn("pi-workflow-readonly-review", names)
        self.assertIn("pi-workflow-guarded-edit", names)
        self.assertIn("pi-workflow-session-resume-export", names)
        self.assertIn("pi-workflow-model-context", names)
        self.assertIn("generic-tui-workflow", names)


if __name__ == "__main__":
    unittest.main()
