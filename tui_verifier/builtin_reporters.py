from __future__ import annotations

from typing import Protocol

from .before_after import BeforeAfterResult
from .build_info import BuildInfo
from .models import RunResult


class Reporter(Protocol):
    """Protocol for pluggable report generators."""

    name: str

    def generate(
        self,
        results: list[RunResult],
        build_info: BuildInfo | None = None,
        before_after: BeforeAfterResult | None = None,
    ) -> str:
        ...


class MarkdownReporter:
    """Markdown report (current behavior)."""

    name = "markdown"

    def generate(
        self,
        results: list[RunResult],
        build_info: BuildInfo | None = None,
        before_after: BeforeAfterResult | None = None,
    ) -> str:
        from .report import ReportGenerator

        return ReportGenerator().generate_markdown(results, build_info, before_after)
