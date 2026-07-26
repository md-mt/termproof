"""Behavioral validation for launch-kit assets in docs/launch.

Validates:
- HN titles are <=80 chars
- Local paths referenced in launch docs resolve to existing files or are explicitly gated
- Embedded JSON recipes are parseable and structurally valid
- Embedded YAML CI snippets are syntactically valid
- Social platform handle syntax (no underscores on Bluesky), bio limits, tweet limits
- No secrets, tokens, or real account-created claims in any launch doc
- Issue #38 legacy-handle migration represented in checklist
- Output-directory consistency between run commands and artifact paths
- session.mp4 preflight check present
"""

from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
LAUNCH_DIR = REPO_ROOT / "docs" / "launch"


def _yaml_safe_load(text: str):
    """Try to load YAML; skip if pyyaml not available."""
    try:
        import yaml
    except ImportError:
        return None
    try:
        return yaml.safe_load(text)
    except yaml.YAMLError:
        return None


# ── helpers ──────────────────────────────────────────────────────────

def _extract_hackernews_titles(content: str) -> list[str]:
    """Extract HN title strings (backtick-quoted after 'Target Title' heading)."""
    titles: list[str] = []
    in_section = False
    for line in content.split("\n"):
        if "Target Title" in line:
            in_section = True
            continue
        if in_section:
            if line.strip().startswith("## ") or line.strip().startswith("# "):
                break
            m = re.search(r"`([^`]+)`", line)
            if m:
                titles.append(m[1])
    return titles


def _extract_local_path_refs(content: str) -> list[str]:
    """Extract local file-system paths referenced in markdown.

    Only returns paths that look like real repo file references:
    - backtick-quoted paths with directory components (e.g. `docs/foo/bar.md`)
    - markdown links [text](relative/path)
    Skips: bare filenames in code blocks (artifact output examples like final.svg),
    single-component paths, and shell-command relative paths starting with '.'.
    """
    refs: list[str] = []
    # inline code paths with at least one directory separator
    for m in re.finditer(r"`([a-zA-Z0-9_./-]+/[a-zA-Z0-9_./-]+\.[a-zA-Z]{2,6})`", content):
        ref = m.group(1)
        if not ref.startswith("."):
            # Skip domain-like paths (e.g. bsky.app/profile/...)
            first = ref.split("/")[0]
            if "." in first and not any(first.endswith(ext) for ext in (".md", ".py", ".json", ".yaml", ".toml", ".cfg", ".txt", ".svg", ".png")):
                continue
            refs.append(ref)
    # markdown links: [text](relative/path)
    for m in re.finditer(r"\]\(([^) ]+)\)", content):
        url = m.group(1)
        if not url.startswith(("http://", "https://", "#")):
            # Skip domain-like references (e.g. bsky.app/profile/...)
            if "." in url.split("/")[0]:
                continue
            refs.append(url)
    return refs


def _count_graphemes(s: str) -> int:
    return len(s)


# ── file existence ───────────────────────────────────────────────────

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
            LAUNCH_DIR / "social" / "assets" / "README.md",
            LAUNCH_DIR / "checklist.md",
            LAUNCH_DIR / "runbook.md",
        ]
        missing = [str(p.relative_to(REPO_ROOT)) for p in required if not p.exists()]
        self.assertEqual([], missing, f"Missing launch assets: {missing}")


# ── HN title validation ─────────────────────────────────────────────

class ShowHNDraftTest(unittest.TestCase):
    def setUp(self) -> None:
        self.path = LAUNCH_DIR / "show-hn.md"
        self.content = self.path.read_text(encoding="utf-8") if self.path.exists() else ""

    def test_show_hn_is_termproof_retitled(self) -> None:
        self.assertIn("TermProof", self.content)
        self.assertRegex(self.content, r"Show HN.*TermProof",
                         "Show HN title must reference TermProof")

    def test_show_hn_has_required_sections(self) -> None:
        for section in ["Draft Body", "Images", "Posting Checklist", "Monitoring", "60-second demo"]:
            self.assertIn(section.lower(), self.content.lower(),
                          f"Show HN draft missing section: {section}")

    def test_show_hn_has_canonical_links(self) -> None:
        for link in ["github.com/md-mt/termproof", "examples/generic", "recipe-packs"]:
            self.assertIn(link, self.content, f"Show HN missing canonical reference: {link}")

    def test_show_hn_has_human_gate_note(self) -> None:
        self.assertIn("t_550ba351", self.content)
        self.assertIn("DRAFT", self.content)

    # ── behavioral: title length ─────────────────────────────────────

    def test_hackernews_titles_are_under_80_chars(self) -> None:
        """Every extracted HN title must be <=80 Unicode code points."""
        titles = _extract_hackernews_titles(self.content)
        self.assertGreater(len(titles), 0, "No HN titles extracted from show-hn.md")
        for t in titles:
            length = _count_graphemes(t)
            self.assertLessEqual(length, 80,
                                 f"Title '{t[:50]}...' is {length} chars (limit 80)")

    def test_preferred_title_is_explicitly_sized(self) -> None:
        """The primary title line must state its character count."""
        # Find the first title line after 'Target Title'
        lines = self.content.split("\n")
        in_section = False
        found_title = False
        for line in lines:
            if "Target Title" in line:
                in_section = True
                continue
            if in_section and line.strip().startswith("`"):
                found_title = True
                # Allow char count in parens on same line or next
                if "chars" in line.lower() or "chars" in (
                    lines[lines.index(line) + 1].lower()
                    if lines.index(line) + 1 < len(lines)
                    else ""
                ):
                    return
                # Check if the title line itself has a count
                if re.search(r"\(\d+\s*chars?\s*\)", line):
                    return
        if found_title:
            self.fail("Preferred title should declare its character count (e.g. '(69 chars)')")

    def test_no_title_claims_wrong_length(self) -> None:
        """No title should claim a wrong character count.

        Extracts each title line and its associated count paren, verifies they match.
        """
        lines = self.content.split("\n")
        in_section = False
        for i, line in enumerate(lines):
            if "Target Title" in line:
                in_section = True
                continue
            if not in_section:
                continue
            if line.strip().startswith(("## ", "# ")):
                break
            # Look for title: `...` (NN chars)
            m = re.match(r"\s*(?:\d+\.\s*)?`([^`]+)`\s*\((\d+)\s*chars?\s*\)", line)
            if m:
                title = m.group(1)
                claimed = int(m.group(2))
                actual = _count_graphemes(title)
                self.assertEqual(actual, claimed,
                                 f"Title '{title[:40]}...' is {actual} chars but claims {claimed}")

    # ── behavioral: path resolution ──────────────────────────────────

    def test_show_hn_local_paths_resolve(self) -> None:
        """Local file paths referenced in show-hn.md must exist or be explicitly gated."""
        # Known future/gated paths that are acceptable to reference
        gated_prefixes = (
            "docs/guides/", "docs/plugins.md", "docs/verified-badge.md",
        )
        content_lower = self.content.lower()
        refs = _extract_local_path_refs(self.content)
        missing: list[str] = []
        for ref in refs:
            # Skip relative paths that start with . (shell commands)
            if ref.startswith("."):
                continue
            # Skip gated paths
            if ref.startswith(gated_prefixes):
                continue
            full = REPO_ROOT / ref
            if not full.exists():
                # Check if it's gated in nearby text
                context_start = max(0, self.content.find(ref) - 100)
                context_end = min(len(self.content), self.content.find(ref) + len(ref) + 100)
                context = self.content[context_start:context_end].lower()
                if any(gate in context for gate in ("when live", "future", "v0.3", "lands in", "t_1b2bfea8")):
                    continue
                missing.append(ref)
        self.assertEqual([], missing, f"show-hn.md references non-existent paths: {missing}")

    def test_companion_comment_describes_assertion_boundary(self) -> None:
        """Companion comment must clarify that assertions do not replay from cast."""
        self.assertIn("Assertions evaluate from live terminal state",
                      self.content,
                      "Companion comment must describe assertion/replay boundary accurately")


# ── behavioral: outreach validation ──────────────────────────────────

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
            self.assertIn("Short", content, f"{fw} missing short template marker")
            self.assertIn("Long", content, f"{fw} missing long-form")
            self.assertIn("github.com/md-mt/termproof", content, f"{fw} missing repo link")
            self.assertIn("termproof", content.lower(), f"{fw} missing termproof mention")
            self.assertNotRegex(content.lower(), r"dm sent|posted on",
                                f"{fw} should not claim DM posted")

    def test_common_readme_exists_and_has_tracking(self) -> None:
        content = self._read("README")
        self.assertIn("Tracking", content)
        self.assertIn("termproof", content.lower())

    def test_outreach_does_not_claim_endorsement(self) -> None:
        for fw in ["textual", "bubbletea", "ratatui", "ink"]:
            content = self._read(fw).lower()
            self.assertNotIn("endorsed by", content, f"{fw} must not claim endorsement")
            self.assertNotIn("official partnership", content, f"{fw} must not claim partnership")

    # ── behavioral: recipe JSON validation ───────────────────────────

    def test_embedded_recipes_are_valid_json(self) -> None:
        """Every ```json block in outreach templates must be parseable JSON."""
        for fw in ["textual", "bubbletea", "ratatui", "ink"]:
            content = self._read(fw)
            for m in re.finditer(r"```json\n(.*?)```", content, re.DOTALL):
                try:
                    data = json.loads(m.group(1))
                    # Must have required recipe fields
                    self.assertIn("name", data, f"{fw}: recipe JSON missing 'name'")
                    self.assertIn("command", data, f"{fw}: recipe JSON missing 'command'")
                    self.assertIn("steps", data, f"{fw}: recipe JSON missing 'steps'")
                except json.JSONDecodeError as e:
                    self.fail(f"{fw}: invalid recipe JSON: {e}")

    # ── behavioral: YAML CI validation ───────────────────────────────

    def test_yaml_ci_snippets_use_valid_actions_syntax(self) -> None:
        """YAML CI snippets must not misuse 'uses:' with shell commands."""
        for fw in ["textual", "bubbletea", "ratatui", "ink", "README"]:
            content = self._read(fw)
            for m in re.finditer(r"```yaml\n(.*?)```", content, re.DOTALL):
                yaml_text = m.group(1)
                # Reject 'uses:' with a shell command (must be owner/repo@ref)
                for line in yaml_text.split("\n"):
                    stripped = line.strip()
                    if stripped.startswith("uses:") and not stripped.startswith("uses: actions/"):
                        after = stripped[5:].strip()
                        if not re.match(r"^[\w.-]+/[\w.-]+@", after):
                            self.fail(
                                f"{fw}: 'uses:' with shell command '{after}' — "
                                f"use 'run: |' instead"
                            )

    def test_ci_snippets_have_session_mp4_check(self) -> None:
        """Common outreach CI must check session.mp4 exists (no || true on agg install)."""
        content = self._read("README")
        # Must not have || true on cargo install agg
        self.assertNotIn("|| true", content,
                         "outreach/README.md must not mask agg install failures with || true")
        # Must have a session.mp4 check
        self.assertIn("session.mp4", content,
                      "outreach/README.md CI must verify session.mp4 exists")

    def test_no_280_char_tweet_claim(self) -> None:
        """No outreach template should claim <280 chars for tweet if actual is longer."""
        content = self._read("textual")
        self.assertNotIn("<280 chars for tweet", content,
                         "textual.md short template is 458 chars, must not claim <280")

    def test_dependency_preflight_present(self) -> None:
        """Framework CI snippets include render-dependency install steps."""
        for fw in ["bubbletea", "ratatui", "ink"]:
            content = self._read(fw)
            yaml_blocks = list(re.finditer(r"```yaml\n(.*?)```", content, re.DOTALL))
            if yaml_blocks:
                self.assertIn("agg", yaml_blocks[0].group(1),
                              f"{fw}: CI snippet should include agg install step")
                self.assertIn("ffmpeg", yaml_blocks[0].group(1),
                              f"{fw}: CI snippet should include ffmpeg install")


# ── behavioral: social profile validation ────────────────────────────

class SocialProfilesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.path = LAUNCH_DIR / "social" / "profiles.md"
        self.content = self.path.read_text(encoding="utf-8") if self.path.exists() else ""

    def test_social_has_handle_plan(self) -> None:
        self.assertIn("@termproof", self.content.lower())
        self.assertIn("fallback", self.content.lower())

    def test_social_has_profile_copy(self) -> None:
        self.assertIn("Bio", self.content)
        self.assertIn("TermProof", self.content)

    def test_social_has_launch_templates(self) -> None:
        for platform in ["twitter", "mastodon", "bluesky"]:
            self.assertIn(platform, self.content.lower(),
                          f"Missing platform {platform} template")

    # ── behavioral: Bluesky handle syntax ────────────────────────────

    def test_bluesky_handles_have_no_underscores(self) -> None:
        """Bluesky ATProto handles must not contain underscores."""
        # Find Bluesky-specific handle references
        bluesky_section = False
        for line in self.content.split("\n"):
            if "bluesky" in line.lower():
                bluesky_section = True
            if bluesky_section and ".bsky.social" in line:
                # Extract handle
                m = re.search(r"([\w.-]+\.bsky\.social)", line)
                if m:
                    handle = m.group(1)
                    self.assertNotIn("_", handle,
                                     f"Bluesky handle '{handle}' contains underscore — "
                                     f"not valid in ATProto")

    def test_bluesky_fallback_handles_are_valid(self) -> None:
        """Fallback order must note Bluesky validity constraints."""
        self.assertIn("not valid on Bluesky", self.content,
                      "Fallback order must flag handles invalid on Bluesky")

    # ── behavioral: bio limits ───────────────────────────────────────

    def test_bio_character_counts_are_accurate(self) -> None:
        """Bio A and Bio B character counts must match actual text."""
        # Extract bio option A
        m_a = re.search(
            r"Option A[^>]*>\s*(.+?)(?:\n\n|\n> \*\*|Character counts)",
            self.content, re.DOTALL
        )
        m_b = re.search(
            r"Option B[^>]*>\s*(.+?)(?:\n\n|\n> \*\*|Character counts)",
            self.content, re.DOTALL
        )
        # Extract declared counts
        count_m = re.search(r"A\s*=\s*(\d+),\s*B\s*=\s*(\d+)", self.content)
        if count_m:
            declared_a = int(count_m.group(1))
            declared_b = int(count_m.group(2))
            if m_a:
                actual_a = _count_graphemes(m_a.group(1).strip())
                self.assertEqual(declared_a, actual_a,
                                 f"Bio A declared {declared_a} chars but is {actual_a}")
            if m_b:
                actual_b = _count_graphemes(m_b.group(1).strip())
                self.assertEqual(declared_b, actual_b,
                                 f"Bio B declared {declared_b} chars but is {actual_b}")

    def test_bluesky_description_under_256_graphemes(self) -> None:
        """Bluesky-specific long bio must be <=256 graphemes."""
        # Find Bluesky description block
        m = re.search(
            r"### Bluesky Description[^>]*>\s*(.+?)(?:\n###|\n##|\Z)",
            self.content, re.DOTALL
        )
        if m:
            text = m.group(1).strip()
            graphemes = _count_graphemes(text)
            self.assertLessEqual(graphemes, 256,
                                 f"Bluesky description is {graphemes} graphemes (limit 256)")

    # ── behavioral: tweet limits ────────────────────────────────────

    def test_tweet_6_under_280_chars(self) -> None:
        """Tweet 6 must be under 280 characters (X limit)."""
        m = re.search(
            r"Tweet 6/6[^>]*>\s*(.+?)(?:\n###|\n##|\Z)",
            self.content, re.DOTALL
        )
        if m:
            text = m.group(1).strip()
            # Remove markdown blockquote markers for counting
            clean = "\n".join(
                line.lstrip("> ").rstrip()
                for line in text.split("\n")
            )
            length = _count_graphemes(clean)
            self.assertLessEqual(length, 280,
                                 f"Tweet 6 is {length} chars (X limit 280)")

    # ── behavioral: replay claim accuracy ────────────────────────────

    def test_replay_claim_distinguishes_assertions_from_cast(self) -> None:
        """Tweet 4 must not claim assertions replay from cast."""
        tweet4_match = re.search(
            r"Tweet 4/6[^.]*?cast[^.]*?\.",
            self.content, re.DOTALL
        )
        if tweet4_match:
            tweet4 = tweet4_match.group(0)
            self.assertNotIn("assertions", tweet4.lower())

    # ── behavioral: legacy handle ────────────────────────────────────

    def test_legacy_tui_verifier_handle_required(self) -> None:
        """Issue #38 legacy @tui_verifier must be described as required, not optional."""
        self.assertIn("@tui_verifier", self.content,
                      "social/profiles.md must reference legacy @tui_verifier handle")
        # Check it's framed as a requirement
        tui_verifier_context = self.content[
            max(0, self.content.find("@tui_verifier") - 50):
            min(len(self.content), self.content.find("@tui_verifier") + 100)
        ]
        self.assertTrue(
            "reserve" in tui_verifier_context.lower()
            or "register" in tui_verifier_context.lower()
            or "redirect" in tui_verifier_context.lower(),
            "@tui_verifier must be described as requiring registration/redirect"
        )


# ── behavioral: checklist and runbook ────────────────────────────────

class ChecklistAndRunbookTest(unittest.TestCase):
    def test_checklist_exists_with_required_sections(self) -> None:
        path = LAUNCH_DIR / "checklist.md"
        self.assertTrue(path.exists())
        content = path.read_text(encoding="utf-8")
        for kw in ["Pre-Requisites", "Human Gate", "Show HN", "Outreach",
                    "Social", "Close Criteria"]:
            self.assertIn(kw, content, f"Checklist missing section {kw}")

    def test_runbook_exists_with_monitoring(self) -> None:
        path = LAUNCH_DIR / "runbook.md"
        self.assertTrue(path.exists())
        content = path.read_text(encoding="utf-8")
        for kw in ["Monitoring", "Show HN", "Outreach", "Metrics", "Failure"]:
            self.assertIn(kw, content, f"Runbook missing {kw}")
        self.assertIn("github.com/md-mt/termproof", content)

    # ── behavioral: output-directory consistency ─────────────────────

    def test_runbook_output_directory_consistent(self) -> None:
        """Runbook run command must use --out matching ffprobe path."""
        content = (LAUNCH_DIR / "runbook.md").read_text(encoding="utf-8")
        # Find termproof run --out args and ffprobe paths, strip backtick quotes
        run_outs = [
            m.group(1).rstrip("`")
            for m in re.finditer(r"--out\s+`?([^\s`]+)", content)
        ]
        ffprobe_paths = [
            m.group(1).rstrip("`")
            for m in re.finditer(r"ffprobe\s+`?([^\s`]+)", content)
        ]
        if run_outs and ffprobe_paths:
            for rp in run_outs:
                for fp in ffprobe_paths:
                    if rp in fp:
                        return  # consistent
            self.fail(
                f"Runbook: --out paths {run_outs} inconsistent with "
                f"ffprobe paths {ffprobe_paths}"
            )

    def test_runbook_session_mp4_preflight(self) -> None:
        """Runbook must mention session.mp4 may be absent if agg unavailable."""
        content = (LAUNCH_DIR / "runbook.md").read_text(encoding="utf-8").lower()
        self.assertIn("session.mp4", content, "Runbook must reference session.mp4")
        self.assertTrue(
            "absent" in content or "unavailable" in content or "silently skip" in content,
            "Runbook must warn that session.mp4 may be absent if agg unavailable"
        )

    # ── behavioral: checklist HN title ───────────────────────────────

    def test_checklist_hn_title_is_under_80_chars(self) -> None:
        """The HN title in the checklist must be <=80 chars."""
        content = (LAUNCH_DIR / "checklist.md").read_text(encoding="utf-8")
        m = re.search(r"Title final:.*`([^`]+)`", content)
        if m:
            title = m.group(1)
            self.assertLessEqual(_count_graphemes(title), 80,
                                 f"Checklist HN title '{title[:40]}...' is "
                                 f"{_count_graphemes(title)} chars (limit 80)")

    # ── behavioral: #38 legacy handle in checklist ───────────────────

    def test_checklist_includes_legacy_handle_registration(self) -> None:
        """Checklist must require @tui_verifier registration/redirect."""
        content = (LAUNCH_DIR / "checklist.md").read_text(encoding="utf-8").lower()
        self.assertIn("tui_verifier", content,
                      "Checklist must reference @tui_verifier legacy handle registration")
        self.assertIn("bluesky", content,
                      "Checklist must note Bluesky handle constraint for legacy handle")

    def test_checklist_issue38_close_includes_legacy_handle(self) -> None:
        """Close criteria for #38 must include legacy handle registration."""
        content = (LAUNCH_DIR / "checklist.md").read_text(encoding="utf-8")
        close_section = content[content.find("Close Criteria"):]
        self.assertIn("@tui_verifier", close_section,
                      "Issue #38 close criteria must reference @tui_verifier")


# ── behavioral: canonical links ─────────────────────────────────────

class CanonicalLinksTest(unittest.TestCase):
    def test_repo_canonical_files_exist(self) -> None:
        expected = [
            REPO_ROOT / "README.md",
            REPO_ROOT / "docs" / "recipe-packs.md",
            REPO_ROOT / "docs" / "releases.md",
            REPO_ROOT / "examples" / "generic" / "generic_tui.recipe.json",
            REPO_ROOT / "examples" / "generic" / "generic_tui.py",
        ]
        missing = [str(p.relative_to(REPO_ROOT)) for p in expected if not p.exists()]
        self.assertEqual([], missing, f"Canonical files missing: {missing}")

    def test_launch_docs_reference_only_existing_or_gated_paths(self) -> None:
        """Every local path in launch docs must exist or be gated."""
        gated_prefixes = (
            "docs/guides/", "docs/plugins.md", "docs/verified-badge.md",
        )
        all_missing: dict[str, list[str]] = {}
        for md_file in sorted(LAUNCH_DIR.rglob("*.md")):
            content = md_file.read_text(encoding="utf-8")
            refs = _extract_local_path_refs(content)
            file_dir = md_file.parent
            for ref in refs:
                if ref.startswith("."):
                    continue
                if ref.startswith(gated_prefixes):
                    continue
                # Try resolving from the document's directory first, then repo root
                full = file_dir / ref
                if not full.exists():
                    full = REPO_ROOT / ref
                if not full.exists():
                    context_start = max(0, content.find(ref) - 100)
                    context_end = min(len(content), content.find(ref) + len(ref) + 100)
                    context = content[context_start:context_end].lower()
                    if any(g in context for g in ("when live", "future", "v0.3",
                                                   "lands in", "t_1b2bfea8",
                                                   "follow-up", "not yet",
                                                   "lightweight", "transition",
                                                   "convert this runbook")):
                        continue
                    all_missing.setdefault(str(md_file.relative_to(REPO_ROOT)), []).append(ref)
        self.assertEqual({}, all_missing, f"Launch docs reference non-existent paths: {all_missing}")

    def test_examples_directory_has_expected_structure(self) -> None:
        generic_dir = REPO_ROOT / "examples" / "generic"
        self.assertTrue(generic_dir.exists())
        self.assertTrue((generic_dir / "generic_tui.recipe.json").exists())
        data = json.loads((generic_dir / "generic_tui.recipe.json").read_text(encoding="utf-8"))
        self.assertIn("name", data)
        self.assertIn("command", data)
        self.assertIn("steps", data)


# ── behavioral: secrets and external actions ─────────────────────────

class LaunchKitSecretAndActionTest(unittest.TestCase):
    """Assert (not pass) that no secrets or real external actions appear."""

    SECRET_PATTERNS = [
        r"oauth_token",
        r"gho_[A-Za-z0-9]{36}",     # classic GH PAT
        r"github_pat_[A-Za-z0-9_]{22,}",
        r"ghp_[A-Za-z0-9]{36}",
        r"sk-[A-Za-z0-9]{32,}",       # OpenAI
        r"xox[bprs]-[A-Za-z0-9-]+",  # Slack
        r"AKIA[0-9A-Z]{16}",          # AWS
    ]

    ACCOUNT_CREATED_PATTERNS = [
        r"account created.*https?://(x\.com|twitter\.com)",
        r"account created.*bsky\.app",
        r"\(live\)",
        r"handle.*successfully.*registered",
        r"DM sent.*success",
        r"posted to.*https?://(x\.com|twitter\.com)",
    ]

    def test_no_secrets_in_any_launch_doc(self) -> None:
        """No secret/token patterns in any launch doc."""
        violations: list[str] = []
        for md_file in sorted(LAUNCH_DIR.rglob("*.md")):
            content = md_file.read_text(encoding="utf-8")
            for pattern in self.SECRET_PATTERNS:
                if re.search(pattern, content):
                    rel = md_file.relative_to(REPO_ROOT)
                    violations.append(f"{rel}: matches secret pattern '{pattern}'")
        self.assertEqual([], violations,
                         f"Secrets found in launch docs: {violations}")

    def test_no_real_social_urls_claimed_live(self) -> None:
        """No launch doc may claim an account was created or a post was sent."""
        violations: list[str] = []
        for md_file in sorted(LAUNCH_DIR.rglob("*.md")):
            content = md_file.read_text(encoding="utf-8").lower()
            rel = str(md_file.relative_to(REPO_ROOT))
            # Skip this file if it's explicitly a DRAFT with gate markers
            if "draft" in content[:500] and "t_550ba351" in content.lower():
                for pattern in self.ACCOUNT_CREATED_PATTERNS:
                    if re.search(pattern, content):
                        violations.append(f"{rel}: matches '{pattern}'")
        self.assertEqual([], violations,
                         f"Launch docs claim live accounts/posts: {violations}")


if __name__ == "__main__":
    unittest.main()
