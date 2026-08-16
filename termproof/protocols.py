from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

from .before_after import BeforeAfterResult
from .build_info import BuildInfo
from .config import EvidenceConfig, PngRenderConfig, SvgRenderConfig, VideoConfig
from .models import AssertionResult, PublishedArtifact, Recipe, RunResult, StepResult
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


class StepAwareAssertionType(Protocol):
    """An assertion that also sees the screen captured after each step.

    Implementations satisfy ``AssertionType`` as well: ``steps`` is keyword-only
    and defaults to ``None``, so a caller that predates it invokes them exactly
    as before. TermProof passes ``steps`` only to evaluators that declare the
    parameter, which is why an assertion written against ``AssertionType`` keeps
    working without source changes.

    ``steps`` is ``None`` when the execution mode did not supply per-step
    screens — an assertion that needs them should report that rather than
    assume an empty run.
    """

    name: str

    def evaluate(
        self,
        recipe: Recipe,
        assertion: dict[str, Any],
        screen: str,
        raw_output: str,
        exit_code: int | None,
        *,
        steps: list[StepResult] | None = None,
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


class ArtifactPublisher(Protocol):
    """Send a local evidence file somewhere durable and say where it landed.

    ``key`` is the destination-relative identifier the caller has chosen — the
    layout of the evidence, which is the caller's policy, not the store's. The
    publisher decides only how a key maps onto its own namespace and onto a
    public URL.

    Returning a :class:`PublishedArtifact` rather than a URL string is what
    makes the result usable downstream: reports reference evidence by local
    path, so rewriting those links needs source and URL together, and a
    publisher that could not place a file has to be able to say so without
    aborting the artifacts that did publish.
    """

    name: str

    def publish(self, source: Path, key: str) -> PublishedArtifact:
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
    "ArtifactPublisher",
    "AssertionType",
    "EvidenceConfig",
    "ExecutionMode",
    "PngRenderConfig",
    "PublishedArtifact",
    "Reporter",
    "ScreenRenderer",
    "SessionBackend",
    "StepAction",
    "StepAwareAssertionType",
    "SvgRenderConfig",
    "VideoBackend",
    "VideoConfig",
]
