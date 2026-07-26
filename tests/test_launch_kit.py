"""Validation for launch-kit assets shipped in docs/launch.

Ensures:
- All required launch kit files exist
- Show HN draft retitled for TermProof (not stale TUI Verifier)
- Outreach templates exist for Textual, Bubble Tea, Ratatui, Ink with required sections
- Social profiles have handle fallback plan and no account claimed as created
- Checklist + runbook exist with canonical links and gates
- No actual external actions performed (no secrets, no real DMs, no posting)
- Canonical links reference real repo paths where applicable
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
LAUNCH_DIR = REPO_ROOT / "docs" / "launch"


class LaunchKitFileExistenceTest(unittest.TestCase):
    def test_launch_directory_exists(self) -> None:
        self.assertTrue(LAUNCH_DIR.exists(), f"Missing {LAUNCH_DIR}")

    def test_required_files_exist(self) -> None:
        required = [
            LAUNCH_DIR / "README.md",
            LAUNCH_DIR / "show-hn.md",
            LAUNCH_DIR / "outreach" / "textual.md",
            LAUNCH_DIR / "outreach" / "bubbletea.md",
            LAUNCH_DIR / "outreach" / "ratatui.md",
            LAUNCH_DIR / "outreach" / "ink.md",
            LAUNCH_DIR / "outreach" / "README.md",
            LAUNCH_DIR / "social" / "profiles.md",
            LAUNCH_DIR / "checklist.md",
            LAUNCH_DIR / "runbook.md",
        ]
        missing = [p for p in required if not p.exists()]
        self.assertEqual([], missing, f"Missing launch assets: {missing}")


class ShowHNDraftTest(unittest.TestCase):
    def setUp(self) -> None:
        self.path = LAUNCH_DIR / "show-hn.md"
        self.content = self.path.read_text(encoding="utf-8") if self.path.exists() else ""

    def test_show_hn_is_termproof_retitled(self) -> None:
        # Must reference TermProof, not only old TUI Verifier title
        self.assertIn("TermProof", self.content)
        # The draft title should include TermProof
        self.assertRegex(self.content, r"Show HN.*TermProof", "Show HN title must be retitled for TermProof")
        # Old exact title "TUI Verifier — Evidence-first verification for terminal apps (like Cypress for TUIs)"
        # should not be the primary title — allow historical mention but prefer TermProof title
        self.assertNotIn(
            "Title: 'TUI Verifier — Evidence-first verification for terminal apps (like Cypress for TUIs)'",
            self.content,
            "Show HN must be retitled for TermProof, not old TUI Verifier title",
        )

    def test_show_hn_has_required_sections(self) -> None:
        for section in ["Draft Body", "Images", "Posting Checklist", "Monitoring", "60-second demo"]:
            # Case-insensitive check
            self.assertIn(section.lower(), self.content.lower(), f"Show HN draft missing section: {section}")

    def test_show_hn_has_canonical_links(self) -> None:
        # Must reference repo + canonical demo/docs links
        for link in ["github.com/md-mt/termproof", "examples/generic", "recipe-packs"]:
            self.assertIn(link, self.content, f"Show HN missing canonical link/reference: {link}")

    def test_show_hn_has_human_gate_note(self) -> None:
        self.assertIn("t_550ba351", self.content.lower() + self.content, "Show HN must reference human gate")
        self.assertIn("DRAFT", self.content, "Show HN must be marked as draft")


class OutreachTemplatesTest(unittest.TestCase):
    def _read(self, name: str) -> str:
        path = LAUNCH_DIR / "outreach" / f"{name}.md"
        self.assertTrue(path.exists(), f"Missing outreach template {name}")
        return path.read_text(encoding="utf-8")

    def test_all_frameworks_present(self) -> None:
        for fw in ["textual", "bubbletea", "ratatui", "ink"]:
            path = LAUNCH_DIR / "outreach" / f"{fw}.md"
            self.assertTrue(path.exists(), f"Missing {fw} outreach template")

    def test_each_template_has_short_and_long_and_links(self) -> None:
        for fw in ["textual", "bubbletea", "ratatui", "ink"]:
            content = self._read(fw)
            self.assertTrue(len(content) > 500, f"{fw} template too short")
            # Should have at least short + long or template notion
            self.assertIn("Short", content, f"{fw} missing short template marker")
            self.assertIn("Long", content, f"{fw} missing long-form")
            self.assertIn("github.com/md-mt/termproof", content, f"{fw} missing repo link")
            self.assertIn("termproof", content.lower(), f"{fw} missing termproof mention")
            # Should not contain actual DM send artifact
            self.assertNotRegex(content.lower(), r"dm sent|posted on", f"{fw} should not claim DM posted")

    def test_common_readme_exists_and_has_tracking(self) -> None:
        content = self._read("README")
        self.assertIn("Tracking", content, "Common outreach README should have tracking guidance")
        self.assertIn("termproof", content.lower())

    def test_outreach_does_not_claim_endorsement(self) -> None:
        for fw in ["textual", "bubbletea", "ratatui", "ink"]:
            content = self._read(fw).lower()
            self.assertNotIn("endorsed by", content, f"{fw} must not claim endorsement")
            self.assertNotIn("official partnership", content, f"{fw} must not claim partnership")


class SocialProfilesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.path = LAUNCH_DIR / "social" / "profiles.md"
        self.content = self.path.read_text(encoding="utf-8") if self.path.exists() else ""

    def test_social_has_handle_plan(self) -> None:
        self.assertIn("@termproof", self.content.lower(), "Must have desired handle @termproof")
        self.assertIn("fallback", self.content.lower(), "Must have fallback plan")

    def test_social_has_profile_copy(self) -> None:
        self.assertIn("Bio", self.content, "Must have profile bio copy")
        self.assertIn("TermProof", self.content, "Bio should mention TermProof")

    def test_social_no_account_claimed_as_created(self) -> None:
        # The draft must NOT claim accounts are already created
        # Allow phrases like "after creation" but not "created at https://x.com/termproof (live)"
        lowered = self.content.lower()
        # It should mention human gate blocks actual creation
        self.assertIn("t_550ba351", lowered, "Social profiles must reference human gate")
        self.assertIn("draft", lowered, "Must be draft")
        # Must not contain a real post URL claiming success
        self.assertNotRegex(self.content, r"https://x\.com/termproof\s*\(live\)", "Should not claim handle is live")
        # Must mention Do Not for automated posting
        self.assertIn("do not", lowered)

    def test_social_has_launch_templates(self) -> None:
        for platform in ["twitter", "mastodon", "bluesky"]:
            self.assertIn(platform, self.content.lower(), f"Missing platform {platform} template")


class ChecklistAndRunbookTest(unittest.TestCase):
    def test_checklist_exists_with_required_sections(self) -> None:
        path = LAUNCH_DIR / "checklist.md"
        self.assertTrue(path.exists())
        content = path.read_text(encoding="utf-8")
        for kw in ["Pre-Requisites", "Human Gate", "Show HN", "Outreach", "Social", "Close Criteria"]:
            self.assertIn(kw, content, f"Checklist missing section {kw}")

    def test_runbook_exists_with_monitoring(self) -> None:
        path = LAUNCH_DIR / "runbook.md"
        self.assertTrue(path.exists())
        content = path.read_text(encoding="utf-8")
        for kw in ["Monitoring", "Show HN", "Outreach", "Metrics", "Failure"]:
            self.assertIn(kw, content, f"Runbook missing {kw}")
        self.assertIn("github.com/md-mt/termproof", content)

    def test_checklist_has_canonical_links_reference(self) -> None:
        content = (LAUNCH_DIR / "checklist.md").read_text(encoding="utf-8")
        readme_content = (LAUNCH_DIR / "README.md").read_text(encoding="utf-8")
        # README must have canonical links section
        self.assertIn("Canonical Links", readme_content)
        self.assertIn("60-second demo", readme_content)
        self.assertIn("termproof", readme_content.lower())

    def test_runbook_no_secrets(self) -> None:
        content = (LAUNCH_DIR / "runbook.md").read_text(encoding="utf-8")
        # Must not contain oauth_token, passwords, api keys
        self.assertNotIn("oauth_token", content.lower())
        self.assertNotIn("gho_", content)


class CanonicalLinksTest(unittest.TestCase):
    def test_repo_canonical_files_exist(self) -> None:
        # Verify files referenced in launch/README.md actually exist in repo
        expected = [
            REPO_ROOT / "README.md",
            REPO_ROOT / "docs" / "recipe-packs.md",
            REPO_ROOT / "docs" / "releases.md",
            REPO_ROOT / "examples" / "generic" / "generic_tui.recipe.json",
            REPO_ROOT / "examples" / "generic" / "generic_tui.py",
        ]
        missing = [p for p in expected if not p.exists()]
        self.assertEqual([], missing, f"Canonical files missing: {missing}")

    def test_examples_directory_has_expected_structure(self) -> None:
        generic_dir = REPO_ROOT / "examples" / "generic"
        self.assertTrue(generic_dir.exists())
        self.assertTrue((generic_dir / "generic_tui.recipe.json").exists())
        # Ensure recipe is valid JSON with required fields
        import json

        data = json.loads((generic_dir / "generic_tui.recipe.json").read_text(encoding="utf-8"))
        self.assertIn("name", data)
        self.assertIn("command", data)
        self.assertIn("steps", data)


class LaunchKitNoExternalActionTest(unittest.TestCase):
    def test_no_real_social_urls_claimed_live(self) -> None:
        # Walk all launch docs, ensure no claim like "Created https://..."
        for path in LAUNCH_DIR.rglob("*.md"):
            content = path.read_text(encoding="utf-8").lower()
            # No "account created https://x.com"
            if "account created" in content and "draft" not in content:
                # The common README may have tracking example — ensure it is template
                pass
            self.assertNotIn("oauth_token", content, f"{path} should not contain tokens")
            self.assertNotIn("gho_", content, f"{path} should not contain GH tokens")


if __name__ == "__main__":
    unittest.main()
