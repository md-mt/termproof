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


class WaitForRegex:
    """Wait until terminal screen or raw output matches a regular expression.

    Recipe usage::

        {
          "action": "wait_for_regex",
          "pattern": "Dashboard .* \\d+/\\d+",
          "timeout_seconds": 10
        }

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
        pattern = step.get("pattern")
        if not pattern:
            return StepResult(display, False, "missing required field 'pattern'", session.screen)

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
            return StepResult(display, False, f"invalid regex {pattern!r}: {exc}", session.screen)

        timeout = float(step.get("timeout_seconds", 10))
        poll = float(step.get("poll_seconds", 0.05))
        search_raw = bool(step.get("search_raw_output", True))
        deadline = time.monotonic() + timeout

        while time.monotonic() < deadline:
            session.read_available(poll)
            haystack = session.screen
            if search_raw:
                haystack = haystack + "\n" + session.raw_output
            match = compiled.search(haystack)
            if match:
                snippet = (match.group(0)[:120] + "…") if len(match.group(0)) > 120 else match.group(0)
                return StepResult(display, True, f"matched {snippet!r}", session.screen)
            if not session.is_alive():
                session.read_available(0)
                haystack = session.screen + "\n" + session.raw_output
                if compiled.search(haystack):
                    return StepResult(display, True, "matched after process exit", session.screen)
                break

        return StepResult(display, False, f"timed out waiting for regex {pattern!r}", session.screen)
