from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = ROOT / "templates" / "gitlab" / ".gitlab-ci.yml"
DOCS = ROOT / "docs" / "ci" / "gitlab.md"


class GitLabCiTemplateTest(unittest.TestCase):
    def test_template_runs_termproof_and_uploads_evidence(self) -> None:
        text = TEMPLATE.read_text(encoding="utf-8")

        self.assertIn("uvx --from git+https://github.com/md-mt/termproof.git termproof run", text)
        self.assertIn('"$TERMPROOF_RECIPES"', text)
        self.assertIn("--out .termproof/runs $TERMPROOF_ARGS", text)
        self.assertIn("--xml-path .termproof/runs/latest-report.xml", text)
        self.assertIn("cargo install --locked --git https://github.com/asciinema/agg", text)
        self.assertIn("when: always", text)
        self.assertIn("- .termproof/runs", text)

    def test_template_can_comment_on_merge_requests(self) -> None:
        text = TEMPLATE.read_text(encoding="utf-8")

        self.assertIn("termproof:mr-comment", text)
        self.assertIn("$CI_MERGE_REQUEST_IID", text)
        self.assertIn("GITLAB_TOKEN", text)
        self.assertIn("merge_requests/$CI_MERGE_REQUEST_IID/notes", text)
        self.assertIn("latest-report.md", text)

    def test_docs_link_template(self) -> None:
        text = DOCS.read_text(encoding="utf-8")

        self.assertIn("templates/gitlab/.gitlab-ci.yml", text)
        self.assertIn("TERMPROOF_RECIPES", text)
        self.assertIn("artifacts.reports.junit", text)


if __name__ == "__main__":
    unittest.main()
