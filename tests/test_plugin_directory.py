from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs" / "plugins.md"
DOCS_SITE = ROOT / "docs-site" / "plugins.md"


class PluginDirectoryTest(unittest.TestCase):
    def test_first_party_plugin_repos_are_listed(self) -> None:
        docs = DOCS.read_text(encoding="utf-8")
        docs_site = DOCS_SITE.read_text(encoding="utf-8")

        for repo in (
            "termproof-slack-reporter",
            "termproof-docker-backend",
            "termproof-png-renderer",
        ):
            url = f"https://github.com/md-mt/{repo}"
            self.assertIn(url, docs)
            self.assertIn(url, docs_site)

    def test_directory_uses_git_installs_until_pypi_release(self) -> None:
        docs = DOCS.read_text(encoding="utf-8")

        self.assertIn("pip install git+https://github.com/md-mt/termproof-slack-reporter.git", docs)
        self.assertIn("pip install git+https://github.com/md-mt/termproof-docker-backend.git", docs)
        self.assertIn("pip install git+https://github.com/md-mt/termproof-png-renderer.git", docs)


if __name__ == "__main__":
    unittest.main()
