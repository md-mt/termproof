from __future__ import annotations

import re
import time
from typing import Any, Protocol

from .models import StepResult
from .session import TerminalSession


class StepAction(Protocol):
    """Protocol for pluggable step actions."""

    name: str  # class-level identifier matching recipe "action" field

    def execute(
        self,
        session: TerminalSession,
        step: dict[str, Any],
        index: int,
    ) -> StepResult:
        ...


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
        detail = f"stable for {stable}s" if passed else "timed out waiting for idle"
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
        pattern_str = step.get("pattern")
        if pattern_str is None:
            return StepResult(
                display,
                False,
                "wait_for_regex requires 'pattern' field",
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

        timeout = float(step.get("timeout_seconds", 10))
        deadline = time.monotonic() + timeout
        last_match_detail: str | None = None

        def _format_match(m: re.Match[str]) -> str:
            named = m.groupdict()
            if named:
                pairs = ", ".join(f"{k}={v!r}" for k, v in named.items())
                return f"matched {pattern_str!r} -> {pairs} (full: {m.group(0)!r})"
            if m.groups():
                return f"matched {pattern_str!r} -> groups={m.groups()!r} (full: {m.group(0)!r})"
            return f"matched {pattern_str!r} -> match={m.group(0)!r}"

        def _search(text: str) -> re.Match[str] | None:
            if not text:
                return None
            return pattern.search(text)

        while True:
            # Poll for new terminal data (same cadence as wait_for_text)
            session.read_available(0.05)
            combined = (getattr(session, "screen", "") or "") + "\n" + (getattr(session, "raw_output", "") or "")

            m = _search(combined)
            if m is None:
                m = _search(getattr(session, "screen", "") or "")
            if m is None:
                m = _search(getattr(session, "raw_output", "") or "")

            if m:
                return StepResult(display, True, _format_match(m), getattr(session, "screen", ""))

            if time.monotonic() >= deadline:
                break

            if hasattr(session, "is_alive") and not session.is_alive():
                session.read_available(0)
                combined = (getattr(session, "screen", "") or "") + "\n" + (getattr(session, "raw_output", "") or "")
                final = _search(combined) or _search(getattr(session, "screen", "") or "") or _search(getattr(session, "raw_output", "") or "")
                if final:
                    return StepResult(display, True, _format_match(final), getattr(session, "screen", ""))
                break

        return StepResult(
            display,
            False,
            f"timed out waiting for regex {pattern_str!r} after {timeout}s",
            getattr(session, "screen", ""),
        )
