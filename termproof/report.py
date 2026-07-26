from __future__ import annotations

from .before_after import BeforeAfterResult
from .build_info import BuildInfo
from .models import RunResult


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


def _build_info_lines(build_info: BuildInfo) -> list[str]:
    verified = "yes" if build_info.verify_provenance() else "no"
    return [
        "## Build Provenance",
        "",
        f"- Mode: `{build_info.mode}`",
        f"- Command: `{_one_line(' '.join(build_info.command))}`",
        f"- Binary: `{_one_line(str(build_info.binary_path))}`",
        f"- Version: `{_one_line(build_info.version)}`",
        f"- Git commit: `{_one_line(str(build_info.git_commit))}`",
        f"- Verified: `{verified}`",
        "",
    ]


def _evidence_links(result: RunResult) -> str:
    links: list[str] = []
    for key in ("screenshot", "video", "cast", "screen_text", "step_screenshots"):
        value = result.artifacts.get(key)
        if value:
            links.append(f"[{key}]({value})")
    return " / ".join(links) if links else "-"


def _detail(result: RunResult) -> str:
    status = "PASS" if result.passed else "FAIL"
    lines = [
        f"<details><summary>{status} {result.recipe_name} [{result.renderer}]</summary>",
        "",
        "### Assertions",
        "",
    ]
    for assertion in result.assertions:
        mark = "PASS" if assertion.passed else "FAIL"
        lines.append(f"- {mark} `{assertion.name}` - {assertion.detail}")
    lines.extend(["", "### Steps", ""])
    for step in result.steps:
        mark = "PASS" if step.passed else "FAIL"
        lines.append(f"- {mark} `{step.name}` - {step.detail}")
    lines.extend(["", "</details>"])
    return "\n".join(lines)


def _one_line(value: str) -> str:
    return " / ".join(part.strip() for part in value.splitlines() if part.strip())
