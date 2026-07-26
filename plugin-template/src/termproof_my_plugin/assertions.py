"""Example custom assertion for TermProof.

Implements ``screen_count`` — asserts a regex appears at least/at most N times
on the final screen. Register it in config:

.. code-block:: yaml

   assertions:
     screen_count: termproof_my_plugin.assertions:ScreenCount

Protocol compatibility:
- Compatible with TermProof >=0.1.0
- ``name`` class attribute must match the config ``assertions`` mapping
- ``evaluate(recipe, assertion, screen, raw_output, exit_code) -> AssertionResult``

Note: The assertion protocol only receives the final screen/raw_output/exit_code.
Timing data and run artifacts are NOT available, so duration-based assertions
must be implemented in TermProof core and cannot be written in a plugin.
See ``docs/protocol.md`` for the full availability matrix.
"""

from __future__ import annotations

import re
from typing import Any

from termproof.models import AssertionResult, Recipe


class ScreenCount:
    """Assert a regex appears at least/at most N times on the final screen.

    Recipe usage::

        {
          "type": "screen_count",
          "pattern": "TODO",
          "min": 0,
          "max": 3
        }

    ``min`` and ``max`` are optional integer bounds (inclusive).
    At least one of ``min`` or ``max`` must be provided.
    Bounds must be non-negative integers, and ``min <= max`` when both set.
    """

    name = "screen_count"

    def evaluate(
        self,
        recipe: Recipe,
        assertion: dict[str, Any],
        screen: str,
        raw_output: str,
        exit_code: int | None,
    ) -> AssertionResult:
        display = str(assertion.get("name", self.name))

        # --- validate pattern --------------------------------------------------
        pattern = assertion.get("pattern")
        if not pattern:
            return AssertionResult(
                display, False, "missing required field 'pattern'"
            )
        if not isinstance(pattern, str):
            return AssertionResult(
                display, False,
                f"pattern must be a string, got {type(pattern).__name__}"
            )
        try:
            compiled = re.compile(pattern)
        except re.error as exc:
            return AssertionResult(
                display, False, f"invalid regex {pattern!r}: {exc}"
            )
        except TypeError as exc:
            return AssertionResult(
                display, False, f"invalid pattern type: {exc}"
            )

        # --- validate bounds ---------------------------------------------------
        min_c = assertion.get("min")
        max_c = assertion.get("max")
        if min_c is None and max_c is None:
            return AssertionResult(
                display, False,
                "at least one of 'min' or 'max' must be provided"
            )

        def _validate_bound(
            value: object, label: str
        ) -> tuple[bool, str]:
            """Return (ok, error_msg)."""
            if value is None:
                return True, ""
            # Reject booleans (bool is a subclass of int)
            if isinstance(value, bool):
                return False, f"invalid {label} {value!r}: must be an integer, not bool"
            try:
                v = int(value)
            except (TypeError, ValueError):
                return False, f"invalid {label} {value!r}: expected integer"
            if v < 0:
                return False, f"{label} {v} must be >= 0"
            return True, str(v)

        if min_c is not None:
            ok, msg = _validate_bound(min_c, "min")
            if not ok:
                return AssertionResult(display, False, msg)
            min_val = int(msg)
        else:
            min_val = None

        if max_c is not None:
            ok, msg = _validate_bound(max_c, "max")
            if not ok:
                return AssertionResult(display, False, msg)
            max_val = int(msg)
        else:
            max_val = None

        if min_val is not None and max_val is not None and min_val > max_val:
            return AssertionResult(
                display, False,
                f"min ({min_val}) > max ({max_val})"
            )

        # --- evaluate ----------------------------------------------------------
        count = len(compiled.findall(screen))
        passed = True
        reasons: list[str] = [f"found {count} match(es) for {pattern!r}"]

        if min_val is not None:
            reasons.append(f"min={min_val}")
            if count < min_val:
                passed = False
        if max_val is not None:
            reasons.append(f"max={max_val}")
            if count > max_val:
                passed = False

        return AssertionResult(display, passed, ", ".join(reasons))
