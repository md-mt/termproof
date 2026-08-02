#!/usr/bin/env python3
"""Deterministic broad differential oracle probe for the termproof recipe
validator consolidation (PR #127).

Compares the consolidated schema-based validator (termproof.recipe_schema)
against the frozen legacy oracle (tests/legacy_recipe_validator.py) over a
large deterministic corpus built by mutating every structural field of the
recipe with missing/null/wrong-type/boundary values, including nested
missing-required-property cases (command={}, steps=[{}], assertions=[{}]).

Contract (same as tests/test_differential_compat.py):
- accept/reject (presence of any error) must match exactly;
- warning paths+severities must match exactly;
- no exceptions may be raised by either validator;
- error paths must be equal-or-more-granular (legacy path covered by new path),
  and for the missing-required family the paths must be byte-identical.

Deterministic: no randomness; the corpus is a pure function of the mutation
tables below.
"""

from __future__ import annotations

import itertools
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tests"))

from termproof.config import VerifierConfig
from termproof.recipe_schema import validate_recipe_mapping

from legacy_recipe_validator import validate_recipe_mapping as legacy_validate

CONFIG = VerifierConfig.builtin()

BASE = {
    "recipe_version": 1,
    "name": "x",
    "description": "d",
    "intent": "i",
    "priority": "p",
    "execution": "e",
    "determinism": "d",
    "timeout_seconds": 30,
    "cols": 80,
    "rows": 24,
    "expect_exit_code": 0,
    "checks": ["c1"],
    "ci_paths": ["ci"],
    "operator": {"name": "op"},
    "renderers": {"default": ["renderer"]},
    "command": {"argv": ["true"], "cwd": None, "env": {"K": "V"}, "pty": False},
    "steps": [{"action": "wait_for_text", "text": "ok", "timeout_seconds": 10}],
    "assertions": [{"type": "output_contains", "value": "ok"}],
}

# Per-field mutations: (label, value) applied via data[field] = value, or
# ("__missing__", None) to remove the key entirely.
TOP_LEVEL_MUTATIONS: dict[str, list[tuple[str, object]]] = {
    "recipe_version": [("missing", "__missing__"), ("two", 2), ("bool", True), ("string", "1")],
    "name": [("missing", "__missing__"), ("empty", ""), ("int", 5)],
    "description": [("missing", "__missing__"), ("null", None), ("int", 123), ("bool", True), ("obj", {"a": 1})],
    "intent": [("missing", "__missing__"), ("null", None), ("int", 456), ("bool", False), ("obj", {"a": 1})],
    "priority": [("missing", "__missing__"), ("null", None), ("int", 5), ("bool", True)],
    "execution": [("missing", "__missing__"), ("null", None), ("list", ["x"]), ("bool", True)],
    "determinism": [("missing", "__missing__"), ("null", None), ("list", ["x"])],
    "timeout_seconds": [("missing", "__missing__"), ("null", None), ("zero", 0), ("bool", True), ("float", 1.5), ("neg", -1)],
    "cols": [("missing", "__missing__"), ("null", None), ("zero", 0), ("bool", True), ("one_dot_zero", 1.0), ("zero_dot_zero", 0.0), ("neg_one_dot_zero", -1.0), ("float", 1.5), ("neg", -1)],
    "rows": [("missing", "__missing__"), ("null", None), ("zero", 0), ("bool", True), ("one_dot_zero", 1.0), ("zero_dot_zero", 0.0), ("neg_one_dot_zero", -1.0), ("float", 1.5), ("neg", -1)],
    "expect_exit_code": [("missing", "__missing__"), ("null", None), ("bool", True), ("one_dot_zero", 1.0), ("zero_dot_zero", 0.0), ("neg_one_dot_zero", -1.0), ("float", 1.5), ("neg", -1)],
    "checks": [("missing", "__missing__"), ("null", None), ("int_list", [1]), ("string", "a")],
    "ci_paths": [("missing", "__missing__"), ("null", None), ("int_list", [1]), ("string", "a")],
    "operator": [("missing", "__missing__"), ("null", None), ("list", []), ("string", "x")],
    "renderers": [("missing", "__missing__"), ("null", None), ("string", "x"), ("bad_argv", {"default": "x"})],
    "command": [("missing", "__missing__"), ("null", None), ("string", "echo"), ("int", 5)],
    "steps": [("missing", "__missing__"), ("null", None), ("string", "x"), ("empty", [])],
    "assertions": [("missing", "__missing__"), ("null", None), ("string", "x"), ("empty", [])],
}

COMMAND_MUTATIONS: list[tuple[str, object]] = [
    ("empty_obj", {}),
    ("missing_argv", {"cwd": None, "env": {"K": "V"}, "pty": False}),
    ("argv_empty", {"argv": []}),
    ("argv_int", {"argv": [1, 2]}),
    ("argv_string", {"argv": "true"}),
    ("env_int", {"argv": ["a"], "env": {"K": 1}}),
    ("env_list", {"argv": ["a"], "env": []}),
    ("cwd_int", {"argv": ["a"], "cwd": 5}),
    ("pty_string", {"argv": ["a"], "pty": "yes"}),
    ("pty_null", {"argv": ["a"], "pty": None}),
    ("cwd_null", {"argv": ["a"], "cwd": None}),
    ("cwd_string", {"argv": ["a"], "cwd": "/tmp"}),
]

STEP_MUTATIONS: list[tuple[str, object]] = [
    ("empty_obj", {}),
    ("missing_action", {"text": "ok"}),
    ("action_int", {"action": 5}),
    ("action_unknown", {"action": "missing_step"}),
    ("timeout_zero", {"action": "wait_for_text", "text": "ok", "timeout_seconds": 0}),
    ("timeout_bool", {"action": "wait_for_text", "text": "ok", "timeout_seconds": True}),
    ("timeout_null", {"action": "wait_for_text", "text": "ok", "timeout_seconds": None}),
    ("name_int", {"action": "wait_for_text", "text": "ok", "name": 123}),
    ("not_object", "string"),
    ("not_object_list", [1]),
]

ASSERTION_MUTATIONS: list[tuple[str, object]] = [
    ("empty_obj", {}),
    ("missing_type", {"value": "ok"}),
    ("type_int", {"type": 5}),
    ("type_unknown", {"type": "missing_assertion"}),
    ("name_int", {"type": "output_contains", "value": "ok", "name": 123}),
    ("not_object", "string"),
    ("not_object_list", [1]),
]

NESTED_ITEM_MISSING = [
    ("command", COMMAND_MUTATIONS),
    ("steps", STEP_MUTATIONS),
    ("assertions", ASSERTION_MUTATIONS),
]

# Multi-index nested cases: the missing-required family at nonzero indices,
# which exercises bracket formatting on later list positions.
MULTI_INDEX_CASES: list[tuple[str, dict]] = [
    (
        "steps[1] empty object",
        {**BASE, "steps": [{"action": "wait_for_text", "text": "ok"}, {}]},
    ),
    (
        "assertions[2] empty object",
        {
            **BASE,
            "assertions": [
                {"type": "output_contains", "value": "a"},
                {"type": "output_contains", "value": "b"},
                {},
            ],
        },
    ),
    (
        "steps[0] missing action at depth",
        {**BASE, "steps": [{"timeout_seconds": 5}]},
    ),
    (
        "assertions[0] missing type at depth",
        {**BASE, "assertions": [{"value": "x"}]},
    ),
    (
        "command missing argv with siblings",
        {**BASE, "command": {"cwd": "/tmp", "env": {"K": "V"}}},
    ),
]


def _apply(data: dict, key: str, mutation: tuple[str, object]) -> dict:
    out = dict(data)
    label, value = mutation
    if value == "__missing__":
        out.pop(key, None)
    else:
        out[key] = value
    return out


def _verdict(validate, data: dict) -> tuple[list[tuple[str, str]], str | None]:
    """Return (issues as (path, severity) list, exception-message-or-None)."""
    try:
        issues = validate(data, CONFIG)
        return [(i.path, i.severity) for i in issues], None
    except Exception as exc:  # noqa: BLE001 - probe must count exceptions
        return [], f"{type(exc).__name__}: {exc}"


def _path_covers(outer: str, inner: str) -> bool:
    return inner == outer or inner.startswith(outer + ".") or inner.startswith(outer + "[")


def _path_mismatch(legacy_errors, new_errors) -> bool:
    """True when the error paths are not equivalent under the differential
    contract (bidirectional coverage, legacy path covered by new path)."""
    for legacy_path, severity in legacy_errors:
        if not any(
            severity == new_severity and _path_covers(legacy_path, new_path)
            for new_path, new_severity in new_errors
        ):
            return True
    for new_path, severity in new_errors:
        if not any(
            severity == legacy_severity and _path_covers(legacy_path, new_path)
            for legacy_path, legacy_severity in legacy_errors
        ):
            return True
    return False


def _exact_missing_required_mismatch(legacy_errors, new_errors) -> bool:
    """For the missing-required family the review demands byte-identical
    paths (no leading dot). Any case where a legacy error path appears with a
    leading dot in the new validator is a mismatch."""
    legacy_paths = {p for p, s in legacy_errors if s == "error"}
    new_paths = {p for p, s in new_errors if s == "error"}
    for path in legacy_paths:
        if "." + path in new_paths:
            return True
    return False


def main() -> None:
    cases: list[tuple[str, dict]] = []
    # Single-field mutations (top level).
    for field, mutations in TOP_LEVEL_MUTATIONS.items():
        for label, _value in mutations:
            cases.append((f"{field}={label}", _apply(BASE, field, (label, _value))))
    # Nested single mutations: command / steps[0] / assertions[0].
    for field, mutations in NESTED_ITEM_MISSING:
        for label, value in mutations:
            data = dict(BASE)
            if value == "__missing__":
                pass
            if field == "command":
                data["command"] = value
            elif field == "steps":
                data["steps"] = [value] if isinstance(value, dict) else value
            elif field == "assertions":
                data["assertions"] = [value] if isinstance(value, dict) else value
            cases.append((f"{field}={label}", data))
    # Pairwise top-level mutations (the bulk of the corpus).
    fields = list(TOP_LEVEL_MUTATIONS)
    for f1, f2 in itertools.combinations(fields, 2):
        for label1, value1 in TOP_LEVEL_MUTATIONS[f1]:
            for label2, value2 in TOP_LEVEL_MUTATIONS[f2]:
                data = _apply(BASE, f1, (label1, value1))
                data = _apply(data, f2, (label2, value2))
                cases.append((f"{f1}={label1},{f2}={label2}", data))
    # Triple top-level mutations (deep cross-field interactions).
    for f1, f2, f3 in itertools.combinations(fields, 3):
        for label1, value1 in TOP_LEVEL_MUTATIONS[f1]:
            for label2, value2 in TOP_LEVEL_MUTATIONS[f2]:
                for label3, value3 in TOP_LEVEL_MUTATIONS[f3]:
                    data = _apply(BASE, f1, (label1, value1))
                    data = _apply(data, f2, (label2, value2))
                    data = _apply(data, f3, (label3, value3))
                    cases.append((f"{f1}={label1},{f2}={label2},{f3}={label3}", data))
    # Explicit multi-index nested missing-required cases.
    cases.extend(MULTI_INDEX_CASES)

    total = len(cases)
    accept_mismatch = 0
    warning_mismatch = 0
    exception_mismatch = 0
    path_mismatch = 0
    exact_required_mismatch = 0
    mismatches: list[tuple[str, str, object]] = []

    for label, data in cases:
        legacy_issues, legacy_exc = _verdict(legacy_validate, data)
        new_issues, new_exc = _verdict(validate_recipe_mapping, data)
        if legacy_exc or new_exc:
            exception_mismatch += 1
            mismatches.append(("exception", label, (legacy_exc, new_exc)))
            continue
        legacy_errors = [(p, s) for p, s in legacy_issues if s == "error"]
        new_errors = [(p, s) for p, s in new_issues if s == "error"]
        legacy_warnings = sorted((p, s) for p, s in legacy_issues if s == "warning")
        new_warnings = sorted((p, s) for p, s in new_issues if s == "warning")
        if bool(legacy_errors) != bool(new_errors):
            accept_mismatch += 1
            mismatches.append(("accept", label, (legacy_errors, new_errors)))
        if legacy_warnings != new_warnings:
            warning_mismatch += 1
            mismatches.append(("warning", label, (legacy_warnings, new_warnings)))
        if _path_mismatch(legacy_errors, new_errors):
            path_mismatch += 1
            mismatches.append(("path", label, (legacy_errors, new_errors)))
        if _exact_missing_required_mismatch(legacy_errors, new_errors):
            exact_required_mismatch += 1
            mismatches.append(("exact-required", label, (legacy_errors, new_errors)))

    print(f"total cases: {total}")
    print(f"accept/reject mismatches: {accept_mismatch}")
    print(f"warning mismatches: {warning_mismatch}")
    print(f"exception mismatches: {exception_mismatch}")
    print(f"path (coverage contract) mismatches: {path_mismatch}")
    print(f"missing-required exact-path (leading-dot) mismatches: {exact_required_mismatch}")
    if mismatches:
        print(f"\n{len(mismatches)} mismatches, first 20:")
        for kind, label, detail in mismatches[:20]:
            print(f"  [{kind}] {label}: {json.dumps(detail, default=str)[:200]}")
        return 1
    print("\nPROBE PASS: zero mismatches across all contracts")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
