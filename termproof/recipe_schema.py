from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from importlib import resources
from pathlib import Path
from typing import Any

import jsonschema

from .config import VerifierConfig
from .models import RECIPE_VERSION

_SCHEMA_RESOURCE = "recipe-schema-v1.json"


@dataclass(frozen=True)
class ValidationIssue:
    path: str
    message: str
    severity: str = "error"


def has_errors(issues: list[ValidationIssue]) -> bool:
    return any(issue.severity == "error" for issue in issues)


@lru_cache(maxsize=1)
def load_recipe_schema() -> dict[str, Any]:
    """Load the canonical recipe JSON schema shipped as a package resource."""
    resource = resources.files("termproof").joinpath("_resources", _SCHEMA_RESOURCE)
    if resource.is_file():
        return json.loads(resource.read_text(encoding="utf-8"))
    # Source-tree fallback: the canonical schema lives under docs/ and is only
    # force-included into the built wheel under termproof/_resources/.
    docs_schema = Path(__file__).resolve().parent.parent / "docs" / _SCHEMA_RESOURCE
    return json.loads(docs_schema.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def _schema_validator() -> jsonschema.protocols.Validator:
    schema = load_recipe_schema()
    validator_cls = jsonschema.validators.validator_for(schema)
    validator_cls.check_schema(schema)
    return validator_cls(schema)


def _issue_path(error: jsonschema.ValidationError) -> str:
    parts: list[str] = []
    for part in error.absolute_path:
        if isinstance(part, int):
            parts.append(f"[{part}]")
        elif parts:
            parts.append(f".{part}")
        else:
            parts.append(str(part))
    return "".join(parts) or "$"


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
    _validate_recipe_version(data, issues)
    for error in _schema_validator().iter_errors(data):
        # recipe_version carries a legacy-warning nuance that JSON Schema cannot
        # express, so it is handled entirely by _validate_recipe_version above.
        if list(error.absolute_path) == ["recipe_version"]:
            continue
        issues.append(ValidationIssue(_issue_path(error), error.message))
    _validate_plugin_names(data, config, issues)
    return issues


def _validate_recipe_version(data: dict[str, Any], issues: list[ValidationIssue]) -> None:
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


def _validate_plugin_names(
    data: dict[str, Any],
    config: VerifierConfig,
    issues: list[ValidationIssue],
) -> None:
    # Plugin-registry membership depends on runtime config and cannot be encoded
    # in the static JSON Schema, so these checks stay in Python.
    steps = data.get("steps")
    if isinstance(steps, list):
        for index, step in enumerate(steps):
            if isinstance(step, dict):
                action = step.get("action")
                if isinstance(action, str) and action not in config.steps:
                    issues.append(
                        ValidationIssue(
                            f"steps[{index}].action",
                            f"unknown step action {action!r}",
                        )
                    )
    assertions = data.get("assertions")
    if isinstance(assertions, list):
        for index, assertion in enumerate(assertions):
            if isinstance(assertion, dict):
                kind = assertion.get("type")
                if isinstance(kind, str) and kind not in config.assertions:
                    issues.append(
                        ValidationIssue(
                            f"assertions[{index}].type",
                            f"unknown assertion type {kind!r}",
                        )
                    )
