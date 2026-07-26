from __future__ import annotations

import html
import xml.etree.ElementTree as ET
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
    """Markdown report generator."""

    name = "markdown"

    def generate(
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


class JUnitXmlReporter:
    """JUnit XML reporter consumable by Jenkins, GitLab CI, CircleCI, etc.

    Output follows the classic JUnit XML schema:
    <testsuites><testsuite><testcase>[<failure>][<system-out>]</testsuite></testsuites>

    Each RunResult maps to one <testcase>. Failures include step + assertion
    detail. Artifacts are included in system-out for CI visibility.
    """

    name = "junit_xml"

    def generate(
        self,
        results: list[RunResult],
        build_info: BuildInfo | None = None,
        before_after: BeforeAfterResult | None = None,
    ) -> str:
        total = len(results)
        failures = sum(0 if r.passed else 1 for r in results)
        total_time = sum(r.duration_seconds for r in results)

        testsuites = ET.Element("testsuites")
        testsuites.set("name", "termproof")
        testsuites.set("tests", str(total))
        testsuites.set("failures", str(failures))
        testsuites.set("errors", "0")
        testsuites.set("time", f"{total_time:.3f}")

        suite_name = "termproof"
        if build_info is not None and hasattr(build_info, "mode"):
            suite_name = f"termproof-{build_info.mode}"

        testsuite = ET.SubElement(testsuites, "testsuite")
        testsuite.set("name", suite_name)
        testsuite.set("tests", str(total))
        testsuite.set("failures", str(failures))
        testsuite.set("errors", "0")
        testsuite.set("skipped", "0")
        testsuite.set("time", f"{total_time:.3f}")

        if build_info is not None:
            props = ET.SubElement(testsuite, "properties")
            for key, attr in [
                ("mode", "mode"),
                ("command", "command"),
                ("version", "version"),
                ("git_commit", "git_commit"),
            ]:
                val = getattr(build_info, attr, "")
                if isinstance(val, list):
                    val = " ".join(str(x) for x in val)
                prop = ET.SubElement(props, "property")
                prop.set("name", key)
                prop.set("value", str(val))

        for result in results:
            testcase = ET.SubElement(testsuite, "testcase")
            classname = result.execution or "termproof"
            tc_name = (
                f"{result.recipe_name} [{result.renderer}]"
                if result.renderer != "default"
                else result.recipe_name
            )
            testcase.set("classname", classname)
            testcase.set("name", tc_name)
            testcase.set("time", f"{result.duration_seconds:.3f}")

            if not result.passed:
                failure = ET.SubElement(testcase, "failure")
                failure.set("message", f"{result.recipe_name} failed (score {result.score:.2f})")
                failure.set("type", "AssertionError")
                lines = [
                    f"Recipe: {result.recipe_name}",
                    f"Renderer: {result.renderer}",
                    f"Priority: {result.priority}",
                    f"Execution: {result.execution}",
                    f"Score: {result.score:.2f}",
                    f"Exit code: {result.exit_code}",
                    "",
                    "Steps:",
                ]
                for st in result.steps:
                    mark = "PASS" if st.passed else "FAIL"
                    lines.append(f"  {mark} {st.name}: {st.detail}")
                lines.extend(["", "Assertions:"])
                for a in result.assertions:
                    mark = "PASS" if a.passed else "FAIL"
                    lines.append(f"  {mark} {a.name}: {a.detail}")
                if result.artifacts:
                    lines.extend(["", "Artifacts:"])
                    for k, v in result.artifacts.items():
                        lines.append(f"  {k}: {v}")
                failure.text = "\n".join(lines)

            sysout = ET.SubElement(testcase, "system-out")
            out_lines: list[str] = []
            # include step/assertion summary even for passing cases for visibility
            if result.steps:
                out_lines.append("Steps:")
                for st in result.steps:
                    mark = "PASS" if st.passed else "FAIL"
                    out_lines.append(f"  {mark} {st.name}: {st.detail}")
                out_lines.append("")
            if result.artifacts:
                out_lines.append("Artifacts:")
                for k, v in result.artifacts.items():
                    out_lines.append(f"  {k}: {v}")
            sysout.text = "\n".join(out_lines) if out_lines else ""

        xml_body = ET.tostring(testsuites, encoding="unicode")
        return f'<?xml version="1.0" encoding="UTF-8"?>\n{xml_body}\n'


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
