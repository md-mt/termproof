from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

from termproof.before_after import build_before_after
from termproof.build_info import BuildInfo
from termproof.models import AssertionResult, CommandSpec, Recipe, RunResult
from termproof.registry import load_recipes, select_recipes
from termproof.renderer import selected_renderers
from termproof.report import ReportGenerator


class StackDesignTest(unittest.TestCase):
    def test_registry_loads_and_filters_recipe_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            nested = Path(tmp) / "pack"
            nested.mkdir()
            path = nested / "demo.recipe.json"
            path.write_text(
                """{
  "name": "demo",
  "priority": "P0",
  "command": {"argv": ["python3", "--version"], "pty": false}
}
""",
                encoding="utf-8",
            )
            recipes = load_recipes([Path(tmp)])
            self.assertEqual(["demo"], [recipe.name for recipe in recipes])
            self.assertEqual(["demo"], [r.name for r in select_recipes(recipes, "P0")])
            self.assertEqual([], select_recipes(recipes, "P1"))

    def test_renderer_selection_expands_all(self) -> None:
        recipe = Recipe(
            name="demo",
            command=CommandSpec(argv=["demo"]),
            renderers={"default": [], "alt": ["--alt"]},
        )
        self.assertEqual(
            [("default", []), ("alt", ["--alt"])],
            selected_renderers(recipe, "all"),
        )
        self.assertEqual([("alt", ["--alt"])], selected_renderers(recipe, "alt"))

    def test_build_info_records_command_provenance(self) -> None:
        info = BuildInfo.from_command([sys.executable, "--version"])
        self.assertEqual("installed", info.mode)
        self.assertTrue(info.binary_path)
        self.assertIn("Python", info.version)
        self.assertTrue(info.verify_provenance())

    def test_report_includes_renderer_and_build_info(self) -> None:
        result = _result("demo", True, "default")
        report = ReportGenerator().generate_markdown(
            [result],
            build_info=BuildInfo.from_command([sys.executable, "--version"]),
        )
        self.assertIn("1/1 Passed", report)
        self.assertIn("Build Provenance", report)
        self.assertIn("`default`", report)
        self.assertIn("[video](session.mp4)", report)

    def test_before_after_delta_matches_recipe_and_renderer(self) -> None:
        before = [_result("demo", True, "default"), _result("demo", True, "alt")]
        after = [_result("demo", False, "default"), _result("demo", True, "alt")]
        before_after = build_before_after(before, after)
        self.assertEqual(1, len(before_after.deltas))
        self.assertEqual("default", before_after.deltas[0].renderer)
        self.assertIn("PASS -> FAIL", before_after.to_markdown())


def _result(recipe: str, passed: bool, renderer: str) -> RunResult:
    return RunResult(
        recipe_name=recipe,
        passed=passed,
        exit_code=0 if passed else 1,
        duration_seconds=1.0,
        priority="P0",
        execution="scripted",
        renderer=renderer,
        score=1.0 if passed else 0.0,
        steps=[],
        assertions=[AssertionResult("ok", passed, "detail")],
        artifacts={"video": "session.mp4"},
    )
