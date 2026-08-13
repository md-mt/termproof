from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from termproof.builtin_assertions import JsonSchema
from termproof.config import VerifierConfig
from termproof.models import CommandSpec, Recipe


def _recipe(cwd: Path | None = None) -> Recipe:
    return Recipe(
        name="json-schema",
        command=CommandSpec(argv=["tool"], cwd=str(cwd) if cwd else None),
    )


class JsonSchemaAssertionTest(unittest.TestCase):
    def test_json_schema_registered_in_builtin_config(self) -> None:
        config = VerifierConfig.builtin()
        self.assertEqual(
            "termproof.builtin_assertions:JsonSchema",
            config.assertions["json_schema"],
        )

    def test_inline_schema_passes_valid_output(self) -> None:
        result = JsonSchema().evaluate(
            _recipe(),
            {
                "type": "json_schema",
                "schema": {
                    "type": "object",
                    "required": ["status"],
                    "properties": {"status": {"const": "ok"}},
                },
            },
            "",
            '{"status": "ok"}',
            0,
        )

        self.assertTrue(result.passed)
        self.assertEqual("matches JSON schema", result.detail)

    def test_inline_schema_reports_validation_failure(self) -> None:
        result = JsonSchema().evaluate(
            _recipe(),
            {
                "type": "json_schema",
                "schema": {
                    "type": "object",
                    "required": ["count"],
                    "properties": {"count": {"type": "integer"}},
                },
            },
            "",
            '{"count": "many"}',
            0,
        )

        self.assertFalse(result.passed)
        self.assertIn("schema validation failed at count", result.detail)

    def test_schema_path_resolves_from_recipe_cwd(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            cwd = Path(tmp)
            schema_path = cwd / "output.schema.json"
            schema_path.write_text(
                json.dumps(
                    {
                        "type": "object",
                        "required": ["items"],
                        "properties": {
                            "items": {
                                "type": "array",
                                "items": {"type": "string"},
                            }
                        },
                    }
                ),
                encoding="utf-8",
            )

            result = JsonSchema().evaluate(
                _recipe(cwd),
                {"type": "json_schema", "schema": "output.schema.json"},
                "",
                '{"items": ["one", "two"]}',
                0,
            )

        self.assertTrue(result.passed)

    def test_invalid_json_output_fails(self) -> None:
        result = JsonSchema().evaluate(
            _recipe(),
            {"type": "json_schema", "schema": {"type": "object"}},
            "",
            "not json",
            0,
        )

        self.assertFalse(result.passed)
        self.assertEqual("invalid JSON output: Expecting value", result.detail)


if __name__ == "__main__":
    unittest.main()
