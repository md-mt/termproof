from __future__ import annotations

import json
import re
from dataclasses import dataclass
from functools import lru_cache
from importlib import resources
from pathlib import Path
from typing import Any

import jsonschema

from .config import VerifierConfig
from .models import RECIPE_VERSION

_SCHEMA_RESOURCE = "recipe-schema-v1.json"
_REQUIRED_PROP_RE = re.compile(r"'([^']+)' is a required property")


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
    # jsonschema reports missing required properties at the containing object
    # (e.g. ``$`` for a missing top-level ``command``). The legacy validator
    # reported the missing property itself, so recover it from the message to
    # keep error paths compatible.
    if error.validator == "required":
        match = _REQUIRED_PROP_RE.search(error.message)
        if match:
            prop = match.group(1)
            parent = "".join(
                f"[{part}]" if isinstance(part, int) else f".{part}"
                for part in error.absolute_path
            )
            return f"{parent}.{prop}" if parent else prop
    parts: list[str] = []
    for part in error.absolute_path:
        if isinstance(part, int):
            parts.append(f"[{part}]")
        elif parts:
            parts.append(f".{part}")
        else:
            parts.append(str(part))
    return "".join(parts) or "$"


# Legacy-compatibility tolerance. The pre-#93 Python validator (see
# tests/legacy_recipe_validator.py) guarded every optional field with
# `value is not None` and never type-checked free-form metadata. Recipes the
# legacy validator accepted must keep being accepted with equivalent
# warnings/errors, so schema errors on those exact inputs are ignored here.
# The canonical schema remains the authoritative structural spec; these are the
# only carve-outs, mirroring the recipe_version handling above.
_LEGACY_NULL_TOLERANT_TOP = frozenset(
    {
        "priority",
        "execution",
        "determinism",
        "timeout_seconds",
        "cols",
        "rows",
        "checks",
        "ci_paths",
        "operator",
        "renderers",
        "description",
        "intent",
    }
)
_LEGACY_NULL_TOLERANT_COMMAND = frozenset({"cwd", "pty"})
_LEGACY_NULL_TOLERANT_STEP = frozenset({"timeout_seconds"})
# Fields the legacy validator never checked at all — any value (including
# non-null, non-string) was accepted for these.
_LEGACY_UNCHECKED_TOP = frozenset({"description", "intent"})
# Fields inside steps/assertions the legacy validator never checked at all.
_LEGACY_UNCHECKED_NESTED = frozenset({"name"})


def _is_legacy_tolerated(data: dict[str, Any], error: jsonschema.ValidationError) -> bool:
    """Return True when the schema error points at input the legacy validator
    would have accepted, so it must not surface as a new error."""
    path = list(error.absolute_path)
    if not path:
        return False
    # Top-level description/intent: legacy never type-checked them at all, so
    # any schema error there (e.g. numeric description) must be suppressed.
    if len(path) == 1 and path[0] in _LEGACY_UNCHECKED_TOP:
        return True
    # steps[i].<field> / assertions[i].<field>: legacy only checked action/type
    # (+ timeout_seconds); extra fields and name were never validated.
    if (
        len(path) == 3
        and isinstance(path[1], int)
        and path[0] in ("steps", "assertions")
        and path[2] in _LEGACY_UNCHECKED_NESTED
    ):
        return True
    # Locate the value at the error path.
    value: Any = data
    for part in path:
        if isinstance(value, dict):
            if part not in value:
                return False
            value = value[part]
        elif isinstance(value, list) and isinstance(part, int) and 0 <= part < len(value):
            value = value[part]
        else:
            return False
    if value is not None:
        return False
    # A null value: legacy's `value is not None` guards accepted it for every
    # optional field. Only reject paths where legacy required a list/object.
    if len(path) == 1:
        return path[0] in _LEGACY_NULL_TOLERANT_TOP
    if len(path) == 2 and path[0] == "command":
        return path[1] in _LEGACY_NULL_TOLERANT_COMMAND
    if len(path) == 3 and isinstance(path[1], int) and path[0] == "steps":
        return path[2] in _LEGACY_NULL_TOLERANT_STEP
    return False


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
        # Legacy compatibility: inputs the legacy validator accepted (null
        # optional fields, free-form description/intent, unchecked nested
        # names) must not become new errors in a behavior-preserving refactor.
        if _is_legacy_tolerated(data, error):
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
