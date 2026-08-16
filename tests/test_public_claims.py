"""No user-visible surface may carry a claim the code does not support.

Three consecutive review rounds on the attributed-rendering change found the
same overclaim surviving in a place the previous manual sweep had not reached:
first module docstrings, then the PR body, then the published site page. Each
round the fix was to correct that surface; each round a different one was
missed. Sweeping by hand does not converge, so the sweep lives here instead.

This is a regression net, not a semantic checker. Every pattern below is a
phrasing that actually shipped and actually had to be corrected, so a new one is
added when a new one is found rather than guessed at in advance. What it buys is
that a correction stays corrected, and that a claim reintroduced on a surface
nobody thought to look at fails a test rather than a review.

`SURFACES` is the enumeration itself, and is the part worth reviewing: a
user-visible file not matched by it is not checked at all.
"""

from __future__ import annotations

import ast
import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

#: Every tracked path that can carry a claim a reader will believe. Generated
#: artifacts are excluded because they are renderer output, not prose.
#:
#: Deliberately wider than prose: package metadata (`pyproject.toml` description
#: and keywords, the Homebrew formula's `desc`, `action.yml`), the docs-site
#: config that supplies the site's `<meta>` description, container labels and
#: shell scripts that echo to a user have all been claim surfaces on other
#: projects even where they are currently clean here.
SURFACE_GLOBS = (
    "*.md",
    "*.html",
    "*.py",
    "*.toml",
    "*.rb",
    "*.yml",
    "*.yaml",
    "*.mts",
    "*.sh",
    "*.json",
    "*Dockerfile",
)

#: Trees that hold recorded evidence or fixtures rather than prose.
EXCLUDED_PREFIXES = (
    "examples/artifacts/",
    "tests/fixtures/",
    "site/artifacts/",
    "_site/",
)


def _tracked_surfaces() -> list[Path]:
    """Tracked files that can carry a user-visible claim.

    Driven off `git ls-files` rather than a hand-maintained list, so a new
    documentation page is covered the moment it is added.
    """
    listing = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    paths = []
    for name in listing.split("\0"):
        if not name or name.startswith(EXCLUDED_PREFIXES):
            continue
        path = Path(name)
        if any(path.match(glob) for glob in SURFACE_GLOBS):
            paths.append(ROOT / path)
    return paths


#: `(pattern, why)`. Each is a phrasing that shipped and had to be withdrawn.
BANNED = (
    (
        re.compile(r"colou?r in every (?:rendered )?artifact", re.I),
        "per-step screenshots are rendered from plain text and are monochrome; "
        "name final.svg and the attributed video instead",
    ),
    (
        re.compile(r"the same attributed (?:grid|screen) the screenshots use", re.I),
        "only final.svg is rendered from the grid; say which artifact",
    ),
    (
        re.compile(r"a screenshot of the same moment are\s+(?:\n\s*)?then the same image", re.I),
        "true of the final screenshot only, not the per-step images",
    ),
    (
        re.compile(r"\basciinema\b[^.<]{0,40}\brecords the (?:session|real PTY)\b", re.I),
        "the default backend writes the cast itself; the asciinema CLI is "
        "optional, behind termproof[record]",
    ),
    (
        re.compile(r"records?[^.<]{0,40}\bwith asciinema\b", re.I),
        "same: the CLI no longer does the recording; say 'in asciinema format'",
    ),
    (
        re.compile(r"colou?r (?:SVGs|screenshots)\b", re.I),
        "unqualified plural reads as the whole artifact set; name final.svg",
    ),
    (
        # The shipped defect was an attribute list, not a sentence about dim.
        # Matching prose would flag the correctly-qualified statements that
        # replaced it ("dim is carried only when the grid is parsed from SGR
        # text"), and a pattern with false positives teaches people to add
        # exemptions rather than to read it.
        re.compile(r"bold,\s*dim,", re.I),
        "listing dim among supported attributes without naming the path; it is "
        "dropped on the cast-replay path, where final.svg and the video come from",
    ),
)


class PublicClaimsTest(unittest.TestCase):
    def test_the_enumeration_is_not_vacuous(self) -> None:
        """Guard the guard: a broken glob would silently check nothing."""
        surfaces = _tracked_surfaces()
        self.assertGreater(len(surfaces), 100, "surface enumeration collapsed")
        names = {path.relative_to(ROOT).as_posix() for path in surfaces}
        # The three surfaces that each escaped a round, plus package metadata.
        for required in (
            "README.md",
            "CHANGELOG.md",
            "AGENTS.md",
            "site/index.html",
            "docs/plugins.md",
            "docs/plugin-protocols.md",
            "examples/colorstress/README.md",
            "termproof/cast_video.py",
            "termproof/attributed.py",
            "pyproject.toml",
            "action.yml",
            "Formula/termproof.rb",
            "docs-site/.vitepress/config.mts",
            "docker/termproof.Dockerfile",
            "examples/apps/multi_turn_conversation.py",
        ):
            self.assertIn(required, names, f"{required} is not being checked")

    def test_no_surface_carries_a_withdrawn_claim(self) -> None:
        offenders = []
        for path in _tracked_surfaces():
            text = path.read_text(encoding="utf-8", errors="replace")
            for pattern, why in BANNED:
                for match in pattern.finditer(text):
                    line = text[: match.start()].count("\n") + 1
                    offenders.append(
                        f"{path.relative_to(ROOT).as_posix()}:{line}: "
                        f"{match.group(0)!r} — {why}"
                    )
        self.assertEqual([], sorted(offenders), "\n" + "\n".join(sorted(offenders)))

    def test_module_docstrings_are_covered_too(self) -> None:
        """Docstrings were the first surface a sweep missed.

        The file-level scan above already reads `.py` files whole, so this only
        has to prove docstrings are reachable prose rather than incidentally
        skipped.
        """
        parsed = 0
        for path in sorted((ROOT / "termproof").glob("*.py")):
            doc = ast.get_docstring(ast.parse(path.read_text(encoding="utf-8")))
            if doc:
                parsed += 1
                for pattern, why in BANNED:
                    self.assertIsNone(
                        pattern.search(doc),
                        f"{path.name} docstring carries a withdrawn claim — {why}",
                    )
        self.assertGreater(parsed, 5, "no module docstrings found to check")


if __name__ == "__main__":
    unittest.main()
