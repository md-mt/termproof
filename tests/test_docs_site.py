from __future__ import annotations

import json
import unittest
from pathlib import Path

import yaml


ROOT = Path(__file__).resolve().parents[1]
DOCS_SITE = ROOT / "docs-site"
CONFIG = DOCS_SITE / ".vitepress" / "config.mts"
WORKFLOW = ROOT / ".github" / "workflows" / "docs-site.yml"


class DocsSiteTest(unittest.TestCase):
    def test_vitepress_package_and_sections_exist(self) -> None:
        package = json.loads((DOCS_SITE / "package.json").read_text(encoding="utf-8"))

        self.assertEqual("vitepress build .", package["scripts"]["docs:build"])
        for path in (
            "getting-started.md",
            "install/homebrew.md",
            "guides/index.md",
            "api/index.md",
            "plugins.md",
            "ci/index.md",
            "faq.md",
        ):
            self.assertTrue((DOCS_SITE / path).is_file(), path)

    def test_vitepress_nav_has_expected_structure(self) -> None:
        text = CONFIG.read_text(encoding="utf-8")

        self.assertIn("Getting Started", text)
        self.assertIn("Homebrew", text)
        self.assertIn("Guides", text)
        self.assertIn("API Reference", text)
        self.assertIn("Plugins", text)
        self.assertIn("CI Integration", text)
        self.assertIn("FAQ", text)

    def test_docs_site_workflow_builds_artifact(self) -> None:
        workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
        text = WORKFLOW.read_text(encoding="utf-8")

        self.assertIn("pull_request", workflow[True])
        self.assertIn("npm run --prefix docs-site docs:build", text)
        self.assertIn("docs-site/.vitepress/dist", text)


class DocsSiteDeployTest(unittest.TestCase):
    """Acceptance tests for the VitePress Pages deployment remediation (PR #91
    replacement). Each test corresponds to a review finding from the formal
    mw-ding CHANGES_REQUESTED review or the md-mt blocking comment."""

    @staticmethod
    def _workflow() -> dict:
        return yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))

    def test_vitepress_base_path_for_github_pages(self) -> None:
        text = CONFIG.read_text(encoding="utf-8")
        self.assertIn('base: "/termproof/"', text)

    def test_docs_site_lockfile_committed(self) -> None:
        lockfile = DOCS_SITE / "package-lock.json"
        self.assertTrue(lockfile.is_file(), "docs-site/package-lock.json must be committed")
        lock = json.loads(lockfile.read_text(encoding="utf-8"))
        self.assertEqual(lock["name"], "docs-site")
        self.assertIn("vitepress", lock.get("packages", {}).get("", {}).get("devDependencies", {}))

    def test_docs_site_workflow_uses_npm_ci(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("npm ci --prefix docs-site", text)
        self.assertNotIn("npm install --prefix docs-site --no-package-lock", text)

    def test_docs_site_workflow_pins_pages_actions(self) -> None:
        text = WORKFLOW.read_text(encoding="utf-8")
        self.assertIn("uses: actions/configure-pages@v5", text)
        self.assertIn("uses: actions/upload-pages-artifact@v3", text)
        self.assertIn("uses: actions/deploy-pages@v4", text)

    def test_docs_site_workflow_has_deploy_job(self) -> None:
        workflow = self._workflow()
        self.assertIn("deploy", workflow["jobs"])

    def test_docs_site_deploy_gated_on_enable_pages(self) -> None:
        workflow = self._workflow()
        deploy = workflow["jobs"]["deploy"]
        self.assertIn("vars.ENABLE_PAGES", deploy["if"])

    def test_docs_site_deploy_job_least_privilege(self) -> None:
        workflow = self._workflow()
        deploy = workflow["jobs"]["deploy"]
        self.assertEqual(
            {"contents": "read", "pages": "write", "id-token": "write"},
            deploy["permissions"],
            "deploy job must request only contents:read, pages:write, id-token:write",
        )
        self.assertEqual("github-pages", deploy["environment"]["name"])

    def test_docs_site_build_job_stays_pr_safe(self) -> None:
        workflow = self._workflow()
        build = workflow["jobs"]["build"]
        steps = build["steps"]
        upload = next(s for s in steps if "upload-pages-artifact" in s.get("uses", ""))
        self.assertEqual("github.event_name != 'pull_request'", upload["if"])

    def test_docs_site_workflow_yaml_parses(self) -> None:
        workflow = self._workflow()
        self.assertIn("build", workflow["jobs"])
        self.assertIn("pull_request", workflow[True])


if __name__ == "__main__":
    unittest.main()
