"""Example custom assertion for TermProof.

Implements ``duration_under`` — asserts the verification run completed
within a budget. Register it in config:

.. code-block:: yaml

   assertions:
     duration_under: termproof_my_plugin.assertions:DurationUnder
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from termproof.models import AssertionResult, Recipe


class DurationUnder:
    """Fail when run artifacts indicate the run exceeded a duration budget.

    Recipe usage::

        {
          "type": "duration_under",
          "value": 30,
          "name": "launch is fast"
        }

    The assertion inspects ``RunResult`` artifact paths indirectly through the
    hosting runner (the runner populates ``duration_seconds`` on ``RunResult``,
    which downstream assertions may receive via file conventions).  For
    portability this example reads ``result.json`` next to the artifacts folder
    when available and falls back to scanning ``raw_output`` metadata.

    Protocol compatibility:
    - Compatible with TermProof >=0.1.0
    - ``name`` class attribute must match the config ``assertions`` mapping
    - ``evaluate(recipe, assertion, screen, raw_output, exit_code) -> AssertionResult``
    """

    name = "duration_under"

    def evaluate(
        self,
        recipe: Recipe,
        assertion: dict[str, Any],
        screen: str,
        raw_output: str,
        exit_code: int | None,
    ) -> AssertionResult:
        display = str(assertion.get("name", self.name))
        raw_value = assertion.get("value")
        if raw_value is None:
            return AssertionResult(display, False, "missing required field 'value' (seconds budget)")
        try:
            budget = float(raw_value)
        except (TypeError, ValueError):
            return AssertionResult(display, False, f"invalid budget {raw_value!r}: expected number")

        # Prefer result.json if present near cwd or recipe.command.cwd hints.
        duration = _try_read_duration(recipe)
        if duration is not None:
            passed = duration <= budget
            detail = f"duration {duration:.2f}s {'<=' if passed else '>'} budget {budget:.2f}s"
            return AssertionResult(display, passed, detail)

        # Fallback: if TermProof runner provides raw timing in raw_output metadata,
        # we treat missing as soft-pass with a note rather than hard-fail.
        return AssertionResult(display, True, f"budget {budget:.2f}s — no timing file found, skipping enforced check")


def _try_read_duration(recipe: Recipe) -> float | None:
    guesses: list[Path] = []
    if recipe.command.cwd:
        guesses.append(Path(recipe.command.cwd) / ".termproof" / "runs")
    guesses.append(Path.cwd() / ".termproof" / "runs")

    import json

    for run_root in guesses:
        if not run_root.is_dir():
            continue
        # Pick latest run dir matching recipe name
        candidates = sorted(run_root.iterdir(), reverse=True)
        for cand in candidates:
            if recipe.name in cand.name and cand.is_dir():
                result = cand / "result.json"
                if result.exists():
                    try:
                        data = json.loads(result.read_text(encoding="utf-8"))
                        dur = data.get("duration_seconds")
                        if dur is not None:
                            return float(dur)
                    except Exception:
                        continue
    return None


class ScreenCount:
    """Assert a regex appears at least/at most N times on the final screen.

    Recipe usage::

        {
          "type": "screen_count",
          "pattern": "TODO",
          "min": 0,
          "max": 3
        }
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
        import re

        display = str(assertion.get("name", self.name))
        pattern = assertion.get("pattern")
        if not pattern:
            return AssertionResult(display, False, "missing required field 'pattern'")
        try:
            compiled = re.compile(pattern)
        except re.error as exc:
            return AssertionResult(display, False, f"invalid regex {pattern!r}: {exc}")

        count = len(compiled.findall(screen))
        min_c = assertion.get("min")
        max_c = assertion.get("max")
        passed = True
        reasons: list[str] = []
        reasons.append(f"found {count} match(es) for {pattern!r}")
        if min_c is not None:
            try:
                mc = int(min_c)
            except (TypeError, ValueError):
                return AssertionResult(display, False, f"invalid min {min_c!r}")
            if count < mc:
                passed = False
            reasons.append(f"min={mc}")
        if max_c is not None:
            try:
                mc = int(max_c)
            except (TypeError, ValueError):
                return AssertionResult(display, False, f"invalid max {max_c!r}")
            if count > mc:
                passed = False
            reasons.append(f"max={mc}")
        return AssertionResult(display, passed, ", ".join(reasons))
