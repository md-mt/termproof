from __future__ import annotations

import math
import re
import time
from typing import Any

from .models import StepResult
from .protocols import StepAction as StepAction
from .screen import ScreenCapture, capture_screen
from .session import TerminalSession


def step_result(
    name: str,
    passed: bool,
    detail: str,
    session: Any,
) -> StepResult:
    """A ``StepResult`` carrying whatever screen the session can report.

    One read via :func:`~termproof.screen.capture_screen`, so the text on the
    step and the grid its screenshot is rendered from are the same instant. A
    session with no grid to give yields ``screen_attributed=None``, and the
    screenshot falls back to the text exactly as before.

    Public so a third-party ``StepAction`` can pick up attributed step
    screenshots by calling it instead of building a ``StepResult`` by hand.
    """
    capture = capture_screen(session)
    return StepResult(name, passed, detail, capture.screen, capture.attributed)


class WaitForText:
    name = "wait_for_text"

    def execute(
        self,
        session: TerminalSession,
        step: dict[str, Any],
        index: int,
    ) -> StepResult:
        text = step["text"]
        display = step.get("name", f"{index}:{self.name}")
        timeout = float(step.get("timeout_seconds", 10))
        passed = session.wait_for_text(text, timeout)
        detail = f"found {text!r}" if passed else f"timed out waiting for {text!r}"
        return step_result(display, passed, detail, session)


class WaitForIdle:
    name = "wait_for_idle"

    def execute(
        self,
        session: TerminalSession,
        step: dict[str, Any],
        index: int,
    ) -> StepResult:
        display = step.get("name", f"{index}:{self.name}")
        stable = float(step.get("stable_seconds", 0.5))
        timeout = float(step.get("timeout_seconds", 10))
        passed = session.wait_for_idle(stable, timeout)
        if passed:
            detail = f"stable for {stable}s"
        elif not session.raw_output:
            # The stable window never armed because the session produced nothing
            # at all — distinct from output that arrived but never settled.
            detail = "no output observed from the session"
        else:
            detail = "timed out waiting for idle"
        return step_result(display, passed, detail, session)


class SendText:
    name = "send_text"

    def execute(
        self,
        session: TerminalSession,
        step: dict[str, Any],
        index: int,
    ) -> StepResult:
        display = step.get("name", f"{index}:{self.name}")
        session.send_text(step["text"])
        return step_result(display, True, "sent text", session)


class SendLine:
    name = "send_line"

    def execute(
        self,
        session: TerminalSession,
        step: dict[str, Any],
        index: int,
    ) -> StepResult:
        display = step.get("name", f"{index}:{self.name}")
        session.send_line(step.get("text", ""))
        return step_result(display, True, "sent line", session)


class Press:
    name = "press"

    def execute(
        self,
        session: TerminalSession,
        step: dict[str, Any],
        index: int,
    ) -> StepResult:
        display = step.get("name", f"{index}:{self.name}")
        session.press(step["key"])
        return step_result(display, True, f"pressed {step['key']}", session)


class Sleep:
    name = "sleep"

    def execute(
        self,
        session: TerminalSession,
        step: dict[str, Any],
        index: int,
    ) -> StepResult:
        display = step.get("name", f"{index}:{self.name}")
        time.sleep(float(step.get("seconds", 1)))
        session.read_available(0)
        return step_result(display, True, "slept", session)


class WaitForRegex:
    """Wait until terminal output matches a regular expression.

    Config:
        pattern (str, required): Python regex pattern to match.
        timeout_seconds (float, optional): max wait time, defaults to 10.
        name (str, optional): human-readable step name for reports.

    On success, detail includes match-group evidence (named groups if present,
    else positional groups, else the full match). On invalid regex, returns a
    failed StepResult with a clear validation message — never raises raw re.error.
    """

    name = "wait_for_regex"

    def execute(
        self,
        session: TerminalSession,
        step: dict[str, Any],
        index: int,
    ) -> StepResult:
        display = step.get("name", f"{index}:{self.name}")

        # -- validate pattern -------------------------------------------------
        pattern_str = step.get("pattern")
        if not isinstance(pattern_str, str):
            return step_result(
                display,
                False,
                f"wait_for_regex 'pattern' must be a string, got {type(pattern_str).__name__}",
                session,
            )

        try:
            pattern = re.compile(pattern_str)
        except re.error as exc:
            return step_result(display, False, f"invalid regex {pattern_str!r}: {exc}", session)

        # -- validate timeout -------------------------------------------------
        raw_timeout = step.get("timeout_seconds", 10)
        try:
            timeout = float(raw_timeout)
        except (TypeError, ValueError):
            return step_result(
                display,
                False,
                f"wait_for_regex timeout_seconds must be a number, got {raw_timeout!r}",
                session,
            )
        if math.isnan(timeout) or math.isinf(timeout):
            return step_result(
                display, False, f"wait_for_regex timeout_seconds must be finite, got {timeout}", session
            )
        if timeout <= 0:
            return step_result(
                display, False, f"wait_for_regex timeout_seconds must be > 0, got {timeout}", session
            )

        deadline = time.monotonic() + timeout

        def _format_match(m: re.Match[str]) -> str:
            named = m.groupdict()
            parts: list[str] = []
            if named:
                pairs = ", ".join(f"{k}={v!r}" for k, v in named.items())
                parts.append(pairs)
            if m.groups():
                # Show positional groups even when named groups also exist
                parts.append(f"groups={m.groups()!r}")
            if parts:
                return f"matched {pattern_str!r} -> {'; '.join(parts)} (full: {m.group(0)!r})"
            return f"matched {pattern_str!r} -> match={m.group(0)!r}"

        def _search(text: str) -> re.Match[str] | None:
            if not text:
                return None
            return pattern.search(text)

        def _matched(capture: ScreenCapture) -> StepResult | None:
            raw_text = getattr(session, "raw_output", "") or ""
            match = _search(capture.screen) or _search(raw_text)
            if match is None:
                return None
            # Built from the capture that was searched, not from a fresh read:
            # the screen this step reports is the one the pattern matched.
            return StepResult(
                display, True, _format_match(match), capture.screen, capture.attributed
            )

        # Search screen and raw_output independently — concatenating
        # with '\n' creates synthetic boundaries that never existed
        # in the terminal.
        while True:
            # Poll for new terminal data (same cadence as wait_for_text)
            session.read_available(0.05)
            found = _matched(capture_screen(session))
            if found is not None:
                return found

            if time.monotonic() >= deadline:
                break

            if hasattr(session, "is_alive") and not session.is_alive():
                session.read_available(0)
                found = _matched(capture_screen(session))
                if found is not None:
                    return found
                break

        return step_result(
            display, False, f"timed out waiting for regex {pattern_str!r} after {timeout}s", session
        )
