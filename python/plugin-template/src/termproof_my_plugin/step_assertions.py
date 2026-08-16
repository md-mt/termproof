"""Example step-aware assertion for TermProof.

Implements ``step_screen_matches`` — asserts a regex matches the screen
captured after a named step, rather than the final screen. Register it in
config:

.. code-block:: yaml

   assertions:
     step_screen_matches: termproof_my_plugin.step_assertions:StepScreenMatches

Protocol compatibility:
- Requires a TermProof that supplies per-step screens to assertions
- Loads and runs on older TermProof too: ``steps`` is keyword-only with a
  default, so a runner that does not know about it calls this unchanged and the
  assertion reports that the screens were unavailable
- ``evaluate(recipe, assertion, screen, raw_output, exit_code, *, steps=None)
  -> AssertionResult``

An assertion opts into per-step screens purely by declaring a ``steps``
parameter — see ``ScreenCount`` in ``assertions.py`` for one that does not and
is called with the original five arguments. ``**kwargs`` alone does not opt in,
so a wrapper that forwards unrecognised arguments to another assertion stays
safe. See ``docs/protocol.md`` for the full availability matrix.
"""

from __future__ import annotations

import re
from typing import Any

from termproof.models import AssertionResult, Recipe, StepResult


class StepScreenMatches:
    """Assert a regex matches the screen captured after a named step.

    Recipe usage::

        {
          "type": "step_screen_matches",
          "step": "open dashboard",
          "pattern": "Dashboard .* \\d+/\\d+"
        }

    ``step`` matches ``StepResult.name``: the recipe step's ``name`` when it
    sets one, and ``"<index>:<action>"`` when it does not.
    """

    name = "step_screen_matches"

    def evaluate(
        self,
        recipe: Recipe,
        assertion: dict[str, Any],
        screen: str,
        raw_output: str,
        exit_code: int | None,
        *,
        steps: list[StepResult] | None = None,
    ) -> AssertionResult:
        display = str(assertion.get("name", self.name))

        step_name = assertion.get("step")
        if not isinstance(step_name, str) or not step_name:
            return AssertionResult(display, False, "missing required field 'step'")

        pattern = assertion.get("pattern")
        if not isinstance(pattern, str) or not pattern:
            return AssertionResult(display, False, "missing required field 'pattern'")
        try:
            compiled = re.compile(pattern)
        except re.error as exc:
            return AssertionResult(display, False, f"invalid regex {pattern!r}: {exc}")

        if steps is None:
            return AssertionResult(
                display,
                False,
                "per-step screens are unavailable: this TermProof, or this "
                "execution mode, does not supply them",
            )

        match = next((step for step in steps if step.name == step_name), None)
        if match is None:
            ran = ", ".join(repr(step.name) for step in steps) or "no steps ran"
            return AssertionResult(display, False, f"no step named {step_name!r}: {ran}")

        found = compiled.search(match.screen) is not None
        return AssertionResult(
            display,
            found,
            f"{pattern!r} {'matches' if found else 'does not match'} "
            f"the screen after {step_name!r}",
        )
