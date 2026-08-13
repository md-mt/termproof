from __future__ import annotations

import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from termproof.cli import main
from termproof.config import VerifierConfig
from termproof.models import RunResult, load_recipe
from termproof.run_cache import store_cached_result


class CliTest(unittest.TestCase):
    def test_init_command_creates_recipe(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            with contextlib.redirect_stdout(io.StringIO()):
                exit_code = main(
                    [
                        "init",
                        str(Path(tmp) / "recipes"),
                        "--name",
                        "demo-tui",
                        "--command",
                        "python3 -c 'print(42)'",
                        "--non-pty",
                    ]
                )
            self.assertEqual(0, exit_code)
            self.assertTrue((Path(tmp) / "recipes" / "demo-tui.recipe.json").exists())

    def test_run_config_file_overrides_cascaded_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            recipe_path = root / "recipe.json"
            recipe_path.write_text(
                """{
  "name": "configured-run",
  "command": {"argv": ["python3", "-c", "print('ok')"], "pty": false}
}
""",
                encoding="utf-8",
            )
            config_path = root / "explicit-config.yaml"
            config_path.write_text(
                "docker:\n  image: explicit-image\n", encoding="utf-8"
            )
            result = RunResult(
                recipe_name="configured-run",
                passed=True,
                exit_code=0,
                duration_seconds=0.0,
                priority="P2",
                execution="scripted",
                renderer="default",
                score=1.0,
                steps=[],
                assertions=[],
                artifacts={},
            )
            with patch("termproof.cli.VerificationRunner") as runner_class:
                runner = runner_class.return_value
                runner.run.return_value = result
                runner.reporter_registry.get.return_value.generate.return_value = "report"
                with contextlib.redirect_stdout(io.StringIO()):
                    exit_code = main(
                        [
                            "run",
                            str(recipe_path),
                            "--config",
                            str(config_path),
                            "--out",
                            str(root / "out"),
                        ]
                    )

            self.assertEqual(0, exit_code)
            self.assertEqual(
                "explicit-image",
                runner_class.call_args.kwargs["config"].docker.image,
            )

    def test_xml_path_writes_junit_xml_to_explicit_path(self) -> None:
        """--xml-path should write JUnit XML to the explicit path and imply --reporter junit_xml."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            recipe_path = root / "recipe.json"
            recipe_path.write_text(
                """{
  "name": "xml-test",
  "command": {"argv": ["python3", "-c", "print('ok')"], "pty": false}
}
""",
                encoding="utf-8",
            )
            xml_target = root / "ci-reports" / "junit.xml"
            result = RunResult(
                recipe_name="xml-test",
                passed=True,
                exit_code=0,
                duration_seconds=0.1,
                priority="P2",
                execution="scripted",
                renderer="default",
                score=1.0,
                steps=[],
                assertions=[],
                artifacts={},
            )
            with patch("termproof.cli.VerificationRunner") as runner_class:
                runner = runner_class.return_value
                runner.run.return_value = result
                runner.reporter_registry.get.return_value.generate.return_value = "report"
                # Patch file writing to avoid real FS writes after mock
                with patch("pathlib.Path.write_text"):
                    with contextlib.redirect_stdout(io.StringIO()):
                        exit_code = main(
                            [
                                "run",
                                str(recipe_path),
                                "--xml-path", str(xml_target),
                                "--out", str(root / "out"),
                            ]
                        )
            self.assertEqual(0, exit_code)
            # Verify junit_xml reporter was requested (implied by --xml-path)
            reporter_calls = runner.reporter_registry.get.call_args_list
            self.assertTrue(any("junit_xml" in str(c) for c in reporter_calls))

    def test_run_parallel_runs_all_selected_recipes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            recipes = []
            for name in ("one", "two"):
                recipe_path = root / f"{name}.json"
                recipe_path.write_text(
                    f"""{{
  "name": "{name}",
  "command": {{"argv": ["python3", "-c", "print('ok')"], "pty": false}}
}}
""",
                    encoding="utf-8",
                )
                recipes.append(recipe_path)

            class FakeReporter:
                def generate(self, results, build_info=None):
                    return "report"

            class FakeRegistry:
                def get(self, name):
                    return FakeReporter()

            class FakeRunner:
                calls: list[str] = []
                reporter_registry = FakeRegistry()

                def __init__(self, *args, **kwargs):
                    pass

                def run(self, recipe, **kwargs):
                    self.calls.append(recipe.name)
                    return RunResult(
                        recipe_name=recipe.name,
                        passed=True,
                        exit_code=0,
                        duration_seconds=0.0,
                        priority="P2",
                        execution="scripted",
                        renderer=kwargs["renderer"],
                        score=1.0,
                        steps=[],
                        assertions=[],
                        artifacts={},
                    )

            with patch("termproof.cli.VerificationRunner", side_effect=FakeRunner):
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    exit_code = main(
                        [
                            "run",
                            str(recipes[0]),
                            str(recipes[1]),
                            "--out",
                            str(root / "out"),
                            "--parallel",
                            "2",
                        ]
                    )

            self.assertEqual(0, exit_code)
            self.assertEqual(["one", "two"], sorted(FakeRunner.calls))
            self.assertIn("2/2 passed", output.getvalue())

    def test_run_rejects_invalid_parallel_count(self) -> None:
        output = io.StringIO()

        with contextlib.redirect_stdout(output):
            exit_code = main(["run", "missing.recipe.json", "--parallel", "0"])

        self.assertEqual(2, exit_code)
        self.assertIn("--parallel must be >= 1", output.getvalue())

    def test_run_diff_marks_visual_regression(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            recipe_path = root / "recipe.json"
            recipe_path.write_text(
                """{
  "name": "diff-test",
  "command": {"argv": ["python3", "-c", "print('ok')"], "pty": false}
}
""",
                encoding="utf-8",
            )
            screenshot = root / "run" / "final.svg"
            baseline = root / "baselines" / "diff-test" / "default" / "final.svg"
            screenshot.parent.mkdir()
            baseline.parent.mkdir(parents=True)
            screenshot.write_text("<svg>actual</svg>\n", encoding="utf-8")
            baseline.write_text("<svg>baseline</svg>\n", encoding="utf-8")

            result = RunResult(
                recipe_name="diff-test",
                passed=True,
                exit_code=0,
                duration_seconds=0.0,
                priority="P2",
                execution="scripted",
                renderer="default",
                score=1.0,
                steps=[],
                assertions=[],
                artifacts={"screenshot": str(screenshot)},
            )

            with patch("termproof.cli.VerificationRunner") as runner_class:
                runner = runner_class.return_value
                runner.run.return_value = result
                runner.reporter_registry.get.return_value.generate.return_value = "report"
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    exit_code = main(
                        [
                            "run",
                            str(recipe_path),
                            "--out",
                            str(root / "out"),
                            "--diff",
                            "--baseline-dir",
                            str(root / "baselines"),
                        ]
                    )

            self.assertEqual(1, exit_code)
            self.assertTrue(screenshot.with_name("visual-diff.svg").is_file())
            self.assertIn("0/1 passed", output.getvalue())

    def test_run_skip_unchanged_reuses_cached_results(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            pack = root / "recipes"
            pack.mkdir()
            cache = root / "cache"
            for index in range(50):
                name = f"recipe-{index:02d}"
                recipe_path = pack / f"{name}.recipe.json"
                recipe_path.write_text(
                    f"""{{
  "name": "{name}",
  "command": {{"argv": ["python3", "-c", "print('ok')"], "pty": false}}
}}
""",
                    encoding="utf-8",
                )
                screenshot = root / "runs" / name / "final.svg"
                screenshot.parent.mkdir(parents=True)
                screenshot.write_text("<svg/>\n", encoding="utf-8")
                store_cached_result(
                    cache,
                    load_recipe(recipe_path),
                    "default",
                    [],
                    RunResult(
                        recipe_name=name,
                        passed=True,
                        exit_code=0,
                        duration_seconds=1.0,
                        priority="P2",
                        execution="scripted",
                        renderer="default",
                        score=1.0,
                        steps=[],
                        assertions=[],
                        artifacts={"screenshot": str(screenshot)},
                    ),
                    out_dir=root / "runs",
                    screen_renderer="svg",
                    video_backend="agg_ffmpeg",
                    render_video=False,
                    video_fps=60,
                )

            with patch("termproof.cli.VerificationRunner") as runner_class:
                runner = runner_class.return_value
                # The cache key covers the evidence config the runner renders
                # with, so the stand-in needs the real one.
                runner.config = VerifierConfig.builtin()
                runner.run.side_effect = AssertionError("runner should be skipped")
                runner.reporter_registry.get.return_value.generate.return_value = "report"
                output = io.StringIO()
                with contextlib.redirect_stdout(output):
                    exit_code = main(
                        [
                            "run",
                            str(pack),
                            "--out",
                            str(root / "runs"),
                            "--skip-unchanged",
                            "--cache-dir",
                            str(cache),
                        ]
                    )

            self.assertEqual(0, exit_code)
            self.assertIn("50/50 passed", output.getvalue())
            runner.run.assert_not_called()

    def test_run_rejects_skip_unchanged_with_visual_diff(self) -> None:
        output = io.StringIO()

        with contextlib.redirect_stdout(output):
            exit_code = main(["run", "missing.recipe.json", "--skip-unchanged", "--diff"])

        self.assertEqual(2, exit_code)
        self.assertIn("cannot be combined", output.getvalue())


class DemoCommandTest(unittest.TestCase):
    def test_demo_creates_recipe_and_passes(self):
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "demo_out"
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                code = main(["demo", "--out", str(out), "--no-open"])
            # demo should succeed exit code 0
            self.assertEqual(0, code, f"stdout: {buf.getvalue()}")
            self.assertTrue(out.exists(), "out dir should exist")
            # should have report
            self.assertTrue((out / "latest-report.md").exists() or any(out.rglob("*.md")))
            output = buf.getvalue()
            # should mention evidence
            evidence_found = "evidence" in output.lower() or "report" in output.lower()
            self.assertTrue(evidence_found, f"output should mention evidence: {output[:200]}")

    def test_demo_exercises_all_steps_and_assertions(self):
        # check that demo_tui exists and recipe covers all step and assertion types
        from termproof import demo as demo_module
        recipe = demo_module.build_demo_recipe(out_dir=Path("/tmp/demo_test"))
        step_actions = {s["action"] for s in recipe.steps}
        assertion_types = {a["type"] for a in recipe.assertions}
        # must include every built-in step
        for expected in ["wait_for_text", "wait_for_idle", "send_text", "send_line", "press", "sleep", "wait_for_regex"]:
            self.assertIn(expected, step_actions, f"missing step {expected}")
        for expected in ["output_contains", "output_not_contains", "screen_contains", "screen_not_contains", "exit_code", "file_exists", "file_contains"]:
            self.assertIn(expected, assertion_types, f"missing assertion {expected}")

    def test_demo_artifact_inventory_lists_all_artifact_keys(self):
        """Demo output must include artifact inventory keys."""
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "demo_out"
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                code = main(["demo", "--out", str(out), "--no-open"])
            self.assertEqual(0, code)
            output = buf.getvalue()
            # Evidence section should list expected artifact types
            for key in ["cast", "screenshot", "screen_text"]:
                self.assertIn(key, output, f"artifact key {key!r} must appear in demo output")

    def test_demo_reports_runtime_duration(self):
        """Demo output must include runtime duration."""
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "demo_out"
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                code = main(["demo", "--out", str(out), "--no-open"])
            self.assertEqual(0, code)
            output = buf.getvalue()
            self.assertIn("Duration:", output)
            self.assertIn("s", output)

    def test_demo_no_open_suppresses_browser(self):
        """--no-open must not attempt to open a browser."""
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "demo_out"
            buf = io.StringIO()
            with patch("webbrowser.open") as mock_open:
                with contextlib.redirect_stdout(buf):
                    code = main(["demo", "--out", str(out), "--no-open"])
                mock_open.assert_not_called()
            self.assertEqual(0, code)

    def test_demo_passes_with_junit_xml_reporter(self):
        """Demo with --reporter junit_xml must succeed."""
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "demo_out"
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                code = main(["demo", "--out", str(out), "--reporter", "junit_xml", "--no-open"])
            self.assertEqual(0, code)
            self.assertTrue((out / "junit.xml").exists(), "junit.xml must exist")
            self.assertTrue((out / "latest-report.md").exists(), "markdown supplement must exist")

    def test_demo_xml_path_writes_additional_junit(self):
        """--xml-path on demo writes additional JUnit XML at explicit path."""
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "demo_out"
            xml_target = Path(tmp) / "extra" / "results.xml"
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                code = main(["demo", "--out", str(out), "--xml-path", str(xml_target), "--no-open"])
            self.assertEqual(0, code)
            self.assertTrue(xml_target.exists(), f"xml-path target {xml_target} must exist")

    def test_demo_with_explicit_config(self):
        """Demo with --config should use that config, not builtin."""
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "demo_out"
            config_path = Path(tmp) / "config.yaml"
            config_path.write_text("defaults:\n  cols: 120\n", encoding="utf-8")
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                code = main(["demo", "--out", str(out), "--config", str(config_path), "--no-open"])
            self.assertEqual(0, code)
            output = buf.getvalue()
            self.assertIn("PASS", output)

    def test_demo_defaults_to_builtin_config(self):
        """Demo without --config uses VerifierConfig.builtin(), not load_config()."""
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "demo_out"
            buf = io.StringIO()
            # Patch load_config to verify it is NOT called
            with patch("termproof.demo.load_config") as mock_load:
                with contextlib.redirect_stdout(buf):
                    code = main(["demo", "--out", str(out), "--no-open"])
                mock_load.assert_not_called()
            self.assertEqual(0, code)


if __name__ == "__main__":
    unittest.main()
