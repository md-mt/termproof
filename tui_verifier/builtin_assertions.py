from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from .models import AssertionResult, Recipe


class AssertionType(Protocol):
    """Protocol for pluggable assertion evaluators."""

    name: str  # matches recipe assertion "type" field

    def evaluate(
        self,
        recipe: Recipe,
        assertion: dict[str, Any],
        screen: str,
        raw_output: str,
        exit_code: int | None,
    ) -> AssertionResult:
        ...


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
