from __future__ import annotations

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
