from __future__ import annotations

import inspect
import time
from dataclasses import replace
from functools import cache
from pathlib import Path
from typing import Any

from .agent_driven import AgentDrivenRunner, AgentRunner, CodexCliAgentRunner
from .config import (
    EvidenceConfig,
    VerifierConfig,
)
from .evidence import new_run_dir, render_artifacts, write_result_files
from .models import (
    AssertionResult,
    Recipe,
    RunResult,
    StepResult,
    score_from_assertions,
)
from .protocols import SessionBackend
from .registry import Registry, import_class
from .screen import replay_cast
from .session import TerminalSession

# -- registry builders -------------------------------------------------------

SESSION_BACKEND_ALIASES = {
    "pexpect": "termproof.builtin_session:PexpectBackend",
    "pexpect_asciinema": "termproof.builtin_session:PexpectAsciinemaBackend",
    "docker": "termproof.builtin_session:DockerSessionBackend",
    "tmux": "termproof.tmux_session:TmuxBackend",
}


def _build_step_registry(config: VerifierConfig) -> Registry[Any]:
    registry: Registry[Any] = Registry()
    for name, qualname in config.steps.items():
        cls = import_class(qualname)
        registry.register(name, lambda c=cls: c())
    return registry


def _build_assertion_registry(config: VerifierConfig) -> Registry[Any]:
    registry: Registry[Any] = Registry()
    for name, qualname in config.assertions.items():
        cls = import_class(qualname)
        registry.register(name, lambda c=cls: c())
    return registry


@cache
def _evaluate_wants_steps(evaluate: Any) -> bool:
    """Whether an assertion's ``evaluate`` opts into the per-step screens.

    Opting in means declaring a parameter named ``steps``, the same shape of
    opt-in as ``from_config`` on evidence plugins. A bare ``**kwargs`` does not
    count: an assertion that forwards unrecognised arguments to another
    assertion written against the older signature would break if we passed
    ``steps`` into it.
    """
    try:
        parameters = inspect.signature(evaluate).parameters
    except (TypeError, ValueError):
        return False
    parameter = parameters.get("steps")
    return parameter is not None and parameter.kind is not inspect.Parameter.POSITIONAL_ONLY


def _build_reporter_registry(config: VerifierConfig) -> Registry[Any]:
    registry: Registry[Any] = Registry()
    for name, qualname in config.reporters.items():
        cls = import_class(qualname)
        registry.register(name, lambda c=cls: c())
    return registry


def _construct_evidence_plugin(cls: type, evidence: EvidenceConfig) -> Any:
    """Instantiate a renderer or video backend, passing evidence config if wanted.

    Plugins opt in by exposing ``from_config``. Ones that do not — including
    every third-party plugin written against the existing protocols — keep being
    constructed with no arguments.
    """
    factory = getattr(cls, "from_config", None)
    return cls() if factory is None else factory(evidence)


def _build_renderer_registry(config: VerifierConfig) -> Registry[Any]:
    registry: Registry[Any] = Registry()
    for name, qualname in config.screen_renderers.items():
        cls = import_class(qualname)
        registry.register(name, lambda c=cls: _construct_evidence_plugin(c, config.evidence))
    return registry


def _build_execution_mode_registry(config: VerifierConfig) -> Registry[Any]:
    registry: Registry[Any] = Registry()
    for name, qualname in config.execution_modes.items():
        cls = import_class(qualname)
        registry.register(name, lambda c=cls: c())
    return registry


def _build_agent_runner_registry(config: VerifierConfig) -> Registry[Any]:
    registry: Registry[Any] = Registry()
    for name, qualname in config.agent_runners.items():
        cls = import_class(qualname)
        registry.register(name, lambda c=cls: c())
    return registry


def _build_video_backend_registry(config: VerifierConfig) -> Registry[Any]:
    registry: Registry[Any] = Registry()
    for name, qualname in config.video_backends.items():
        cls = import_class(qualname)
        registry.register(name, lambda c=cls: _construct_evidence_plugin(c, config.evidence))
    return registry


def _build_artifact_publisher_registry(config: VerifierConfig) -> Registry[Any]:
    """Register configured publishers without importing them.

    Unlike the other registries, this one resolves the class on demand: a run
    never publishes, so an artifact store whose module needs an optional
    dependency must not be able to break ``termproof run`` by merely being
    configured.
    """
    registry: Registry[Any] = Registry()
    for name, qualname in config.artifact_publishers.items():
        registry.register(name, lambda q=qualname: import_class(q)())
    return registry


def _resolve_session_backend(config: VerifierConfig) -> SessionBackend:
    qualname = SESSION_BACKEND_ALIASES.get(config.session_backend, config.session_backend)
    cls = import_class(qualname)
    if qualname == "termproof.builtin_session:DockerSessionBackend":
        return cls(config.docker)  # type: ignore[return-value]
    return cls()  # type: ignore[return-value]


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
        self.artifact_publisher_registry = _build_artifact_publisher_registry(self.config)
        self.session_backend = _resolve_session_backend(self.config)

    def run(
        self,
        recipe: Recipe,
        out_dir: Path = Path(".termproof/runs"),
        render_video: bool = False,
        video_fps: int | None = None,
        renderer: str = "default",
        renderer_argv: list[str] | None = None,
        screen_renderer_name: str = "svg",
        video_backend_name: str = "agg_ffmpeg",
    ) -> RunResult:
        start = time.monotonic()
        # An explicit argument wins; otherwise the configured fps is the last
        # step of the same cascade the CLI entry points already follow.
        if video_fps is None:
            video_fps = self.config.evidence.video.fps
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
            evidence_config=self.config.evidence,
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

    def run_agent_driven(
        self,
        recipe: Recipe,
        run_dir: Path,
    ) -> tuple[list[StepResult], list[AssertionResult], str, int | None, str]:
        if self.agent_runner is not None:
            agent_runner = self.agent_runner
        else:
            agent_runner = CodexCliAgentRunner.from_recipe(recipe)
        return AgentDrivenRunner(agent_runner).run(recipe, run_dir)

    def run_pty(
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
                idle_cap = self.config.defaults.idle_cap_seconds
                idle_timeout = (
                    min(idle_cap, recipe.timeout_seconds)
                    if idle_cap is not None
                    else recipe.timeout_seconds
                )
                session.wait_for_idle(0.5, idle_timeout)
            return steps, session.raw_output, session.exit_code, session.screen

    def run_process(
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
        except KeyError as err:
            raise ValueError(f"unknown step action: {action_name}") from err
        return action.execute(session, step, index)

    def evaluate_assertions(
        self,
        recipe: Recipe,
        screen: str,
        raw_output: str,
        exit_code: int | None,
        *,
        steps: list[StepResult] | None = None,
    ) -> list[AssertionResult]:
        assertions = list(recipe.assertions)
        if recipe.expect_exit_code is not None:
            assertions.append({"type": "exit_code", "value": recipe.expect_exit_code})
        return [
            self._evaluate_assertion(
                recipe, assertion, screen, raw_output, exit_code, steps=steps
            )
            for assertion in assertions
        ]

    # -- deprecated private aliases (retained for backward compatibility) -----
    # The public ``run_*`` / ``evaluate_assertions`` methods above are the
    # stable surface for ExecutionMode plugins. These underscore-prefixed
    # aliases delegate to them so existing callers keep working.

    def _run_agent_driven(
        self,
        recipe: Recipe,
        run_dir: Path,
    ) -> tuple[list[StepResult], list[AssertionResult], str, int | None, str]:
        return self.run_agent_driven(recipe, run_dir)

    def _run_pty(
        self,
        recipe: Recipe,
        run_dir: Path,
    ) -> tuple[list[StepResult], str, int | None, str]:
        return self.run_pty(recipe, run_dir)

    def _run_process(
        self,
        recipe: Recipe,
        run_dir: Path,
    ) -> tuple[list[StepResult], str, int | None, str]:
        return self.run_process(recipe, run_dir)

    def _evaluate_assertions(
        self,
        recipe: Recipe,
        screen: str,
        raw_output: str,
        exit_code: int | None,
        *,
        steps: list[StepResult] | None = None,
    ) -> list[AssertionResult]:
        return self.evaluate_assertions(
            recipe, screen, raw_output, exit_code, steps=steps
        )

    def _evaluate_assertion(
        self,
        recipe: Recipe,
        assertion: dict[str, Any],
        screen: str,
        raw_output: str,
        exit_code: int | None,
        *,
        steps: list[StepResult] | None = None,
    ) -> AssertionResult:
        kind = assertion["type"]
        try:
            evaluator = self.assertion_registry.get(kind)
        except KeyError as err:
            raise ValueError(f"unknown assertion type: {kind}") from err
        evaluate = evaluator.evaluate
        if _evaluate_wants_steps(getattr(evaluate, "__func__", evaluate)):
            return evaluate(recipe, assertion, screen, raw_output, exit_code, steps=steps)
        return evaluate(recipe, assertion, screen, raw_output, exit_code)


def _with_renderer_argv(recipe: Recipe, renderer_argv: list[str]) -> Recipe:
    if not renderer_argv:
        return recipe
    command = replace(recipe.command, argv=[*recipe.command.argv, *renderer_argv])
    return replace(recipe, command=command)
