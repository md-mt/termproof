from __future__ import annotations

import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from termproof.cli import main
from termproof.config import VerifierConfig
from termproof.models import recipe_from_mapping
from termproof.recipe_schema import has_errors, validate_recipe_mapping


def _recipe(**overrides):
    data = {
        "recipe_version": 1,
        "name": "valid",
        "command": {"argv": ["python3", "-c", "print('ok')"], "pty": False},
        "steps": [{"action": "wait_for_text", "text": "ok"}],
        "assertions": [{"type": "output_contains", "value": "ok"}],
    }
    data.update(overrides)
    return data


class RecipeValidationTest(unittest.TestCase):
    def test_recipe_version_defaults_to_one_for_legacy_recipes(self) -> None:
        recipe = recipe_from_mapping(
            {
                "name": "legacy",
                "command": {"argv": ["echo", "ok"]},
            }
        )
        self.assertEqual(1, recipe.recipe_version)

    def test_recipe_loader_rejects_unsupported_recipe_version(self) -> None:
        with self.assertRaisesRegex(ValueError, "unsupported recipe_version"):
            recipe_from_mapping(
                {
                    "recipe_version": True,
                    "name": "bad",
                    "command": {"argv": ["echo", "ok"]},
                }
            )

    def test_valid_recipe_has_no_errors(self) -> None:
        issues = validate_recipe_mapping(_recipe(), VerifierConfig.builtin())
        self.assertEqual([], issues)

    def test_missing_recipe_version_warns_without_failing(self) -> None:
        data = _recipe()
        data.pop("recipe_version")
        issues = validate_recipe_mapping(data, VerifierConfig.builtin())
        self.assertFalse(has_errors(issues))
        self.assertEqual(["warning"], [issue.severity for issue in issues])

    def test_unknown_plugin_names_are_errors(self) -> None:
        issues = validate_recipe_mapping(
            _recipe(
                steps=[{"action": "missing_step"}],
                assertions=[{"type": "missing_assertion"}],
            ),
            VerifierConfig.builtin(),
        )
        self.assertTrue(has_errors(issues))
        messages = "\n".join(issue.message for issue in issues)
        self.assertIn("unknown step action", messages)
        self.assertIn("unknown assertion type", messages)

    def test_boolean_recipe_version_is_invalid(self) -> None:
        issues = validate_recipe_mapping(
            _recipe(recipe_version=True),
            VerifierConfig.builtin(),
        )
        self.assertTrue(has_errors(issues))

    def test_validate_cli_returns_nonzero_for_invalid_recipe(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.recipe.json"
            path.write_text(
                '{"recipe_version": 1, "name": "bad", "command": {"argv": []}}',
                encoding="utf-8",
            )
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = main(["validate", str(path)])
        self.assertEqual(1, code)
        self.assertIn("ERROR", output.getvalue())

    def test_validate_cli_accepts_recipe_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "ok.recipe.json"
            path.write_text(
                """{
  "recipe_version": 1,
  "name": "ok",
  "command": {"argv": ["python3", "-c", "print('ok')"], "pty": false}
}
""",
                encoding="utf-8",
            )
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                code = main(["validate", tmp])
        self.assertEqual(0, code)
        self.assertIn("PASS", output.getvalue())


if __name__ == "__main__":
    unittest.main()
