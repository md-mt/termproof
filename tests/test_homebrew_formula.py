from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FORMULA = ROOT / "Formula" / "termproof.rb"
DOCS = ROOT / "docs" / "install" / "homebrew.md"
README = ROOT / "README.md"


class HomebrewFormulaTest(unittest.TestCase):
    def test_formula_installs_termproof_release(self) -> None:
        text = FORMULA.read_text(encoding="utf-8")

        self.assertIn("class Termproof < Formula", text)
        self.assertIn("url \"https://github.com/md-mt/termproof/releases/download/v0.2.0/termproof-0.2.0.tar.gz\"", text)
        self.assertIn("sha256 \"a7f5fad67e4f3af885981f0ed8ef15c8ab30b2e3e97d0f257c7ce2b4dd9092fe\"", text)
        self.assertIn("depends_on \"agg\"", text)
        self.assertIn("depends_on \"ffmpeg\"", text)
        self.assertIn("depends_on \"python@3.13\"", text)
        self.assertIn("virtualenv_install_with_resources", text)
        self.assertEqual(13, text.count("resource \""))

    def test_formula_smoke_test_exercises_cli(self) -> None:
        text = FORMULA.read_text(encoding="utf-8")

        self.assertIn("shell_output(\"#{bin}/termproof --help\")", text)
        self.assertIn("\"init\", testpath/\"recipes\"", text)
        self.assertIn("homebrew-smoke.recipe.json", text)

    def test_docs_show_tap_install_path(self) -> None:
        docs = DOCS.read_text(encoding="utf-8")
        readme = README.read_text(encoding="utf-8")

        for text in (docs, readme):
            self.assertIn("brew tap md-mt/termproof https://github.com/md-mt/termproof", text)
            self.assertIn("brew install termproof", text)


if __name__ == "__main__":
    unittest.main()
