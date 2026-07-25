from __future__ import annotations

from pathlib import Path
from typing import Any, Protocol

from .models import AssertionResult, Recipe, StepResult


class ExecutionMode(Protocol):
    """Protocol for pluggable execution strategies."""

    name: str

    def execute(
        self,
        runner: Any,  # VerificationRunner
        recipe: Recipe,
        run_dir: Path,
    ) -> tuple[list[StepResult], list[AssertionResult], str, int | None, str]:
        ...


class ScriptedPtyMode:
    """PTY-based scripted execution — steps run interactively via terminal session."""

    name = "scripted_pty"

    def execute(
        self,
        runner: Any,
        recipe: Recipe,
        run_dir: Path,
    ) -> tuple[list[StepResult], list[AssertionResult], str, int | None, str]:
        steps, raw_output, exit_code, screen = runner._run_pty(recipe, run_dir)
        assertions = runner._evaluate_assertions(recipe, screen, raw_output, exit_code)
        return steps, assertions, raw_output, exit_code, screen


class ScriptedProcessMode:
    """Process-mode scripted execution — runs to completion, then evaluates."""

    name = "scripted_process"

    def execute(
        self,
        runner: Any,
        recipe: Recipe,
        run_dir: Path,
    ) -> tuple[list[StepResult], list[AssertionResult], str, int | None, str]:
        steps, raw_output, exit_code, screen = runner._run_process(recipe, run_dir)
        assertions = runner._evaluate_assertions(recipe, screen, raw_output, exit_code)
        return steps, assertions, raw_output, exit_code, screen


class AgentDrivenMode:
    """Agent-driven execution — delegates to an AI agent for interactive verification."""

    name = "agent_driven"

    def execute(
        self,
        runner: Any,
        recipe: Recipe,
        run_dir: Path,
    ) -> tuple[list[StepResult], list[AssertionResult], str, int | None, str]:
        return runner._run_agent_driven(recipe, run_dir)
