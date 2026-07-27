from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import VerifierConfig

RECIPE_VERSION = 1


@dataclass(frozen=True)
class ValidationIssue:
    path: str
    message: str
    severity: str = "error"


def has_errors(issues: list[ValidationIssue]) -> bool:
    return any(issue.severity == "error" for issue in issues)


def validate_recipe_file(path: Path, config: VerifierConfig) -> list[ValidationIssue]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as error:
        return [ValidationIssue("$", f"invalid JSON: {error.msg}")]
    if not isinstance(data, dict):
        return [ValidationIssue("$", "recipe must be a JSON object")]
    return validate_recipe_mapping(data, config)


def validate_recipe_mapping(
    data: dict[str, Any],
    config: VerifierConfig,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    version = data.get("recipe_version")
    if version is None:
        issues.append(
            ValidationIssue(
                "recipe_version",
                "missing recipe_version; treating recipe as legacy v0.x",
                "warning",
            )
        )
    elif not isinstance(version, int) or isinstance(version, bool) or version != RECIPE_VERSION:
        issues.append(ValidationIssue("recipe_version", "must be 1"))

    _require_str(data, "name", issues)
    _validate_command(data.get("command"), issues)
    _validate_positive_number(data, "timeout_seconds", issues)
    _validate_positive_int(data, "cols", issues)
    _validate_positive_int(data, "rows", issues)
    _validate_expect_exit_code(data.get("expect_exit_code"), issues)
    _validate_optional_string(data, "priority", issues)
    _validate_optional_string(data, "execution", issues)
    _validate_optional_string(data, "determinism", issues)
    _validate_string_list(data, "checks", issues)
    _validate_string_list(data, "ci_paths", issues)
    _validate_object(data, "operator", issues)
    _validate_renderers(data.get("renderers"), issues)
    _validate_steps(data.get("steps", []), config, issues)
    _validate_assertions(data.get("assertions", []), config, issues)
    return issues


def _require_str(data: dict[str, Any], key: str, issues: list[ValidationIssue]) -> None:
    value = data.get(key)
    if not isinstance(value, str) or not value:
        issues.append(ValidationIssue(key, "must be a non-empty string"))


def _validate_optional_string(
    data: dict[str, Any],
    key: str,
    issues: list[ValidationIssue],
) -> None:
    value = data.get(key)
    if value is not None and not isinstance(value, str):
        issues.append(ValidationIssue(key, "must be a string"))


def _validate_command(value: Any, issues: list[ValidationIssue]) -> None:
    if not isinstance(value, dict):
        issues.append(ValidationIssue("command", "must be an object"))
        return
    argv = value.get("argv")
    if not isinstance(argv, list) or not argv or not all(isinstance(item, str) for item in argv):
        issues.append(ValidationIssue("command.argv", "must be a non-empty list of strings"))
    if value.get("cwd") is not None and not isinstance(value.get("cwd"), str):
        issues.append(ValidationIssue("command.cwd", "must be a string"))
    env = value.get("env", {})
    if not isinstance(env, dict) or not all(
        isinstance(key, str) and isinstance(item, str) for key, item in env.items()
    ):
        issues.append(ValidationIssue("command.env", "must be an object of string values"))
    if value.get("pty") is not None and not isinstance(value.get("pty"), bool):
        issues.append(ValidationIssue("command.pty", "must be true or false"))


def _validate_positive_number(
    data: dict[str, Any],
    key: str,
    issues: list[ValidationIssue],
) -> None:
    value = data.get(key)
    if value is not None and (
        not isinstance(value, (int, float)) or isinstance(value, bool) or value <= 0
    ):
        issues.append(ValidationIssue(key, "must be a positive number"))


def _validate_positive_int(
    data: dict[str, Any],
    key: str,
    issues: list[ValidationIssue],
) -> None:
    value = data.get(key)
    if value is not None and (not isinstance(value, int) or isinstance(value, bool) or value <= 0):
        issues.append(ValidationIssue(key, "must be a positive integer"))


def _validate_expect_exit_code(value: Any, issues: list[ValidationIssue]) -> None:
    if value is not None and (not isinstance(value, int) or isinstance(value, bool)):
        issues.append(ValidationIssue("expect_exit_code", "must be an integer or null"))


def _validate_string_list(
    data: dict[str, Any],
    key: str,
    issues: list[ValidationIssue],
) -> None:
    value = data.get(key)
    if value is not None and (
        not isinstance(value, list) or not all(isinstance(item, str) for item in value)
    ):
        issues.append(ValidationIssue(key, "must be a list of strings"))


def _validate_object(data: dict[str, Any], key: str, issues: list[ValidationIssue]) -> None:
    value = data.get(key)
    if value is not None and not isinstance(value, dict):
        issues.append(ValidationIssue(key, "must be an object"))


def _validate_renderers(value: Any, issues: list[ValidationIssue]) -> None:
    if value is None:
        return
    if not isinstance(value, dict):
        issues.append(ValidationIssue("renderers", "must be an object"))
        return
    for name, argv in value.items():
        if not isinstance(name, str) or not isinstance(argv, list) or not all(
            isinstance(item, str) for item in argv
        ):
            issues.append(ValidationIssue(f"renderers.{name}", "must be a list of strings"))


def _validate_steps(
    value: Any,
    config: VerifierConfig,
    issues: list[ValidationIssue],
) -> None:
    if not isinstance(value, list):
        issues.append(ValidationIssue("steps", "must be a list"))
        return
    for index, step in enumerate(value):
        path = f"steps[{index}]"
        if not isinstance(step, dict):
            issues.append(ValidationIssue(path, "must be an object"))
            continue
        action = step.get("action")
        if not isinstance(action, str):
            issues.append(ValidationIssue(f"{path}.action", "must be a string"))
        elif action not in config.steps:
            issues.append(ValidationIssue(f"{path}.action", f"unknown step action {action!r}"))
        _validate_step_timeout(step, path, issues)


def _validate_step_timeout(
    step: dict[str, Any],
    path: str,
    issues: list[ValidationIssue],
) -> None:
    value = step.get("timeout_seconds")
    if value is not None and (
        not isinstance(value, (int, float)) or isinstance(value, bool) or value <= 0
    ):
        issues.append(ValidationIssue(f"{path}.timeout_seconds", "must be a positive number"))


def _validate_assertions(
    value: Any,
    config: VerifierConfig,
    issues: list[ValidationIssue],
) -> None:
    if not isinstance(value, list):
        issues.append(ValidationIssue("assertions", "must be a list"))
        return
    for index, assertion in enumerate(value):
        path = f"assertions[{index}]"
        if not isinstance(assertion, dict):
            issues.append(ValidationIssue(path, "must be an object"))
            continue
        kind = assertion.get("type")
        if not isinstance(kind, str):
            issues.append(ValidationIssue(f"{path}.type", "must be a string"))
        elif kind not in config.assertions:
            issues.append(ValidationIssue(f"{path}.type", f"unknown assertion type {kind!r}"))
