from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs" / "releases.md"


class ReleaseDocsTest(unittest.TestCase):
    def test_pypi_trusted_publisher_values_are_documented(self) -> None:
        text = DOCS.read_text(encoding="utf-8")

        self.assertIn("Owner: `md-mt`", text)
        self.assertIn("Repository: `termproof`", text)
        self.assertIn("Workflow: `release.yml`", text)
        self.assertIn("Environment: `pypi`", text)
        self.assertIn("invalid-publisher", text)


if __name__ == "__main__":
    unittest.main()
