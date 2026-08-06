from __future__ import annotations

import re
import xml.etree.ElementTree as ET

from .before_after import BeforeAfterResult
from .build_info import BuildInfo
from .models import RunResult
from .protocols import Reporter as Reporter
from .report_helpers import _build_info_lines, _detail, _evidence_links

# XML 1.0 spec: allowed characters are:
#   #x9 | #xA | #xD | [#x20-#xD7FF] | [#xE000-#xFFFD] | [#x10000-#x10FFFF]
# All other control characters (#x00-#x08, #x0B-#x0C, #x0E-#x1F) are FORBIDDEN.
# Additionally, the following are FORBIDDEN by the XML 1.0 spec:
#   - Surrogates: #xD800-#xDFFF
#   - Noncharacters: #xFDD0-#xFDEF, #xFFFE-#xFFFF (and on every plane)
_XML_FORBIDDEN_RE = re.compile(
    "["
    "\x00-\x08"          # control chars (excl. tab, lf, cr)
    "\x0b\x0c"            # vertical tab, form feed
    "\x0e-\x1f"           # other control chars
    "\ud800-\udfff"       # surrogates
    "\ufdd0-\ufdef"       # noncharacters
    "\ufffe\uffff"        # noncharacters
    "\U0001fffe\U0001ffff" # plane 1 noncharacters (handled by regex engine)
    "]"
)


def _xml_sanitize(text: str) -> str:
    """Strip XML 1.0 forbidden characters from *text*.

    Terminal output routinely contains ANSI escape sequences
    (``\\x1b[...``) and other byte-range control codes that would
    produce invalid XML.  The standard ``ET.tostring``
    escaping does not handle these — they must be removed pre-serialisation.

    Also strips XML 1.0 noncharacters (#xFDD0-#xFDEF, #xFFFE-#xFFFF)
    and surrogates (#xD800-#xDFFF) which are invalid in XML 1.0.
    """
    return _XML_FORBIDDEN_RE.sub("", text)


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
        testsuites.set("name", _xml_sanitize("termproof"))
        testsuites.set("tests", str(total))
        testsuites.set("failures", str(failures))
        testsuites.set("errors", "0")
        testsuites.set("time", f"{total_time:.3f}")
        # Aggregate attributes for CI consumers
        import datetime
        import socket
        testsuites.set("timestamp", datetime.datetime.now(datetime.UTC).isoformat())
        try:
            testsuites.set("hostname", socket.gethostname())
        except Exception:
            testsuites.set("hostname", "unknown")

        suite_name = "termproof"
        if build_info is not None and hasattr(build_info, "mode"):
            suite_name = f"termproof-{_xml_sanitize(build_info.mode)}"

        testsuite = ET.SubElement(testsuites, "testsuite")
        testsuite.set("name", _xml_sanitize(suite_name))
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
                prop.set("name", _xml_sanitize(key))
                prop.set("value", _xml_sanitize(str(val)))

        for result in results:
            testcase = ET.SubElement(testsuite, "testcase")
            classname = _xml_sanitize(result.execution or "termproof")
            tc_name = (
                f"{_xml_sanitize(result.recipe_name)} [{_xml_sanitize(result.renderer)}]"
                if result.renderer != "default"
                else _xml_sanitize(result.recipe_name)
            )
            testcase.set("classname", classname)
            testcase.set("name", tc_name)
            testcase.set("time", f"{result.duration_seconds:.3f}")

            if not result.passed:
                failure = ET.SubElement(testcase, "failure")
                failure.set("message", _xml_sanitize(f"{result.recipe_name} failed (score {result.score:.2f})"))
                failure.set("type", "AssertionError")
                lines = [
                    f"Recipe: {_xml_sanitize(result.recipe_name)}",
                    f"Renderer: {_xml_sanitize(result.renderer)}",
                    f"Priority: {_xml_sanitize(result.priority)}",
                    f"Execution: {_xml_sanitize(result.execution)}",
                    f"Score: {result.score:.2f}",
                    f"Exit code: {result.exit_code}",
                    "",
                    "Steps:",
                ]
                for st in result.steps:
                    mark = "PASS" if st.passed else "FAIL"
                    lines.append(f"  {mark} {_xml_sanitize(st.name)}: {_xml_sanitize(st.detail)}")
                lines.extend(["", "Assertions:"])
                for a in result.assertions:
                    mark = "PASS" if a.passed else "FAIL"
                    lines.append(f"  {mark} {_xml_sanitize(a.name)}: {_xml_sanitize(a.detail)}")
                if result.artifacts:
                    lines.extend(["", "Artifacts:"])
                    for k, v in result.artifacts.items():
                        lines.append(f"  {_xml_sanitize(k)}: {_xml_sanitize(v)}")
                failure.text = "\n".join(lines)

            sysout = ET.SubElement(testcase, "system-out")
            out_lines: list[str] = []
            # Include step AND assertion summary even for passing cases for CI visibility
            if result.steps:
                out_lines.append("Steps:")
                for st in result.steps:
                    mark = "PASS" if st.passed else "FAIL"
                    out_lines.append(f"  {mark} {_xml_sanitize(st.name)}: {_xml_sanitize(st.detail)}")
            if result.assertions:
                if out_lines:
                    out_lines.append("")
                out_lines.append("Assertions:")
                for a in result.assertions:
                    mark = "PASS" if a.passed else "FAIL"
                    out_lines.append(f"  {mark} {_xml_sanitize(a.name)}: {_xml_sanitize(a.detail)}")
            if result.artifacts:
                if out_lines:
                    out_lines.append("")
                out_lines.append("Artifacts:")
                for k, v in result.artifacts.items():
                    out_lines.append(f"  {_xml_sanitize(k)}: {_xml_sanitize(v)}")
            sysout.text = "\n".join(out_lines) if out_lines else ""

        xml_body = ET.tostring(testsuites, encoding="unicode")
        return f'<?xml version="1.0" encoding="UTF-8"?>\n{xml_body}\n'
