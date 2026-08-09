from __future__ import annotations

import math
import re
import time
from typing import Any

from .models import StepResult
from .protocols import StepAction as StepAction
from .session import TerminalSession


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
        return StepResult(display, passed, detail, session.screen)


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
        return StepResult(display, passed, detail, session.screen)


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
        return StepResult(display, True, "sent text", session.screen)


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
        return StepResult(display, True, "sent line", session.screen)


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
        return StepResult(display, True, f"pressed {step['key']}", session.screen)


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
        return StepResult(display, True, "slept", session.screen)


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
            return StepResult(
                display,
                False,
                f"wait_for_regex 'pattern' must be a string, got {type(pattern_str).__name__}",
                getattr(session, "screen", ""),
            )

        try:
            pattern = re.compile(pattern_str)
        except re.error as exc:
            return StepResult(
                display,
                False,
                f"invalid regex {pattern_str!r}: {exc}",
                getattr(session, "screen", ""),
            )

        # -- validate timeout -------------------------------------------------
        raw_timeout = step.get("timeout_seconds", 10)
        try:
            timeout = float(raw_timeout)
        except (TypeError, ValueError):
            return StepResult(
                display,
                False,
                f"wait_for_regex timeout_seconds must be a number, got {raw_timeout!r}",
                getattr(session, "screen", ""),
            )
        if math.isnan(timeout) or math.isinf(timeout):
            return StepResult(
                display,
                False,
                f"wait_for_regex timeout_seconds must be finite, got {timeout}",
                getattr(session, "screen", ""),
            )
        if timeout <= 0:
            return StepResult(
                display,
                False,
                f"wait_for_regex timeout_seconds must be > 0, got {timeout}",
                getattr(session, "screen", ""),
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

        # Search screen and raw_output independently — concatenating
        # with '\n' creates synthetic boundaries that never existed
        # in the terminal.
        while True:
            # Poll for new terminal data (same cadence as wait_for_text)
            session.read_available(0.05)
            screen_text = getattr(session, "screen", "") or ""
            raw_text = getattr(session, "raw_output", "") or ""

            m = _search(screen_text) or _search(raw_text)
            if m:
                return StepResult(display, True, _format_match(m), screen_text)

            if time.monotonic() >= deadline:
                break

            if hasattr(session, "is_alive") and not session.is_alive():
                session.read_available(0)
                screen_text = getattr(session, "screen", "") or ""
                raw_text = getattr(session, "raw_output", "") or ""
                final = _search(screen_text) or _search(raw_text)
                if final:
                    return StepResult(display, True, _format_match(final), screen_text)
                break

        return StepResult(
            display,
            False,
            f"timed out waiting for regex {pattern_str!r} after {timeout}s",
            getattr(session, "screen", ""),
        )
