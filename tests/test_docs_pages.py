"""Regression tests for verifier-flagged documentation and Pages defects.

Each test corresponds to a specific finding from the PR #43 review.
"""

from __future__ import annotations

import os
import re
import unittest
from pathlib import Path

# Path to the worktree root (same as tests/ directory parent)
ROOT = Path(__file__).resolve().parent.parent


def _read(path: Path) -> str:
    return path.read_text()


def _html_text(html: str) -> str:
    """Strip HTML tags for content assertion."""
    return re.sub(r"<[^>]+>", "", html)


class CodeOfConductTest(unittest.TestCase):
    """BLOCKING: CODE_OF_CONDUCT.md must have a concrete enforcement contact."""

    def test_enforcement_section_has_concrete_email(self) -> None:
        coc = _read(ROOT / "CODE_OF_CONDUCT.md")
        # Split on "## Enforcement\n" (not "## Enforcement Responsibilities")
        parts = coc.split("## Enforcement\n")
        self.assertGreater(len(parts), 1,
                           "CODE_OF_CONDUCT.md must have a '## Enforcement' section")
        enforcement = parts[1].split("\n## ")[0]
        self.assertIn("@", enforcement,
                      "CODE_OF_CONDUCT.md Enforcement section must contain a "
                      "concrete email address (e.g. md@mt.com)")

    def test_enforcement_does_not_reference_missing_files(self) -> None:
        coc = _read(ROOT / "CODE_OF_CONDUCT.md")
        parts = coc.split("## Enforcement\n")
        self.assertGreater(len(parts), 1)
        enforcement = parts[1].split("\n## ")[0]
        # Must not use the old "email address listed in the repository" placeholder
        self.assertNotIn("email address listed", enforcement,
                         "Enforcement must not redirect to an unspecified address")
        self.assertNotIn("via GitHub Issues (for non-sensitive)",
                         enforcement,
                         "GitHub Issues must not be the primary reporting channel")


class SECURITYTest(unittest.TestCase):
    """BLOCKING: A SECURITY.md must exist with a reporting contact."""

    def test_security_md_exists(self) -> None:
        path = ROOT / "SECURITY.md"
        self.assertTrue(path.is_file(),
                        f"SECURITY.md must exist at {path}")

    def test_security_md_has_contact(self) -> None:
        sec = _read(ROOT / "SECURITY.md")
        self.assertIn("@", sec, "SECURITY.md must contain a contact email")


class ReadmeTest(unittest.TestCase):
    """BLOCKING: README must have valid install commands, embedded demo, and badges."""

    def test_install_command_is_working(self) -> None:
        readme = _read(ROOT / "README.md")
        # Must not claim a PyPI install that doesn't exist
        self.assertNotRegex(readme, r"^pip install termproof$",
                            "README must not use `pip install termproof` (not on PyPI)")
        self.assertNotRegex(readme, r"^uv pip install termproof$",
                            "README must not use `uv pip install termproof` (not on PyPI)")
        # Must have a working install: git URL or from-source
        self.assertTrue(
            "git+https://github.com/md-mt/termproof.git" in readme or
            "git clone https://github.com/md-mt/termproof.git" in readme,
            "README must provide a working install path (git URL or from-source)")

    def test_forks_badge_present(self) -> None:
        readme = _read(ROOT / "README.md")
        self.assertIn("Forks", readme,
                      "README must include a GitHub forks badge")
        self.assertIn("img.shields.io/github/forks", readme,
                      "README must include a shields.io forks badge URL")

    def test_demo_has_embedded_screenshot(self) -> None:
        readme = _read(ROOT / "README.md")
        # Must embed at least one SVG or PNG screenshot in the Demo section
        demo_section = readme.split("## Demo")[1].split("## ")[0] if "## Demo" in readme else ""
        self.assertTrue(
            "![" in demo_section and (".svg" in demo_section or ".png" in demo_section),
            "README Demo section must embed a real screenshot (![alt](path/to/file.svg))")

    def test_demo_references_existing_artifact(self) -> None:
        """The generic-tui-workflow/final.svg that README links to must exist."""
        svg_path = ROOT / "examples/artifacts/generic-tui-workflow/final.svg"
        self.assertTrue(svg_path.is_file(),
                        f"README references {svg_path.relative_to(ROOT)} but it does not exist")

    def test_pages_url_is_gated(self) -> None:
        readme = _read(ROOT / "README.md")
        # Must not claim the Pages URL is live without qualification
        pages_url = "https://md-mt.github.io/termproof/"
        pages_index = readme.find(pages_url)
        if pages_index != -1:
            # The surrounding text must indicate it's conditional
            context = readme[max(0, pages_index - 100):pages_index + len(pages_url) + 100]
            has_gate = any(kw in context.lower() for kw in
                           ["when pages is enabled", "once pages", "preview locally",
                            "after enabling", "if enabled", "enable_pages"])
            self.assertTrue(has_gate,
                            f"README references {pages_url} without gating the claim "
                            f"(repo is private, Pages not enabled)")


class EvidencePageTest(unittest.TestCase):
    """BLOCKING: site/evidence.html must render actual evidence artifacts."""

    def test_evidence_page_has_img_tags(self) -> None:
        html = _read(ROOT / "site/evidence.html")
        # Must have at least one <img> tag referencing a local artifact
        imgs = re.findall(r'<img[^>]+src="([^"]+)"', html)
        local_imgs = [i for i in imgs if not i.startswith("http")]
        self.assertGreater(len(local_imgs), 0,
                           "evidence.html must embed at least one local <img> tag")
        # At least one should reference an SVG
        self.assertTrue(any(i.endswith(".svg") for i in local_imgs),
                        "evidence.html must embed at least one SVG screenshot")

    def test_evidence_page_has_report_links(self) -> None:
        html = _read(ROOT / "site/evidence.html")
        text = _html_text(html)
        # Must reference report files
        self.assertIn("report.md", html.lower(),
                      "evidence.html must reference report artifacts")

    def test_evidence_page_artifact_srcs_are_relative(self) -> None:
        """All local img src must be relative paths (they'll be deployed inside _site)."""
        html = _read(ROOT / "site/evidence.html")
        imgs = re.findall(r'<img[^>]+src="([^"]+)"', html)
        for src in imgs:
            if src.startswith("http"):
                continue  # external badge is fine
            self.assertFalse(src.startswith("/"),
                             f"Image src '{src}' must be relative, not absolute")
            self.assertFalse(src.startswith(".."),
                             f"Image src '{src}' must not escape the site root with '..'")


class PagesWorkflowTest(unittest.TestCase):
    """BLOCKING: pages.yml must copy artifacts into _site and validate links."""

    def test_build_step_copies_curated_artifacts(self) -> None:
        yml = _read(ROOT / ".github/workflows/pages.yml")
        # Must copy from site/artifacts/ (not examples/artifacts/)
        # The build step should reference site/artifacts for curated evidence
        build_section = yml.split("Build site preview")[1].split("Upload Pages artifact")[0] \
            if "Build site preview" in yml else ""
        self.assertIn("site/artifacts", yml,
                      "pages.yml must reference site/artifacts/ (curated evidence pack)")

    def test_link_validation_step_exists(self) -> None:
        yml = _read(ROOT / ".github/workflows/pages.yml")
        self.assertIn("Validate relative links", yml,
                      "pages.yml must have a link validation step")

    def test_pr_trigger_present(self) -> None:
        yml = _read(ROOT / ".github/workflows/pages.yml")
        self.assertIn("pull_request:", yml,
                      "pages.yml must trigger on pull_request for validation")

    def test_deploy_not_on_pr(self) -> None:
        yml = _read(ROOT / ".github/workflows/pages.yml")
        # The deploy job must check github.event_name == 'push'
        deploy_section = yml.split("name: Deploy to Pages")[1].split("environment:")[0] \
            if "name: Deploy to Pages" in yml else ""
        self.assertIn("github.event_name", deploy_section,
                      "pages.yml deploy job must check github.event_name to avoid running on PRs")

    def test_deploy_requires_enable_pages_variable(self) -> None:
        yml = _read(ROOT / ".github/workflows/pages.yml")
        deploy_section = yml.split("name: Deploy to Pages")[1].split("environment:")[0] \
            if "name: Deploy to Pages" in yml else ""

        self.assertIn("vars.ENABLE_PAGES == 'true'", deploy_section)
        self.assertNotIn("github.event.repository.visibility == 'public'", deploy_section)

    def test_skipped_job_runs_when_enable_pages_is_not_true(self) -> None:
        yml = _read(ROOT / ".github/workflows/pages.yml")
        skipped_section = yml.split("name: Pages deploy skipped")[1] \
            if "name: Pages deploy skipped" in yml else ""

        self.assertIn("vars.ENABLE_PAGES != 'true'", skipped_section)
        self.assertIn("Artifact 'termproof-pages-preview' contains the site preview.", skipped_section)


class GenericTuiArtifactsTest(unittest.TestCase):
    """BLOCKING: examples/artifacts/generic-tui-workflow/ must contain demo evidence."""

    def test_generic_tui_artifacts_exist(self) -> None:
        base = ROOT / "examples/artifacts/generic-tui-workflow"
        self.assertTrue(base.is_dir(),
                        f"{base.relative_to(ROOT)} must exist as checked-in demo evidence")
        self.assertTrue((base / "final.svg").is_file(),
                        f"{base.relative_to(ROOT)}/final.svg must exist")
        self.assertTrue((base / "final.txt").is_file(),
                        f"{base.relative_to(ROOT)}/final.txt must exist")
        self.assertTrue((base / "report.md").is_file(),
                        f"{base.relative_to(ROOT)}/report.md must exist")
        self.assertTrue((base / "steps").is_dir(),
                        f"{base.relative_to(ROOT)}/steps/ must exist")

    def test_generic_tui_final_svg_is_valid_svg(self) -> None:
        svg = _read(ROOT / "examples/artifacts/generic-tui-workflow/final.svg")
        self.assertIn("<svg", svg.lower(),
                      "generic-tui-workflow/final.svg must be a valid SVG starting with <svg")
        self.assertIn("</svg>", svg.lower(),
                      "generic-tui-workflow/final.svg must close with </svg>")


class CuratedSiteArtifactsTest(unittest.TestCase):
    """BLOCKING: site/artifacts/ must contain curated evidence for Pages deployment."""

    def test_site_artifacts_exist(self) -> None:
        base = ROOT / "site/artifacts"
        self.assertTrue(base.is_dir(),
                        f"site/artifacts/ must exist as curated evidence for Pages")
        # Generic TUI
        self.assertTrue((base / "generic-tui-workflow/final.svg").is_file(),
                        "site/artifacts/generic-tui-workflow/final.svg must exist")
        # Pi workflow screenshots
        self.assertTrue((base / "pi-workflow-guarded-edit/final.svg").is_file(),
                        "site/artifacts/pi-workflow-guarded-edit/final.svg must exist")
        self.assertTrue((base / "pi-workflow-readonly-review/final.svg").is_file(),
                        "site/artifacts/pi-workflow-readonly-review/final.svg must exist")
        # Reports
        self.assertTrue((base / "latest-report.md").is_file(),
                        "site/artifacts/latest-report.md must exist")
        self.assertTrue((base / "latest-pi-workflows-report.md").is_file(),
                        "site/artifacts/latest-pi-workflows-report.md must exist")


class BuiltSiteLinkTest(unittest.TestCase):
    """Validate that the built _site has no broken relative links."""

    @classmethod
    def setUpClass(cls) -> None:
        # Build _site locally to validate links
        import subprocess
        import shutil
        cls._site = ROOT / "_site"
        # Clean previous build
        if cls._site.exists():
            shutil.rmtree(cls._site)
        cls._site.mkdir()
        # Copy site files
        for item in (ROOT / "site").iterdir():
            dest = cls._site / item.name
            if item.is_dir() and item.name != "artifacts":
                shutil.copytree(item, dest)
            elif item.is_file():
                shutil.copy2(item, dest)
        # Copy curated artifacts (site/artifacts -> _site/artifacts)
        src_artifacts = ROOT / "site" / "artifacts"
        if src_artifacts.is_dir():
            shutil.copytree(src_artifacts, cls._site / "artifacts")
        # Copy docs
        docs_src = ROOT / "docs"
        docs_dst = cls._site / "docs"
        if not docs_dst.exists():
            docs_dst.mkdir()
        if docs_src.is_dir():
            for item in docs_src.iterdir():
                dest = docs_dst / item.name
                if item.is_file():
                    shutil.copy2(item, dest)

    def test_no_broken_relative_links_in_built_site(self) -> None:
        """Every relative href/src in _site HTML files must resolve."""
        failures = []
        for html_file in self._site.rglob("*.html"):
            content = html_file.read_text()
            # Find all href and src attributes
            links = re.findall(r'(?:href|src)="([^"]+)"', content)
            for link in links:
                if link.startswith("http://") or link.startswith("https://"):
                    continue
                if link.startswith("#"):
                    continue
                # Resolve relative to the HTML file's directory
                resolved = (html_file.parent / link).resolve()
                if not resolved.exists():
                    # Normalize: collapse /./ and such
                    resolved_str = os.path.normpath(str(html_file.parent / link))
                    resolved = Path(resolved_str)
                    if not resolved.exists():
                        failures.append(
                            f"{html_file.relative_to(self._site)} -> {link} "
                            f"(resolved: {resolved})")
        self.assertEqual(
            len(failures), 0,
            f"{len(failures)} broken relative links in _site:\n" +
            "\n".join(failures[:20]))


if __name__ == "__main__":
    unittest.main()
