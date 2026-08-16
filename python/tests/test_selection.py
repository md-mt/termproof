from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from termproof.selection import (
    matches_any,
    normalize_path,
    read_changed_files,
    select_names,
)

CANDIDATES = [
    ("smoke", ["src/core/**"]),
    ("editor", ["src/editor/**", "src/keys.py"]),
    ("viewer", ["src/viewer/**"]),
]


class NormalizePathTest(unittest.TestCase):
    def test_backslashes_become_slashes(self) -> None:
        self.assertEqual("src/a/b.py", normalize_path("src\\a\\b.py"))

    def test_leading_dot_slash_and_trailing_slash_go(self) -> None:
        self.assertEqual("src/a", normalize_path("././src/a/"))

    def test_a_root_marker_strips_everything_before_it(self) -> None:
        self.assertEqual("repo/src/a.py", normalize_path("/home/ci/work/repo/src/a.py", "repo"))

    def test_without_a_marker_an_absolute_path_is_left_alone(self) -> None:
        self.assertEqual("/home/ci/repo/src/a.py", normalize_path("/home/ci/repo/src/a.py"))

    def test_a_marker_that_does_not_appear_changes_nothing(self) -> None:
        self.assertEqual("src/a.py", normalize_path("src/a.py", "repo"))


class MatchesAnyTest(unittest.TestCase):
    def test_a_glob_matches_a_nested_path(self) -> None:
        self.assertTrue(matches_any(["src/core/**"], ["src/core/deep/file.py"]))

    def test_no_overlap_does_not_match(self) -> None:
        self.assertFalse(matches_any(["src/core/**"], ["docs/readme.md"]))

    def test_an_empty_pattern_list_matches_nothing(self) -> None:
        self.assertFalse(matches_any([], ["anything"]))

    def test_an_exact_path_matches_itself(self) -> None:
        self.assertTrue(matches_any(["src/keys.py"], ["src/keys.py"]))


class SelectNamesTest(unittest.TestCase):
    def test_only_the_recipes_covering_the_change(self) -> None:
        self.assertEqual(["editor"], select_names(CANDIDATES, ["src/editor/buffer.py"]))

    def test_several_recipes_can_match_one_change(self) -> None:
        selected = select_names(CANDIDATES, ["src/editor/a.py", "src/viewer/b.py"])
        self.assertEqual(["editor", "viewer"], selected)

    def test_an_unmatched_change_selects_nothing(self) -> None:
        self.assertEqual([], select_names(CANDIDATES, ["docs/readme.md"]))

    def test_always_recipes_run_regardless(self) -> None:
        self.assertEqual(["smoke"], select_names(CANDIDATES, ["docs/readme.md"], always=["smoke"]))

    def test_an_always_name_that_is_not_a_candidate_is_ignored(self) -> None:
        self.assertEqual([], select_names(CANDIDATES, ["docs/x.md"], always=["nonexistent"]))

    def test_a_recipe_is_not_selected_twice(self) -> None:
        selected = select_names(CANDIDATES, ["src/editor/a.py", "src/keys.py"], always=["editor"])
        self.assertEqual(["editor"], selected)

    def test_the_order_follows_the_candidate_list(self) -> None:
        selected = select_names(CANDIDATES, ["src/viewer/a.py", "src/editor/b.py"])
        self.assertEqual(["editor", "viewer"], selected)

    def test_touching_the_harness_falls_back_to_the_always_set(self) -> None:
        """The path-to-recipe mapping is what changed, so it is not evidence."""
        selected = select_names(
            CANDIDATES,
            ["tests/harness/runner.py", "src/editor/a.py"],
            always=["smoke"],
            harness_paths=["tests/harness/**"],
        )
        self.assertEqual(["smoke"], selected)

    def test_the_harness_rule_only_fires_when_the_harness_is_touched(self) -> None:
        selected = select_names(
            CANDIDATES,
            ["src/editor/a.py"],
            always=["smoke"],
            harness_paths=["tests/harness/**"],
        )
        self.assertEqual(["smoke", "editor"], selected)

    def test_a_recipe_with_no_ci_paths_is_never_selected_by_a_change(self) -> None:
        self.assertEqual([], select_names([("orphan", [])], ["anything.py"]))

    def test_absolute_ci_paths_are_matched_through_the_root_marker(self) -> None:
        selected = select_names(
            [("editor", ["repo/src/editor/**"])],
            ["/home/ci/build-42/repo/src/editor/a.py"],
            root_marker="repo",
        )
        self.assertEqual(["editor"], selected)

    def test_no_candidates_selects_nothing(self) -> None:
        self.assertEqual([], select_names([], ["src/editor/a.py"], always=["smoke"]))


class ReadChangedFilesTest(unittest.TestCase):
    def test_one_path_per_line_with_blanks_dropped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "changed.txt"
            path.write_text("src/a.py\n\n  src/b.py  \n\n", encoding="utf-8")
            self.assertEqual(["src/a.py", "src/b.py"], read_changed_files(path))

    def test_an_empty_file_yields_no_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "changed.txt"
            path.write_text("", encoding="utf-8")
            self.assertEqual([], read_changed_files(path))


if __name__ == "__main__":
    unittest.main()
