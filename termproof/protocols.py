from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

from .before_after import BeforeAfterResult
from .build_info import BuildInfo
from .config import EvidenceConfig, PngRenderConfig, SvgRenderConfig, VideoConfig
from .models import AssertionResult, Recipe, RunResult, StepResult
from .session import TerminalSession

if TYPE_CHECKING:
    from .agent_driven import AgentOutcome
    from .runner import VerificationRunner


class StepAction(Protocol):
    name: str

    def execute(
        self,
        session: TerminalSession,
        step: dict[str, Any],
        index: int,
    ) -> StepResult:
        ...


class AssertionType(Protocol):
    name: str

    def evaluate(
        self,
        recipe: Recipe,
        assertion: dict[str, Any],
        screen: str,
        raw_output: str,
        exit_code: int | None,
    ) -> AssertionResult:
        ...


class ExecutionMode(Protocol):
    name: str

    def execute(
        self,
        runner: VerificationRunner,
        recipe: Recipe,
        run_dir: Path,
    ) -> tuple[list[StepResult], list[AssertionResult], str, int | None, str]:
        ...


class Reporter(Protocol):
    name: str

    def generate(
        self,
        results: list[RunResult],
        build_info: BuildInfo | None = None,
        before_after: BeforeAfterResult | None = None,
    ) -> str:
        ...


class ScreenRenderer(Protocol):
    name: str

    def render(
        self,
        text: str,
        output_path: Path,
        cols: int,
        rows: int,
    ) -> None:
        ...


class VideoBackend(Protocol):
    name: str

    def render(
        self,
        cast_path: Path,
        output_path: Path,
        fps: int,
    ) -> None:
        ...


class AgentRunner(Protocol):
    def run(self, recipe: Recipe, prompt: str, run_dir: Path) -> AgentOutcome:
        ...


class SessionBackend(Protocol):
    def create_session(
        self,
        argv: list[str],
        cast_path: Path,
        cwd: str | None,
        env: dict[str, str],
        cols: int,
        rows: int,
    ) -> TerminalSession:
        ...


__all__ = [
    "AgentRunner",
    "AssertionType",
    "EvidenceConfig",
    "ExecutionMode",
    "PngRenderConfig",
    "Reporter",
    "ScreenRenderer",
    "SessionBackend",
    "StepAction",
    "SvgRenderConfig",
    "VideoBackend",
    "VideoConfig",
]
