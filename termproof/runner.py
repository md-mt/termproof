from __future__ import annotations

import time
from dataclasses import replace
from pathlib import Path
from typing import Any

from .agent_driven import AgentDrivenRunner, AgentRunner, CodexCliAgentRunner
from .config import (
    CURRENT_PLUGIN_MODULE_PREFIX,
    LEGACY_PLUGIN_MODULE_PREFIX,
    VerifierConfig,
)
from .evidence import new_run_dir, render_artifacts, write_result_files
from .models import (
    AssertionResult,
    Recipe,
    RunResult,
    StepResult,
    load_recipe,
    score_from_assertions,
)
from .protocols import SessionBackend
from .registry import Registry
from .screen import replay_cast
from .session import TerminalSession


# -- registry builders -------------------------------------------------------

SESSION_BACKEND_ALIASES = {
    "pexpect": "termproof.builtin_session:PexpectAsciinemaBackend",
    "docker": "termproof.builtin_session:DockerSessionBackend",
}


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


def _build_reporter_registry(config: VerifierConfig) -> Registry[Any]:
    registry: Registry[Any] = Registry()
    for name, qualname in config.reporters.items():
        cls = _import_class(qualname)
        registry.register(name, lambda c=cls: c())
    return registry


def _build_renderer_registry(config: VerifierConfig) -> Registry[Any]:
    registry: Registry[Any] = Registry()
    for name, qualname in config.screen_renderers.items():
        cls = _import_class(qualname)
        registry.register(name, lambda c=cls: c())
    return registry


def _build_execution_mode_registry(config: VerifierConfig) -> Registry[Any]:
    registry: Registry[Any] = Registry()
    for name, qualname in config.execution_modes.items():
        cls = _import_class(qualname)
        registry.register(name, lambda c=cls: c())
    return registry


def _build_agent_runner_registry(config: VerifierConfig) -> Registry[Any]:
    registry: Registry[Any] = Registry()
    for name, qualname in config.agent_runners.items():
        cls = _import_class(qualname)
        registry.register(name, lambda c=cls: c())
    return registry


def _build_video_backend_registry(config: VerifierConfig) -> Registry[Any]:
    registry: Registry[Any] = Registry()
    for name, qualname in config.video_backends.items():
        cls = _import_class(qualname)
        registry.register(name, lambda c=cls: c())
    return registry


def _resolve_session_backend(config: VerifierConfig) -> SessionBackend:
    qualname = SESSION_BACKEND_ALIASES.get(config.session_backend, config.session_backend)
    cls = _import_class(qualname)
    if qualname == "termproof.builtin_session:DockerSessionBackend":
        return cls(config.docker)  # type: ignore[return-value]
    return cls()  # type: ignore[return-value]


def _import_class(qualname: str) -> type:
    """Import a plugin class from a ``module.path:ClassName`` reference.

    Configuration written for the pre-TermProof package can keep using its
    plugin module prefix. This narrow alias avoids a compatibility shim package
    while ensuring external plugin configuration remains loadable.
    """
    if ":" not in qualname:
        raise ValueError(
            f"expected 'module.path:ClassName', got {qualname!r}"
        )
    module_name, class_name = qualname.split(":", 1)
    if module_name.startswith(LEGACY_PLUGIN_MODULE_PREFIX):
        module_name = (
            CURRENT_PLUGIN_MODULE_PREFIX
            + module_name.removeprefix(LEGACY_PLUGIN_MODULE_PREFIX)
        )
    import importlib

    module = importlib.import_module(module_name)
    return getattr(module, class_name)


def _resolve_execution_mode_name(recipe: Recipe) -> str:
    """Map recipe execution + pty to a config registry name."""
    if recipe.execution == "agent-driven":
        return "agent_driven"
    if recipe.command.pty:
        return "scripted_pty"
    return "scripted_process"


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
        self.reporter_registry = _build_reporter_registry(self.config)
        self.screen_renderer_registry = _build_renderer_registry(self.config)
        self.execution_mode_registry = _build_execution_mode_registry(self.config)
        self.agent_runner_registry = _build_agent_runner_registry(self.config)
        self.video_backend_registry = _build_video_backend_registry(self.config)
        self.session_backend = _resolve_session_backend(self.config)

    def run(
        self,
        recipe: Recipe,
        out_dir: Path = Path(".termproof/runs"),
        render_video: bool = False,
        video_fps: int = 60,
        renderer: str = "default",
        renderer_argv: list[str] | None = None,
        screen_renderer_name: str = "svg",
        video_backend_name: str = "agg_ffmpeg",
    ) -> RunResult:
        start = time.monotonic()
        runnable_recipe = _with_renderer_argv(recipe, renderer_argv or [])
        run_dir = new_run_dir(out_dir, recipe.name, renderer)
        run_dir.mkdir(parents=True, exist_ok=True)
        mode_name = _resolve_execution_mode_name(runnable_recipe)
        mode = self.execution_mode_registry.get(mode_name)
        steps, assertions, raw_output, exit_code, screen = mode.execute(
            self, runnable_recipe, run_dir
        )
        screen_renderer = self.screen_renderer_registry.get(screen_renderer_name)
        video_backend = self.video_backend_registry.get(video_backend_name)
        artifacts = render_artifacts(
            run_dir,
            render_video,
            video_fps,
            steps=steps,
            cols=recipe.cols,
            rows=recipe.rows,
            screen_renderer=screen_renderer,
            video_backend=video_backend,
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
        if self.agent_runner is not None:
            agent_runner = self.agent_runner
        else:
            agent_runner = CodexCliAgentRunner.from_recipe(recipe)
        return AgentDrivenRunner(agent_runner).run(recipe, run_dir)

    def _run_pty(
        self,
        recipe: Recipe,
        run_dir: Path,
    ) -> tuple[list[StepResult], str, int | None, str]:
        steps: list[StepResult] = []
        cast_path = run_dir / "session.cast"
        with self.session_backend.create_session(
            recipe.command.argv,
            cast_path,
            recipe.command.cwd,
            recipe.command.env,
            recipe.cols,
            recipe.rows,
        ) as session:
            for index, step in enumerate(recipe.steps, start=1):
                try:
                    step_result = self._run_step(session, index, step)
                except Exception as exc:
                    action_name = step["action"]
                    name = step.get("name", f"{index}:{action_name}")
                    step_result = StepResult(name, False, str(exc), session.screen)
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
        with self.session_backend.create_session(
            recipe.command.argv,
            cast_path,
            recipe.command.cwd,
            recipe.command.env,
            recipe.cols,
            recipe.rows,
        ) as session:
            steps: list[StepResult] = []
            for index, step in enumerate(recipe.steps, start=1):
                try:
                    step_result = self._run_step(session, index, step)
                except Exception as exc:
                    action_name = step["action"]
                    name = step.get("name", f"{index}:{action_name}")
                    step_result = StepResult(name, False, str(exc), session.screen)
                steps.append(step_result)
                if not step_result.passed:
                    break
            # Wait for process to finish so exit_code is captured.
            # Per-step deadlines were already enforced by _run_step above;
            # this is the overall recipe timeout cap for post-step teardown.
            session.wait_for_exit(recipe.timeout_seconds)
            raw_output = session.raw_output
            exit_code = session.exit_code
        screen, _, _ = replay_cast(cast_path)
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
