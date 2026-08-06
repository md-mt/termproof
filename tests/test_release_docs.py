from __future__ import annotations

import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs" / "releases.md"
WORKFLOW = ROOT / ".github" / "workflows" / "release.yml"


class ReleaseDocsTest(unittest.TestCase):
    def test_pypi_trusted_publisher_values_are_documented(self) -> None:
        text = DOCS.read_text(encoding="utf-8")

        self.assertIn("Owner: `md-mt`", text)
        self.assertIn("Repository: `termproof`", text)
        self.assertIn("Workflow: `release.yml`", text)
        self.assertIn("Environment: `pypi`", text)
        self.assertIn("ENABLE_PYPI", text)
        self.assertIn("invalid-publisher", text)

    def test_pypi_publish_is_opt_in(self) -> None:
        workflow = yaml.safe_load(WORKFLOW.read_text(encoding="utf-8"))
        steps = workflow["jobs"]["release"]["steps"]

        publish_step = next(step for step in steps if step["name"] == "Publish to PyPI")
        self.assertEqual(
            "startsWith(github.ref, 'refs/tags/v') && vars.ENABLE_PYPI == 'true'",
            publish_step["if"],
        )
        self.assertEqual("pypa/gh-action-pypi-publish@release/v1", publish_step["uses"])

        skip_step = next(step for step in steps if step["name"] == "Note skipped PyPI publish")
        self.assertEqual(
            "startsWith(github.ref, 'refs/tags/v') && vars.ENABLE_PYPI != 'true'",
            skip_step["if"],
        )
        self.assertIn("ENABLE_PYPI", skip_step["run"])


if __name__ == "__main__":
    unittest.main()
