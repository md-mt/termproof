from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

# The legacy oracle lives next to this test; make it importable regardless of
# whether the suite is run via `discover -s tests` or `-m unittest tests.…`.
sys.path.insert(0, str(Path(__file__).resolve().parent))

from termproof.config import VerifierConfig
from termproof.recipe_schema import validate_recipe_mapping

from legacy_recipe_validator import validate_recipe_mapping as legacy_validate_recipe_mapping

_REPO_ROOT = Path(__file__).resolve().parent.parent


def _legacy_verdict(data: dict) -> list[tuple[str, str]]:
    return [
        (issue.path, issue.severity)
        for issue in legacy_validate_recipe_mapping(data, VerifierConfig.builtin())
    ]


def _new_verdict(data: dict) -> list[tuple[str, str]]:
    return [
        (issue.path, issue.severity)
        for issue in validate_recipe_mapping(data, VerifierConfig.builtin())
    ]


def _base_recipe(**overrides) -> dict:
    data = {
        "recipe_version": 1,
        "name": "x",
        "command": {"argv": ["true"]},
        "steps": [],
        "assertions": [],
    }
    data.update(overrides)
    return data


def _path_covers(outer: str, inner: str) -> bool:
    """True when ``inner`` is the same error location as ``outer`` or a more
    granular report of it (e.g. legacy ``command.env`` vs schema
    ``command.env.K``). The legacy PR documented that structural error paths
    may become more granular when validated by the JSON Schema."""
    return inner == outer or inner.startswith(outer + ".") or inner.startswith(outer + "[")


class DifferentialCompatibilityTest(unittest.TestCase):
    """Every recipe the legacy validator accepted must be accepted by the
    consolidated schema-based validator with equivalent warnings/errors, and
    every rejection must be preserved.

    Contract:
    - accept/reject (presence of any ``error``) must match exactly;
    - warning paths+severities must match exactly (they are semantic, e.g. the
      legacy recipe_version warning);
    - error severities must match exactly; error paths must be equal or more
      granular (documented structural wording/path drift)."""

    def assert_equivalent(self, legacy: list[tuple[str, str]], new: list[tuple[str, str]], label: str) -> None:
        legacy_errors = [(p, s) for p, s in legacy if s == "error"]
        new_errors = [(p, s) for p, s in new if s == "error"]
        legacy_warnings = sorted((p, s) for p, s in legacy if s == "warning")
        new_warnings = sorted((p, s) for p, s in new if s == "warning")

        self.assertEqual(
            bool(legacy_errors),
            bool(new_errors),
            f"{label}: accept/reject drift legacy_errors={legacy_errors} new_errors={new_errors}",
        )
        self.assertEqual(
            legacy_warnings,
            new_warnings,
            f"{label}: warning drift legacy={legacy_warnings} new={new_warnings}",
        )
        # Bidirectional path coverage with severity preservation: every legacy
        # error must be reported (possibly more granularly, e.g. one per bad
        # argv item) by the new validator, and every new error must trace back
        # to a legacy error. Granular expansion is the documented structural
        # wording/path drift, so counts may differ per field.
        for legacy_path, severity in legacy_errors:
            self.assertTrue(
                any(
                    severity == new_severity and _path_covers(legacy_path, new_path)
                    for new_path, new_severity in new_errors
                ),
                f"{label}: legacy error {legacy_path!r} not covered by new={new_errors}",
            )
        for new_path, severity in new_errors:
            self.assertTrue(
                any(
                    severity == legacy_severity and _path_covers(legacy_path, new_path)
                    for legacy_path, legacy_severity in legacy_errors
                ),
                f"{label}: new error {new_path!r} has no legacy counterpart legacy={legacy_errors}",
            )

    def assert_same_verdict(self, data: dict, label: str) -> None:
        legacy = _legacy_verdict(data)
        new = _new_verdict(data)
        self.assert_equivalent(legacy, new, f"{label} (data={json.dumps(data)})")

    def test_review_repro_numeric_description_without_version(self) -> None:
        # mw-ding CHANGES_REQUESTED repro: base returns only the legacy
        # recipe_version warning; the #93 schema added a description error.
        self.assert_same_verdict(
            {
                "name": "x",
                "description": 123,
                "command": {"argv": ["true"]},
                "steps": [],
                "assertions": [],
            },
            "review repro (numeric description, no recipe_version)",
        )

    def test_numeric_description_with_version(self) -> None:
        self.assert_same_verdict(
            _base_recipe(description=123),
            "numeric description with recipe_version",
        )

    def test_numeric_intent_with_and_without_version(self) -> None:
        self.assert_same_verdict(
            _base_recipe(intent=456),
            "numeric intent with recipe_version",
        )
        data = _base_recipe(intent=456)
        data.pop("recipe_version")
        self.assert_same_verdict(data, "numeric intent without recipe_version")

    def test_boolean_description_is_accepted_like_legacy(self) -> None:
        self.assert_same_verdict(_base_recipe(description=True), "boolean description")

    def test_object_intent_is_accepted_like_legacy(self) -> None:
        self.assert_same_verdict(_base_recipe(intent={"nested": [1, 2]}), "object intent")

    def test_null_description_and_intent(self) -> None:
        self.assert_same_verdict(_base_recipe(description=None), "null description")
        self.assert_same_verdict(_base_recipe(intent=None), "null intent")

    def test_null_optional_fields_match_legacy(self) -> None:
        # The legacy validator's `value is not None` guards accepted null for
        # every optional field; the #93 schema only allowed null for cwd and
        # expect_exit_code. Lock in the legacy verdict for each.
        cases = {
            "priority_null": _base_recipe(priority=None),
            "execution_null": _base_recipe(execution=None),
            "determinism_null": _base_recipe(determinism=None),
            "timeout_null": _base_recipe(timeout_seconds=None),
            "cols_null": _base_recipe(cols=None),
            "rows_null": _base_recipe(rows=None),
            "checks_null": _base_recipe(checks=None),
            "ci_paths_null": _base_recipe(ci_paths=None),
            "operator_null": _base_recipe(operator=None),
            "renderers_null": _base_recipe(renderers=None),
            "pty_null": _base_recipe(command={"argv": ["true"], "pty": None}),
            "step_timeout_null": _base_recipe(
                steps=[{"action": "wait_for_text", "text": "ok", "timeout_seconds": None}]
            ),
            "cwd_null": _base_recipe(command={"argv": ["true"], "cwd": None}),
            "expect_exit_code_null": _base_recipe(expect_exit_code=None),
        }
        for label, data in cases.items():
            self.assert_same_verdict(data, label)

    def test_null_steps_and_assertions_are_errors_like_legacy(self) -> None:
        # steps/assertions must be lists even when null — legacy rejected these.
        self.assert_same_verdict(_base_recipe(steps=None), "steps null")
        self.assert_same_verdict(_base_recipe(assertions=None), "assertions null")

    def test_non_string_optional_fields_still_error(self) -> None:
        # Relaxing null tolerance must not silently accept garbage that legacy
        # rejected (non-null, non-string values).
        cases = {
            "priority_int": _base_recipe(priority=5),
            "execution_bool": _base_recipe(execution=True),
            "determinism_list": _base_recipe(determinism=["x"]),
            "timeout_zero": _base_recipe(timeout_seconds=0),
            "timeout_bool": _base_recipe(timeout_seconds=True),
            "cols_float": _base_recipe(cols=1.5),
            "rows_bool": _base_recipe(rows=True),
            "checks_int_list": _base_recipe(checks=[1]),
            "ci_paths_string": _base_recipe(ci_paths="a"),
            "operator_list": _base_recipe(operator=[]),
            "renderers_string": _base_recipe(renderers="x"),
            "pty_string": _base_recipe(command={"argv": ["true"], "pty": "yes"}),
            "step_timeout_zero": _base_recipe(
                steps=[{"action": "wait_for_text", "text": "ok", "timeout_seconds": 0}]
            ),
        }
        for label, data in cases.items():
            self.assert_same_verdict(data, label)

    def test_integral_float_values_are_rejected_like_legacy(self) -> None:
        # JSON Schema draft 2020-12 (via jsonschema) treats integral-valued
        # floats as `integer`, so `cols: 1.0` would otherwise slip through the
        # canonical schema. The frozen base validator required actual Python
        # `int`, so these must stay errors (behavior-preserving rejection).
        # Oracle cases for the boundary values 1.0, 0.0, -1.0 on every
        # affected field: cols, rows, expect_exit_code.
        cases = {
            "cols_one_point_zero": _base_recipe(cols=1.0),
            "cols_zero_point_zero": _base_recipe(cols=0.0),
            "cols_negative_one_point_zero": _base_recipe(cols=-1.0),
            "rows_one_point_zero": _base_recipe(rows=1.0),
            "rows_zero_point_zero": _base_recipe(rows=0.0),
            "rows_negative_one_point_zero": _base_recipe(rows=-1.0),
            "expect_exit_code_one_point_zero": _base_recipe(expect_exit_code=1.0),
            "expect_exit_code_zero_point_zero": _base_recipe(expect_exit_code=0.0),
            "expect_exit_code_negative_one_point_zero": _base_recipe(
                expect_exit_code=-1.0
            ),
            # Plain integral ints stay accepted (positive ints for cols/rows,
            # any int for expect_exit_code) — no regression there.
            "cols_int_accepted": _base_recipe(cols=1),
            "rows_int_accepted": _base_recipe(rows=30),
            "expect_exit_code_int_accepted": _base_recipe(expect_exit_code=0),
        }
        for label, data in cases.items():
            self.assert_same_verdict(data, label)

    def test_step_and_assertion_extra_fields_are_tolerated_like_legacy(self) -> None:
        # Legacy only checked action/type (+ timeout) inside steps/assertions;
        # arbitrary extra fields and non-string names were not validated.
        self.assert_same_verdict(
            _base_recipe(steps=[{"action": "wait_for_text", "text": "ok", "name": 123}]),
            "step numeric name",
        )
        self.assert_same_verdict(
            _base_recipe(assertions=[{"type": "output_contains", "value": "ok", "name": 123}]),
            "assertion numeric name",
        )

    def test_unknown_plugin_names_are_errors_like_legacy(self) -> None:
        self.assert_same_verdict(
            _base_recipe(steps=[{"action": "missing_step"}]), "unknown step action"
        )
        self.assert_same_verdict(
            _base_recipe(assertions=[{"type": "missing_assertion"}]),
            "unknown assertion type",
        )

    def test_recipe_version_nuances_match_legacy(self) -> None:
        cases = {
            "missing_version": _base_recipe(recipe_version="__missing__"),
            "version_two": _base_recipe(recipe_version=2),
            "version_bool": _base_recipe(recipe_version=True),
            "version_string": _base_recipe(recipe_version="1"),
        }
        for label, base in cases.items():
            data = dict(base)
            if data.get("recipe_version") == "__missing__":
                data.pop("recipe_version")
            self.assert_same_verdict(data, label)

    def test_structure_error_paths_match_legacy(self) -> None:
        cases = {
            "empty_name": _base_recipe(name=""),
            "name_int": _base_recipe(name=5),
            "missing_command": _base_recipe(command="__missing__"),
            "command_string": _base_recipe(command="echo"),
            "empty_argv": _base_recipe(command={"argv": []}),
            "argv_int": _base_recipe(command={"argv": [1, 2]}),
            "env_int_value": _base_recipe(command={"argv": ["a"], "env": {"K": 1}}),
            "cwd_int": _base_recipe(command={"argv": ["a"], "cwd": 5}),
        }
        for label, base in cases.items():
            data = dict(base)
            if data.get("command") == "__missing__":
                data.pop("command")
            self.assert_same_verdict(data, label)

    def test_accepted_legacy_corpus_is_still_accepted(self) -> None:
        """A representative corpus of recipes the legacy validator accepted
        (the shipped example recipes) must still be accepted with identical
        verdicts. All of these are warning-only (missing recipe_version)."""
        corpus_dir = _REPO_ROOT / "examples"
        recipe_paths = sorted(corpus_dir.glob("*.recipe.json"))
        self.assertGreaterEqual(len(recipe_paths), 5)
        for path in recipe_paths:
            data = json.loads(path.read_text(encoding="utf-8"))
            legacy = _legacy_verdict(data)
            new = _new_verdict(data)
            self.assert_equivalent(legacy, new, path.name)
            self.assertFalse(any(sev == "error" for _, sev in new), f"{path.name} got errors")


if __name__ == "__main__":
    unittest.main()
