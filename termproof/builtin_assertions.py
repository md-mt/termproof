from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import jsonschema

from .models import AssertionResult, Recipe
from .protocols import AssertionType


def _contains(
    name: str,
    haystack: str,
    needle: str,
    should_contain: bool,
    custom_detail: str | None = None,
) -> AssertionResult:
    found = needle in haystack
    passed = found if should_contain else not found
    expectation = "contains" if should_contain else "does not contain"
    detail = custom_detail or f"{expectation} {needle!r}"
    return AssertionResult(name, passed, detail)


def _recipe_path(recipe: Recipe, path: str) -> Path:
    candidate = Path(path)
    if candidate.is_absolute():
        return candidate
    base = Path(recipe.command.cwd or ".")
    return base / candidate


def _json_schema(
    recipe: Recipe,
    assertion: dict[str, Any],
) -> tuple[dict[str, Any] | None, str | None]:
    schema_path = assertion.get("schema_path")
    schema = assertion.get("schema")
    if schema_path is not None:
        path = _recipe_path(recipe, str(schema_path))
        try:
            return json.loads(path.read_text(encoding="utf-8")), None
        except OSError as exc:
            return None, f"schema file unreadable: {exc}"
        except json.JSONDecodeError as exc:
            return None, f"invalid schema JSON: {exc.msg}"
    if isinstance(schema, dict):
        return schema, None
    if isinstance(schema, str):
        path = _recipe_path(recipe, schema)
        try:
            return json.loads(path.read_text(encoding="utf-8")), None
        except OSError as exc:
            return None, f"schema file unreadable: {exc}"
        except json.JSONDecodeError as exc:
            return None, f"invalid schema JSON: {exc.msg}"
    return None, "json_schema requires an object schema or schema path"


class OutputContains:
    name = "output_contains"

    def evaluate(
        self,
        recipe: Recipe,
        assertion: dict[str, Any],
        screen: str,
        raw_output: str,
        exit_code: int | None,
    ) -> AssertionResult:
        return _contains(
            assertion.get("name", self.name),
            raw_output,
            assertion["value"],
            True,
            assertion.get("detail"),
        )


class OutputNotContains:
    name = "output_not_contains"

    def evaluate(
        self,
        recipe: Recipe,
        assertion: dict[str, Any],
        screen: str,
        raw_output: str,
        exit_code: int | None,
    ) -> AssertionResult:
        return _contains(
            assertion.get("name", self.name),
            raw_output,
            assertion["value"],
            False,
            assertion.get("detail"),
        )


class ScreenContains:
    name = "screen_contains"

    def evaluate(
        self,
        recipe: Recipe,
        assertion: dict[str, Any],
        screen: str,
        raw_output: str,
        exit_code: int | None,
    ) -> AssertionResult:
        return _contains(
            assertion.get("name", self.name),
            screen,
            assertion["value"],
            True,
            assertion.get("detail"),
        )


class ScreenNotContains:
    name = "screen_not_contains"

    def evaluate(
        self,
        recipe: Recipe,
        assertion: dict[str, Any],
        screen: str,
        raw_output: str,
        exit_code: int | None,
    ) -> AssertionResult:
        return _contains(
            assertion.get("name", self.name),
            screen,
            assertion["value"],
            False,
            assertion.get("detail"),
        )


class ExitCode:
    name = "exit_code"

    def evaluate(
        self,
        recipe: Recipe,
        assertion: dict[str, Any],
        screen: str,
        raw_output: str,
        exit_code: int | None,
    ) -> AssertionResult:
        value = assertion["value"]
        passed = exit_code == value
        return AssertionResult(
            assertion.get("name", self.name),
            passed,
            f"expected {value}, got {exit_code}",
        )


class FileExists:
    name = "file_exists"

    def evaluate(
        self,
        recipe: Recipe,
        assertion: dict[str, Any],
        screen: str,
        raw_output: str,
        exit_code: int | None,
    ) -> AssertionResult:
        path = _recipe_path(recipe, str(assertion["value"]))
        return AssertionResult(
            assertion.get("name", self.name),
            path.exists(),
            str(path),
        )


class FileContains:
    name = "file_contains"

    def evaluate(
        self,
        recipe: Recipe,
        assertion: dict[str, Any],
        screen: str,
        raw_output: str,
        exit_code: int | None,
    ) -> AssertionResult:
        path = _recipe_path(recipe, str(assertion["path"]))
        text = path.read_text(encoding="utf-8") if path.exists() else ""
        return _contains(
            assertion.get("name", self.name),
            text,
            assertion["value"],
            True,
        )


class JsonSchema:
    name = "json_schema"

    def evaluate(
        self,
        recipe: Recipe,
        assertion: dict[str, Any],
        screen: str,
        raw_output: str,
        exit_code: int | None,
    ) -> AssertionResult:
        name = assertion.get("name", self.name)
        schema, schema_error = _json_schema(recipe, assertion)
        if schema_error is not None or schema is None:
            return AssertionResult(name, False, schema_error or "missing schema")
        try:
            instance = json.loads(raw_output.strip())
        except json.JSONDecodeError as exc:
            return AssertionResult(name, False, f"invalid JSON output: {exc.msg}")
        try:
            jsonschema.validate(instance=instance, schema=schema)
        except jsonschema.SchemaError as exc:
            return AssertionResult(name, False, f"invalid schema: {exc.message}")
        except jsonschema.ValidationError as exc:
            path = ".".join(str(part) for part in exc.path)
            location = f" at {path}" if path else ""
            return AssertionResult(
                name,
                False,
                f"schema validation failed{location}: {exc.message}",
            )
        return AssertionResult(name, True, "matches JSON schema")
