from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from .models import AssertionResult, Recipe, StepResult


class ExecutionMode(Protocol):
    """Protocol for pluggable execution strategies."""

    name: str

    def execute(
        self,
        runner: Any,  # VerificationRunner (forward ref to avoid circular import)
        recipe: Recipe,
        run_dir: Path,
    ) -> tuple[list[StepResult], list[AssertionResult], str, int | None, str]:
        ...


class ScriptedPtyMode:
    """PTY-based scripted execution (the current default)."""

    name = "scripted_pty"

    def execute(self, runner: Any, recipe: Recipe, run_dir: Path):
        return runner._run_pty(recipe, run_dir)


class ScriptedProcessMode:
    """Process-mode scripted execution (non-PTY)."""

    name = "scripted_process"

    def execute(self, runner: Any, recipe: Recipe, run_dir: Path):
        return runner._run_process(recipe, run_dir)


class AgentDrivenMode:
    """Agent-driven execution mode."""

    name = "agent_driven"

    def execute(self, runner: Any, recipe: Recipe, run_dir: Path):
        return runner._run_agent_driven(recipe, run_dir)
