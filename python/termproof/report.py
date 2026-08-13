from __future__ import annotations

from .before_after import BeforeAfterResult
from .build_info import BuildInfo
from .models import RunResult
from .report_helpers import _build_info_lines, _detail, _evidence_links


class ReportGenerator:
    def generate_markdown(
        self,
        results: list[RunResult],
        build_info: BuildInfo | None = None,
        before_after: BeforeAfterResult | None = None,
    ) -> str:
        passed = sum(1 for result in results if result.passed)
        lines = [
            f"# TUI Verification - {passed}/{len(results)} Passed",
            "",
        ]
        if build_info is not None:
            lines.extend(_build_info_lines(build_info))
        if before_after is not None:
            lines.extend(["", before_after.to_markdown().rstrip(), ""])
        lines.extend(
            [
                "| Recipe | Renderer | Priority | Execution | Result | Score | Evidence |",
                "| --- | --- | --- | --- | --- | --- | --- |",
            ]
        )
        for result in results:
            status = "PASS" if result.passed else "FAIL"
            evidence = _evidence_links(result)
            lines.append(
                f"| `{result.recipe_name}` | `{result.renderer}` | `{result.priority}` | "
                f"`{result.execution}` | {status} | {result.score:.2f} | {evidence} |"
            )
        for result in results:
            lines.extend(["", _detail(result).rstrip()])
        return "\n".join(lines) + "\n"
