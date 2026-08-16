"""Example custom step action for TermProof.

Implements ``wait_for_regex`` — waits for a regex match in the terminal screen
or raw output. Register it in ``.termproof/config.yaml`` or
``~/.config/termproof/config.yaml``:

.. code-block:: yaml

   steps:
     wait_for_regex: termproof_my_plugin.steps:WaitForRegex
"""

from __future__ import annotations

import re
import time
from typing import Any

from termproof.models import StepResult
from termproof.session import TerminalSession


def _build_haystack(session: TerminalSession, search_raw: bool) -> str:
    """Build the haystack string from session screen and optionally raw output."""
    if search_raw:
        return session.screen + "\n" + session.raw_output
    return session.screen


class WaitForRegex:
    """Wait until terminal screen or raw output matches a regular expression.

    Recipe usage::

        {
          "action": "wait_for_regex",
          "pattern": "Dashboard .* \\\\d+/\\\\d+",
          "timeout_seconds": 10
        }

    The ``search_raw_output`` option (default true) controls whether the
    accumulated raw output is included in the haystack. When false, only the
    visible screen is searched — this contract is honored in both the polling
    loop and the process-exit path.

    Protocol compatibility:
    - Compatible with TermProof >=0.1.0
    - ``name`` class attribute must match the key in config ``steps`` mapping
    - ``execute(session, step, index) -> StepResult`` signature required
    """

    name = "wait_for_regex"

    def execute(
        self,
        session: TerminalSession,
        step: dict[str, Any],
        index: int,
    ) -> StepResult:
        display = step.get("name", f"{index}:{self.name}")

        # --- validate pattern -------------------------------------------------
        pattern = step.get("pattern")
        if not pattern:
            return StepResult(
                display, False, "missing required field 'pattern'", session.screen
            )
        if not isinstance(pattern, str):
            return StepResult(
                display, False,
                f"pattern must be a string, got {type(pattern).__name__}",
                session.screen,
            )

        # --- build regex flags -------------------------------------------------
        flags = 0
        if step.get("ignore_case"):
            flags |= re.IGNORECASE
        if step.get("multiline"):
            flags |= re.MULTILINE
        if step.get("dotall"):
            flags |= re.DOTALL

        try:
            compiled = re.compile(pattern, flags)
        except re.error as exc:
            return StepResult(
                display, False,
                f"invalid regex {pattern!r}: {exc}",
                session.screen,
            )

        # --- validate numeric controls -----------------------------------------
        try:
            timeout = float(step.get("timeout_seconds", 10))
        except (TypeError, ValueError):
            return StepResult(
                display, False,
                f"invalid timeout_seconds {step.get('timeout_seconds')!r}: "
                f"expected number",
                session.screen,
            )
        if timeout < 0:
            return StepResult(
                display, False,
                f"timeout_seconds {timeout} must be >= 0",
                session.screen,
            )

        try:
            poll = float(step.get("poll_seconds", 0.05))
        except (TypeError, ValueError):
            return StepResult(
                display, False,
                f"invalid poll_seconds {step.get('poll_seconds')!r}: "
                f"expected number",
                session.screen,
            )
        if poll <= 0:
            return StepResult(
                display, False,
                f"poll_seconds {poll} must be > 0",
                session.screen,
            )

        search_raw = bool(step.get("search_raw_output", True))
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            session.read_available(poll)
            haystack = _build_haystack(session, search_raw)
            match = compiled.search(haystack)
            if match:
                snippet = (
                    (match.group(0)[:120] + "…")
                    if len(match.group(0)) > 120
                    else match.group(0)
                )
                return StepResult(
                    display, True, f"matched {snippet!r}", session.screen
                )
            if not session.is_alive():
                # Process exited — drain final bytes, then check one last time.
                session.read_available(0)
                haystack = _build_haystack(session, search_raw)
                if compiled.search(haystack):
                    return StepResult(
                        display, True, "matched after process exit", session.screen
                    )
                break

        return StepResult(
            display, False,
            f"timed out waiting for regex {pattern!r}",
            session.screen,
        )
