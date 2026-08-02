"""Community-health / GitHub-template contract tests.

These tests pin the review findings from the community-health remediation
(md-mt/termproof#84 review, replacement PR): the bug-report recipe must be a
valid TermProof recipe (``command.argv`` object, not a command array), the
issue-template ``config.yml`` must satisfy GitHub's issue-config schema
(contact links HTTP(S) only), and every YAML/template we ship must parse.

Run: uv run python -m unittest tests.test_community_health -v
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import unittest
from pathlib import Path

import jsonschema
import yaml

from termproof.config import VerifierConfig
from termproof.recipe_schema import has_errors, validate_recipe_mapping

ROOT = Path(__file__).resolve().parent.parent
ISSUE_TEMPLATE_DIR = ROOT / ".github" / "ISSUE_TEMPLATE"
GITHUB_YAML_FILES = sorted((ROOT / ".github").rglob("*.yml")) + sorted(
    (ROOT / ".github").rglob("*.yaml")
)

# GitHub issue-template chooser schema (SchemaStore github-issue-config.json):
# contact link URLs must be HTTP(S) only.
CONTACT_URL_RE = re.compile(r"^https?://")


def _extract_json_block(path: Path) -> dict:
    """Extract the first ```json ... ``` block from a markdown template."""
    text = path.read_text(encoding="utf-8")
    match = re.search(r"```json\n(.*?)```", text, re.DOTALL)
    if match is None:
        raise AssertionError(f"no ```json block found in {path.name}")
    return json.loads(match.group(1))


def _load_yaml(path: Path) -> dict:
    with path.open(encoding="utf-8") as handle:
        return yaml.safe_load(handle)


def _extract_frontmatter(path: Path) -> dict:
    """Parse YAML frontmatter delimited by --- lines at the top of a file."""
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise AssertionError(f"no frontmatter in {path.name}")
    end = text.index("\n---", 4)
    return yaml.safe_load(text[4:end])


class BugReportRecipeTest(unittest.TestCase):
    """The bug-report template's sample recipe must be a valid TermProof recipe."""

    def setUp(self) -> None:
        self.recipe = _extract_json_block(ISSUE_TEMPLATE_DIR / "bug_report.md")

    def test_recipe_uses_command_argv_object_not_array(self) -> None:
        command = self.recipe.get("command")
        self.assertIsInstance(command, dict, "command must be an object")
        self.assertIsInstance(
            command.get("argv"), list, "command.argv must be a list"
        )
        self.assertTrue(command.get("argv"), "command.argv must be non-empty")

    def test_recipe_includes_recipe_version_one(self) -> None:
        self.assertEqual(1, self.recipe.get("recipe_version"))

    def test_recipe_validates_through_actual_loader(self) -> None:
        issues = validate_recipe_mapping(self.recipe, VerifierConfig.builtin())
        self.assertEqual([], issues, f"recipe should validate clean, got: {issues}")


class IssueTemplateConfigTest(unittest.TestCase):
    """config.yml must satisfy GitHub's issue-config schema."""

    def setUp(self) -> None:
        self.config = _load_yaml(ISSUE_TEMPLATE_DIR / "config.yml")

    def test_blank_issues_flag_is_boolean(self) -> None:
        self.assertIsInstance(self.config.get("blank_issues_enabled"), bool)

    def test_contact_links_are_http_or_https(self) -> None:
        links = self.config.get("contact_links")
        self.assertIsInstance(links, list)
        self.assertGreaterEqual(len(links), 1)
        for link in links:
            with self.subTest(link=link.get("name")):
                self.assertIn("name", link)
                self.assertIn("about", link)
                url = link.get("url")
                self.assertIsInstance(url, str)
                self.assertRegex(
                    url,
                    CONTACT_URL_RE,
                    f"contact link URL must be HTTP(S), got {url!r}",
                )

    def test_no_mailto_contact_links(self) -> None:
        for link in self.config.get("contact_links", []):
            self.assertNotIn("mailto:", link.get("url", ""))


class TemplateFrontmatterTest(unittest.TestCase):
    def test_bug_report_frontmatter(self) -> None:
        fm = _extract_frontmatter(ISSUE_TEMPLATE_DIR / "bug_report.md")
        self.assertEqual("Bug report", fm.get("name"))
        self.assertIsInstance(fm.get("about"), str)
        self.assertIn("bug", fm.get("labels", []))

    def test_feature_request_frontmatter(self) -> None:
        fm = _extract_frontmatter(ISSUE_TEMPLATE_DIR / "feature_request.md")
        self.assertEqual("Feature request", fm.get("name"))
        self.assertIsInstance(fm.get("about"), str)
        self.assertIn("enhancement", fm.get("labels", []))


class GitHubYamlParseTest(unittest.TestCase):
    def test_every_github_yaml_file_parses_to_mapping(self) -> None:
        self.assertTrue(GITHUB_YAML_FILES, "expected .github YAML files")
        for path in GITHUB_YAML_FILES:
            with self.subTest(file=str(path.relative_to(ROOT))):
                data = _load_yaml(path)  # raises on syntax error
                self.assertIsInstance(
                    data,
                    dict,
                    f"{path.name} must be a mapping (got {type(data).__name__}); "
                    "comments-only YAML parses to None and is not a valid config",
                )


class FundingConfigTest(unittest.TestCase):
    """FUNDING.yml must be a valid GitHub funding mapping (SchemaStore)."""

    FUNDING_YML = ROOT / ".github" / "FUNDING.yml"
    FUNDING_SCHEMA = ROOT / "scripts" / "schemas" / "github-funding.json"

    def setUp(self) -> None:
        self.funding = _load_yaml(self.FUNDING_YML)

    def test_funding_yml_is_a_mapping(self) -> None:
        self.assertIsInstance(
            self.funding,
            dict,
            "FUNDING.yml must be a mapping ({} while no sponsor is configured), "
            "not comments-only (which parses to None and fails the Funding schema)",
        )

    def test_funding_yml_validates_against_funding_schema(self) -> None:
        schema_path = self.FUNDING_SCHEMA
        self.assertTrue(
            schema_path.is_file(),
            f"funding schema must be vendored in-repo at {schema_path}",
        )
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        jsonschema.validate(instance=self.funding, schema=schema)


class ValidationHarnessTest(unittest.TestCase):
    """scripts/validate_community_health.py must be hermetic and fail cleanly."""

    SCRIPT = ROOT / "scripts" / "validate_community_health.py"

    def _run(self, *args: str) -> subprocess.CompletedProcess[str]:
        env = dict(os.environ)
        # No pre-seeded /tmp schema and no schema-related env leakage: the
        # harness must work on a fresh checkout with nothing but the repo.
        env.pop("TERMPROOF_ISSUE_CONFIG_SCHEMA", None)
        env.pop("TERMPROOF_FUNDING_SCHEMA", None)
        return subprocess.run(
            [sys.executable, str(self.SCRIPT), *args],
            capture_output=True,
            text=True,
            cwd=ROOT,
            env=env,
            timeout=180,
        )

    def test_harness_does_not_hardcode_tmp_schema(self) -> None:
        source = self.SCRIPT.read_text(encoding="utf-8")
        self.assertNotIn(
            "/tmp/",
            source,
            "harness must use an in-repo vendored schema, not a /tmp path",
        )

    def test_harness_passes_hermetically_on_fresh_checkout(self) -> None:
        proc = self._run()
        self.assertEqual(
            proc.returncode,
            0,
            f"harness should pass with only vendored schemas:\n{proc.stdout}\n{proc.stderr}",
        )
        self.assertIn("ALL VALIDATION CHECKS PASSED", proc.stdout)

    def test_harness_missing_schema_is_clean_failure(self) -> None:
        proc = self._run("--issue-config-schema", "/nonexistent/schema.json")
        self.assertNotEqual(proc.returncode, 0, "missing schema must fail validation")
        self.assertNotIn(
            "Traceback", proc.stderr, "missing schema must be a clean failure, not a traceback"
        )
        self.assertIn("FAIL", proc.stdout)


class SupportRoutingTest(unittest.TestCase):
    """SUPPORT.md and config.yml must not route users to disabled Discussions."""

    def test_support_md_has_no_discussions_link(self) -> None:
        support = (ROOT / "SUPPORT.md").read_text(encoding="utf-8")
        self.assertNotIn("discussions", support.lower())

    def test_config_yml_has_no_discussions_link(self) -> None:
        config = _load_yaml(ISSUE_TEMPLATE_DIR / "config.yml")
        for link in config.get("contact_links", []):
            self.assertNotIn("discussions", link.get("url", "").lower())


class SecurityPolicyTest(unittest.TestCase):
    def test_security_supported_versions_table_has_0_2(self) -> None:
        security = (ROOT / "SECURITY.md").read_text(encoding="utf-8")
        self.assertIn("0.2.x", security)
        self.assertIn(":white_check_mark:", security)


if __name__ == "__main__":
    unittest.main()
