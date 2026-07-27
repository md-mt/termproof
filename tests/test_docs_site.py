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


if __name__ == "__main__":
    unittest.main()
