from __future__ import annotations

import time
from dataclasses import replace
from pathlib import Path
from typing import Any

from .agent_driven import AgentDrivenRunner, AgentRunner, CodexCliAgentRunner
from .config import VerifierConfig
from .evidence import new_run_dir, render_artifacts, write_result_files
from .models import (
    AssertionResult,
    Recipe,
    RunResult,
    StepResult,
    load_recipe,
    score_from_assertions,
)
from .registry import Registry
from .screen import replay_cast
from .session import TerminalSession


# -- registry builders -------------------------------------------------------


def _build_step_registry(config: VerifierConfig) -> Registry[Any]:
    registry: Registry[Any] = Registry()
    for name, qualname in config.steps.items():
        cls = _import_class(qualname)
        registry.register(name, lambda c=cls: c())
    return registry


def _build_assertion_registry(config: VerifierConfig) -> Registry[Any]:
    registry: Registry[Any] = Registry()
    for name, qualname in config.assertions.items():
        cls = _import_class(qualname)
        registry.register(name, lambda c=cls: c())
    return registry


def _import_class(qualname: str) -> type:
    """Import a class from 'module.path:ClassName' string."""
    if ":" not in qualname:
        raise ValueError(
            f"expected 'module.path:ClassName', got {qualname!r}"
        )
    module_name, class_name = qualname.split(":", 1)
    import importlib

    module = importlib.import_module(module_name)
    return getattr(module, class_name)


class VerificationRunner:
    def __init__(
        self,
        agent_runner: AgentRunner | None = None,
        config: VerifierConfig | None = None,
    ) -> None:
        self.agent_runner = agent_runner
        self.config = config or VerifierConfig.builtin()
        self.step_registry = _build_step_registry(self.config)
        self.assertion_registry = _build_assertion_registry(self.config)

    def run(
        self,
        recipe: Recipe,
        out_dir: Path = Path(".tui-verifier/runs"),
        render_video: bool = False,
        video_fps: int = 60,
        renderer: str = "default",
        renderer_argv: list[str] | None = None,
    ) -> RunResult:
        start = time.monotonic()
        runnable_recipe = _with_renderer_argv(recipe, renderer_argv or [])
        run_dir = new_run_dir(out_dir, recipe.name, renderer)
        run_dir.mkdir(parents=True, exist_ok=True)
        if runnable_recipe.execution == "agent-driven":
            steps, assertions, raw_output, exit_code, screen = self._run_agent_driven(
                runnable_recipe, run_dir
            )
        elif runnable_recipe.execution != "scripted":
            raise ValueError(f"unknown execution mode: {runnable_recipe.execution}")
        elif runnable_recipe.command.pty:
            steps, raw_output, exit_code, screen = self._run_pty(runnable_recipe, run_dir)
            assertions = self._evaluate_assertions(recipe, screen, raw_output, exit_code)
        else:
            steps, raw_output, exit_code, screen = self._run_process(runnable_recipe, run_dir)
            assertions = self._evaluate_assertions(recipe, screen, raw_output, exit_code)
        artifacts = render_artifacts(
            run_dir,
            render_video,
            video_fps,
            steps=steps,
            cols=recipe.cols,
            rows=recipe.rows,
        )
        score = score_from_assertions(assertions)
        passed = all(step.passed for step in steps) and all(a.passed for a in assertions)
        result = RunResult(
            recipe_name=recipe.name,
            passed=passed,
            exit_code=exit_code,
            duration_seconds=time.monotonic() - start,
            priority=recipe.priority,
            execution=recipe.execution,
            renderer=renderer,
            score=score,
            steps=steps,
            assertions=assertions,
            artifacts=artifacts,
        )
        write_result_files(run_dir, result)
        return result

    def _run_agent_driven(
        self,
        recipe: Recipe,
        run_dir: Path,
    ) -> tuple[list[StepResult], list[AssertionResult], str, int | None, str]:
        agent_runner = self.agent_runner or CodexCliAgentRunner.from_recipe(recipe)
        return AgentDrivenRunner(agent_runner).run(recipe, run_dir)

    def _run_pty(
        self,
        recipe: Recipe,
        run_dir: Path,
    ) -> tuple[list[StepResult], str, int | None, str]:
        steps: list[StepResult] = []
        with TerminalSession(
            recipe.command.argv,
            run_dir / "session.cast",
            recipe.command.cwd,
            recipe.command.env,
            recipe.cols,
            recipe.rows,
        ) as session:
            for index, step in enumerate(recipe.steps, start=1):
                step_result = self._run_step(session, index, step)
                steps.append(step_result)
                if not step_result.passed:
                    break
            if recipe.expect_exit_code is not None:
                session.wait_for_exit(recipe.timeout_seconds)
            else:
                session.wait_for_idle(0.5, min(3, recipe.timeout_seconds))
            return steps, session.raw_output, session.exit_code, session.screen

    def _run_process(
        self,
        recipe: Recipe,
        run_dir: Path,
    ) -> tuple[list[StepResult], str, int | None, str]:
        cast_path = run_dir / "session.cast"
        with TerminalSession(
            recipe.command.argv,
            cast_path,
            recipe.command.cwd,
            recipe.command.env,
            recipe.cols,
            recipe.rows,
        ) as session:
            session.wait_for_exit(recipe.timeout_seconds)
            raw_output = session.raw_output
            exit_code = session.exit_code
        screen, _, _ = replay_cast(cast_path)
        steps = self._evaluate_output_steps(recipe, screen, raw_output)
        return steps, raw_output, exit_code, screen

    def _run_step(
        self,
        session: TerminalSession,
        index: int,
        step: dict[str, Any],
    ) -> StepResult:
        action_name = step["action"]
        try:
            action = self.step_registry.get(action_name)
        except KeyError:
            raise ValueError(f"unknown step action: {action_name}")
        return action.execute(session, step, index)

    def _evaluate_output_steps(
        self,
        recipe: Recipe,
        screen: str,
        raw_output: str,
    ) -> list[StepResult]:
        results: list[StepResult] = []
        for index, step in enumerate(recipe.steps, start=1):
            action_name = step["action"]
            name = step.get("name", f"{index}:{action_name}")
            if action_name == "wait_for_text":
                text = step["text"]
                passed = text in screen or text in raw_output
                detail = f"found {text!r}" if passed else f"missing {text!r}"
                results.append(StepResult(name, passed, detail, screen))
            elif action_name == "sleep":
                results.append(StepResult(name, True, "not needed for process mode", screen))
            else:
                detail = f"{action_name!r} requires command.pty=true"
                results.append(StepResult(name, False, detail, screen))
        return results

    def _evaluate_assertions(
        self,
        recipe: Recipe,
        screen: str,
        raw_output: str,
        exit_code: int | None,
    ) -> list[AssertionResult]:
        assertions = list(recipe.assertions)
        if recipe.expect_exit_code is not None:
            assertions.append({"type": "exit_code", "value": recipe.expect_exit_code})
        return [
            self._evaluate_assertion(recipe, assertion, screen, raw_output, exit_code)
            for assertion in assertions
        ]

    def _evaluate_assertion(
        self,
        recipe: Recipe,
        assertion: dict[str, Any],
        screen: str,
        raw_output: str,
        exit_code: int | None,
    ) -> AssertionResult:
        kind = assertion["type"]
        try:
            evaluator = self.assertion_registry.get(kind)
        except KeyError:
            raise ValueError(f"unknown assertion type: {kind}")
        return evaluator.evaluate(recipe, assertion, screen, raw_output, exit_code)


def _with_renderer_argv(recipe: Recipe, renderer_argv: list[str]) -> Recipe:
    if not renderer_argv:
        return recipe
    command = replace(recipe.command, argv=[*recipe.command.argv, *renderer_argv])
    return replace(recipe, command=command)
