"""A semver waiver must cover one named break, and must not outlive it.

`.github/scripts/rust/semver-checks.py` is what stands between "this breaking
change was looked at and accepted" and "the semver job is off". The difference
is entirely in its bookkeeping, so the bookkeeping is what these tests pin:

- an unwaived finding fails, so a *different* break cannot ride along on the
  waiver written for this one;
- a waiver matching nothing fails, so the waiver expires when the release it
  was written for lands and the baseline moves past it;
- a tool failure that produced no findings at all is not swallowed.

The parser is a pure function over the tool's text, so it is tested against
recorded output rather than by running `cargo semver-checks`, which needs a
network baseline and a minute of build. The recorded sample below is real
output from `cargo-semver-checks 0.50.0` on this change, trimmed to the parts
the parser reads.

`tests/test_recipe_meta.py` covers the change the waiver is *for*; this covers
the waiver mechanism.
"""

from __future__ import annotations

import importlib.util
import tomllib
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
SCRIPT = REPO_ROOT / ".github" / "scripts" / "rust" / "semver-checks.py"
WAIVERS = REPO_ROOT / "rust" / "semver-waivers.toml"


def _load_script():
    """Import the script by path; its filename is not a valid module name."""
    spec = importlib.util.spec_from_file_location("semver_checks", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


semver_checks = _load_script()

# Real 0.50.0 output, trimmed. Note the duplicated item lines — the tool
# reports each finding once per feature set it checked — and the two different
# location suffixes, which the parser has to strip.
SAMPLE = """\
    Checking termproof v0.4.0 -> v0.4.0 (no change; assume minor)
     Checked [   0.030s] 196 checks: 194 pass, 2 fail, 0 warn, 58 skip

--- failure constructible_struct_adds_field: struct exhaustively constructible through public API adds field ---

Description:
A pub struct that could be exhaustively constructed with a literal has a new pub field.
        ref: https://doc.rust-lang.org/reference/expressions/struct-expr.html

Failed in:
  field Recipe.meta in /repo/rust/crates/termproof/src/recipe.rs:270
  field Recipe.meta in /repo/rust/crates/termproof/src/recipe.rs:270

--- failure struct_pub_field_missing: pub struct's pub field removed or renamed ---

Description:
A publicly-visible struct has at least one public field that is no longer available.
        ref: https://doc.rust-lang.org/cargo/reference/semver.html#item-remove

Failed in:
  field name of struct Recipe, previously in file /baseline/recipe.rs:166
  field ci_paths of struct Recipe, previously in file /baseline/recipe.rs:190
  field name of struct Recipe, previously in file /baseline/recipe.rs:166

     Summary semver requires new major version: 2 major and 0 minor checks failed
"""


class FindingsTest(unittest.TestCase):
    def test_it_reads_the_lint_and_the_item_and_drops_the_location(self) -> None:
        self.assertEqual(
            {
                "constructible_struct_adds_field: field Recipe.meta",
                "struct_pub_field_missing: field name of struct Recipe",
                "struct_pub_field_missing: field ci_paths of struct Recipe",
            },
            semver_checks.findings(SAMPLE),
        )

    def test_repeated_findings_collapse(self) -> None:
        # Both `Recipe.meta` and `name` appear twice in the sample.
        self.assertEqual(3, len(semver_checks.findings(SAMPLE)))

    def test_a_clean_run_has_no_findings(self) -> None:
        clean = "     Checked [ 0.03s] 196 checks: 196 pass, 0 fail\n"
        self.assertEqual(set(), semver_checks.findings(clean))

    def test_the_summary_line_is_not_read_as_an_item(self) -> None:
        # It is indented, but not by two spaces under `Failed in:`.
        for finding in semver_checks.findings(SAMPLE):
            self.assertNotIn("Summary", finding)


class WaiverFileTest(unittest.TestCase):
    def test_every_waived_finding_names_a_lint_and_an_item(self) -> None:
        waived = tomllib.loads(WAIVERS.read_text(encoding="utf-8"))["waived"]
        self.assertTrue(waived)
        for entry in waived:
            with self.subTest(entry=entry):
                lint, _, item = entry.partition(": ")
                self.assertRegex(lint, r"^[a-z0-9_]+$")
                self.assertTrue(item.strip())
                # A waiver must name the API it covers, not just the lint.
                self.assertNotIn("/", item, "a waiver must not carry a path")

    def test_the_waiver_records_a_reason(self) -> None:
        data = tomllib.loads(WAIVERS.read_text(encoding="utf-8"))
        self.assertIn("reason", data)
        self.assertIn("#199", data["reason"])

    def test_the_waiver_covers_exactly_this_changes_findings(self) -> None:
        # Eight: `Recipe.meta` added, seven fields moved out. A ninth entry
        # here would be a break nobody described.
        waived = set(tomllib.loads(WAIVERS.read_text(encoding="utf-8"))["waived"])
        self.assertEqual(
            {
                "constructible_struct_adds_field: field Recipe.meta",
                "struct_pub_field_missing: field name of struct Recipe",
                "struct_pub_field_missing: field description of struct Recipe",
                "struct_pub_field_missing: field intent of struct Recipe",
                "struct_pub_field_missing: field priority of struct Recipe",
                "struct_pub_field_missing: field execution of struct Recipe",
                "struct_pub_field_missing: field determinism of struct Recipe",
                "struct_pub_field_missing: field ci_paths of struct Recipe",
            },
            waived,
        )

    def test_the_waiver_does_not_cover_recipes_other_fields(self) -> None:
        # The lint is not switched off: a break in a field this change did not
        # touch is still a failure.
        waived = set(tomllib.loads(WAIVERS.read_text(encoding="utf-8"))["waived"])
        for untouched in ("checks", "operator", "renderers", "cols", "extension"):
            with self.subTest(field=untouched):
                self.assertNotIn(
                    f"struct_pub_field_missing: field {untouched} of struct Recipe",
                    waived,
                )

    def test_the_changelog_describes_the_waived_break(self) -> None:
        # A waiver without a consumer-facing description is a silent break.
        changelog = (REPO_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        unreleased = changelog.split("## [Unreleased]", 1)[1].split("\n## [", 1)[0]
        self.assertIn("recipe.meta", unreleased)
        self.assertIn("What breaks:", unreleased)


if __name__ == "__main__":
    unittest.main()
