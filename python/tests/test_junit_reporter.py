from __future__ import annotations

import unittest
import xml.etree.ElementTree as ET

from termproof.config import VerifierConfig
from termproof.models import AssertionResult, RunResult, StepResult


class JUnitXmlReporterTest(unittest.TestCase):
    def _make_results(self):
        passing = RunResult(
            recipe_name="demo_pass",
            passed=True,
            exit_code=0,
            duration_seconds=1.23,
            priority="P1",
            execution="scripted",
            renderer="default",
            score=1.0,
            steps=[StepResult("step1", True, "ok", "screen")],
            assertions=[AssertionResult("assert1", True, "contains x")],
            artifacts={"cast": "/tmp/cast", "screenshot": "/tmp/svg"},
        )
        failing = RunResult(
            recipe_name="demo_fail",
            passed=False,
            exit_code=1,
            duration_seconds=0.5,
            priority="P0",
            execution="scripted",
            renderer="default",
            score=0.5,
            steps=[StepResult("step1", False, "timed out waiting for 'missing'", "screen")],
            assertions=[AssertionResult("assert1", False, "missing value")],
            artifacts={},
        )
        return [passing, failing]

    def test_junit_reporter_registered_in_builtin(self):
        config = VerifierConfig.builtin()
        self.assertIn("junit_xml", config.reporters)

    def test_junit_xml_generates_valid_xml(self):
        from termproof.builtin_reporters import JUnitXmlReporter
        reporter = JUnitXmlReporter()
        results = self._make_results()
        xml_str = reporter.generate(results)
        # should be parseable
        root = ET.fromstring(xml_str)
        self.assertEqual("testsuites", root.tag)

    def test_junit_xml_contains_test_cases(self):
        from termproof.builtin_reporters import JUnitXmlReporter
        reporter = JUnitXmlReporter()
        results = self._make_results()
        xml_str = reporter.generate(results)
        root = ET.fromstring(xml_str)
        # find testsuite
        suites = list(root.findall("testsuite"))
        self.assertGreaterEqual(len(suites), 1)
        testcases = []
        for suite in suites:
            testcases.extend(suite.findall("testcase"))
        self.assertEqual(2, len(testcases))
        names = [tc.attrib.get("name") for tc in testcases]
        self.assertIn("demo_pass", " ".join(names) or "")
        self.assertIn("demo_fail", " ".join(names) or "")

    def test_junit_xml_failure_has_failure_element(self):
        from termproof.builtin_reporters import JUnitXmlReporter
        reporter = JUnitXmlReporter()
        results = self._make_results()
        xml_str = reporter.generate(results)
        root = ET.fromstring(xml_str)
        failing_cases = []
        for suite in root.findall("testsuite"):
            for tc in suite.findall("testcase"):
                if "demo_fail" in tc.attrib.get("name", ""):
                    failing_cases.append(tc)
        self.assertTrue(failing_cases)
        self.assertIsNotNone(failing_cases[0].find("failure"))

    def test_junit_xml_passing_has_no_failure(self):
        from termproof.builtin_reporters import JUnitXmlReporter
        reporter = JUnitXmlReporter()
        results = self._make_results()
        xml_str = reporter.generate(results)
        root = ET.fromstring(xml_str)
        for suite in root.findall("testsuite"):
            for tc in suite.findall("testcase"):
                if "demo_pass" in tc.attrib.get("name", ""):
                    self.assertIsNone(tc.find("failure"))

    def test_junit_xml_escapes_special_chars(self):
        from termproof.builtin_reporters import JUnitXmlReporter
        reporter = JUnitXmlReporter()
        result = RunResult(
            recipe_name="special<>&\"'",
            passed=False,
            exit_code=1,
            duration_seconds=0.1,
            priority="P0",
            execution="scripted",
            renderer="default",
            score=0.0,
            steps=[StepResult("s", False, "fail <with> & \"quotes\"", "screen")],
            assertions=[],
            artifacts={},
        )
        xml_str = reporter.generate([result])
        # should still be valid XML
        root = ET.fromstring(xml_str)
        self.assertIsNotNone(root)

    def test_junit_xml_sanitizes_control_characters(self):
        """XML 1.0-forbidden control chars (\\x00-\\x08, \\x0B-\\x0C, \\x0E-\\x1F)
        must be stripped so the output is valid XML."""
        from termproof.builtin_reporters import JUnitXmlReporter
        reporter = JUnitXmlReporter()
        # Include ANSI escape (\\x1b) and other control chars in detail text
        dirty_name = "test\x01ctrl\x02\x1b[32mname"
        dirty_detail = "output\x00null\x08bs\x0cff\x1b[0m"
        result = RunResult(
            recipe_name=dirty_name,
            passed=False,
            exit_code=1,
            duration_seconds=0.2,
            priority="P0",
            execution="scripted",
            renderer="default",
            score=0.0,
            steps=[StepResult("s", False, dirty_detail, "screen")],
            assertions=[AssertionResult("a", True, dirty_detail)],
            artifacts={},
        )
        xml_str = reporter.generate([result])
        # Must be parseable XML — if control chars leaked through, ET will raise
        root = ET.fromstring(xml_str)
        self.assertIsNotNone(root)
        # Check that forbidden chars are gone but safe content remains
        self.assertIn("name", xml_str)
        self.assertNotIn("\x01", xml_str)
        self.assertNotIn("\x1b", xml_str)
        self.assertNotIn("\x00", xml_str)

    def test_junit_xml_sanitize_allows_valid_whitespace(self):
        """Tab (\\t), newline (\\n), and carriage return (\\r) are valid XML
        and must NOT be stripped."""
        from termproof.builtin_reporters import JUnitXmlReporter
        reporter = JUnitXmlReporter()
        detail_with_tabs = "col1\tcol2\tcol3\nrow2\ta\tb\n"
        result = RunResult(
            recipe_name="tab_test",
            passed=True,
            exit_code=0,
            duration_seconds=0.1,
            priority="P0",
            execution="scripted",
            renderer="default",
            score=1.0,
            steps=[StepResult("s", True, detail_with_tabs, "screen")],
            assertions=[],
            artifacts={},
        )
        xml_str = reporter.generate([result])
        root = ET.fromstring(xml_str)
        self.assertIsNotNone(root)
        # Valid whitespace chars should be preserved
        self.assertIn("\t", xml_str)
        self.assertIn("\n", xml_str)

    def test_junit_xml_empty_results(self):
        from termproof.builtin_reporters import JUnitXmlReporter
        reporter = JUnitXmlReporter()
        xml_str = reporter.generate([])
        root = ET.fromstring(xml_str)
        self.assertEqual("testsuites", root.tag)


if __name__ == "__main__":
    unittest.main()
