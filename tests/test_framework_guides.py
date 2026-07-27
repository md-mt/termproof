from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


class FrameworkGuidesTest(unittest.TestCase):
    def test_framework_guides_cover_required_sections(self) -> None:
        for name in ("textual", "bubbletea", "ratatui"):
            with self.subTest(name=name):
                text = (ROOT / "docs" / "guides" / f"{name}.md").read_text(
                    encoding="utf-8"
                )
                for heading in (
                    "## Recipe Setup",
                    "## Common Patterns",
                    "## CI Configuration",
                    "## Example Repo",
                ):
                    self.assertIn(heading, text)
                self.assertIn("termproof run", text)


if __name__ == "__main__":
    unittest.main()
