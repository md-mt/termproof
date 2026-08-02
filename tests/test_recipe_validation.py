from __future__ import annotations

import contextlib
import io
import tempfile
import unittest
from pathlib import Path

from termproof.cli import main
from termproof.config import VerifierConfig
from termproof.models import recipe_from_mapping
from termproof.recipe_schema import (
    has_errors,
    load_recipe_schema,
    validate_recipe_mapping,
)


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


class RecipeSchemaStructuralTest(unittest.TestCase):
    """Lock in the structural verdicts now delegated to the canonical JSON schema."""

    def _errors(self, **overrides) -> list[str]:
        issues = validate_recipe_mapping(_recipe(**overrides), VerifierConfig.builtin())
        return [issue.path for issue in issues if issue.severity == "error"]

    def test_canonical_schema_loads_as_resource(self) -> None:
        schema = load_recipe_schema()
        self.assertEqual(1, schema["properties"]["recipe_version"]["const"])
        self.assertEqual(["name", "command"], schema["required"])

    def test_structurally_valid_recipe_passes(self) -> None:
        self.assertEqual([], self._errors())

    def test_recipe_version_two_is_error(self) -> None:
        self.assertTrue(has_errors(validate_recipe_mapping(_recipe(recipe_version=2), VerifierConfig.builtin())))

    def test_empty_name_is_error(self) -> None:
        self.assertTrue(self._errors(name=""))

    def test_missing_command_is_error(self) -> None:
        data = _recipe()
        data.pop("command")
        self.assertTrue(has_errors(validate_recipe_mapping(data, VerifierConfig.builtin())))

    def test_missing_command_argv_reports_command_argv_path(self) -> None:
        # Missing-required diagnostics inside nested objects must use the same
        # first-component formatting as the legacy validator: no leading dot.
        self.assertEqual(["command.argv"], self._errors(command={}))

    def test_missing_step_action_reports_steps_0_action_path(self) -> None:
        self.assertEqual(["steps[0].action"], self._errors(steps=[{}]))

    def test_missing_assertion_type_reports_assertions_0_type_path(self) -> None:
        self.assertEqual(["assertions[0].type"], self._errors(assertions=[{}]))

    def test_command_not_object_is_error(self) -> None:
        self.assertTrue(self._errors(command="echo"))

    def test_empty_argv_is_error(self) -> None:
        self.assertTrue(self._errors(command={"argv": []}))

    def test_non_string_argv_is_error(self) -> None:
        self.assertTrue(self._errors(command={"argv": [1, 2]}))

    def test_non_string_env_value_is_error(self) -> None:
        self.assertTrue(self._errors(command={"argv": ["a"], "env": {"K": 1}}))

    def test_non_bool_pty_is_error(self) -> None:
        self.assertTrue(self._errors(command={"argv": ["a"], "pty": "yes"}))

    def test_non_string_cwd_is_error(self) -> None:
        self.assertTrue(self._errors(command={"argv": ["a"], "cwd": 5}))

    def test_null_cwd_is_allowed(self) -> None:
        self.assertEqual([], self._errors(command={"argv": ["a"], "cwd": None}))

    def test_non_positive_timeout_is_error(self) -> None:
        self.assertTrue(self._errors(timeout_seconds=0))

    def test_bool_timeout_is_error(self) -> None:
        self.assertTrue(self._errors(timeout_seconds=True))

    def test_non_positive_cols_is_error(self) -> None:
        self.assertTrue(self._errors(cols=0))

    def test_bool_rows_is_error(self) -> None:
        self.assertTrue(self._errors(rows=True))

    def test_non_integer_expect_exit_code_is_error(self) -> None:
        self.assertTrue(self._errors(expect_exit_code=1.5))

    def test_null_expect_exit_code_is_allowed(self) -> None:
        self.assertEqual([], self._errors(expect_exit_code=None))

    def test_non_string_list_checks_is_error(self) -> None:
        self.assertTrue(self._errors(checks=[1]))

    def test_non_string_list_ci_paths_is_error(self) -> None:
        self.assertTrue(self._errors(ci_paths="a"))

    def test_non_object_operator_is_error(self) -> None:
        self.assertTrue(self._errors(operator=[]))

    def test_non_list_renderer_argv_is_error(self) -> None:
        self.assertTrue(self._errors(renderers={"default": "x"}))

    def test_non_positive_step_timeout_is_error(self) -> None:
        self.assertTrue(
            self._errors(
                steps=[{"action": "wait_for_text", "text": "ok", "timeout_seconds": 0}]
            )
        )


if __name__ == "__main__":
    unittest.main()
