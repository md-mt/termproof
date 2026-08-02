from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

# Make scripts/ importable for the corpus generator module.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import generate_corpus  # noqa: E402

_REPO_ROOT = Path(__file__).resolve().parent.parent
_CORPUS = _REPO_ROOT / "corpus"

ALL_BUILTIN_STEPS = {
    "wait_for_text",
    "wait_for_idle",
    "send_text",
    "send_line",
    "press",
    "sleep",
    "wait_for_regex",
}

ALL_BUILTIN_ASSERTIONS = {
    "output_contains",
    "output_not_contains",
    "screen_contains",
    "screen_not_contains",
    "exit_code",
    "file_exists",
    "file_contains",
    "json_schema",
}


class CorpusInventoryTest(unittest.TestCase):
    """The committed corpus covers every category required by issue #94."""

    def _recipe(self, rel: str) -> dict:
        return json.loads((_CORPUS / "recipes" / rel).read_text(encoding="utf-8"))

    def test_recipes_v1_and_legacy_committed(self) -> None:
        v1 = json.loads(
            (_CORPUS / "recipes" / "v1" / "banner-basic.recipe.json").read_text(encoding="utf-8")
        )
        self.assertEqual(1, v1["recipe_version"])
        legacy = json.loads(
            (_CORPUS / "recipes" / "legacy" / "banner-legacy.recipe.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertNotIn("recipe_version", legacy)

    def test_cli_help_for_every_public_command(self) -> None:
        help_dir = _CORPUS / "cli" / "help"
        for command, _argv in generate_corpus.PUBLIC_COMMANDS:
            safe = command.replace("-", "_")
            self.assertTrue(
                (help_dir / f"{safe}-help.txt").exists(),
                f"missing help fixture for {command}",
            )

    def test_run_flags_committed(self) -> None:
        flags = json.loads((_CORPUS / "cli" / "flags.json").read_text(encoding="utf-8"))
        for flag in generate_corpus.RUN_FLAGS:
            self.assertIn(flag, flags["run_flags"], f"missing run flag {flag}")

    def test_exit_codes_committed(self) -> None:
        rows = json.loads((_CORPUS / "cli" / "exit-codes.json").read_text(encoding="utf-8"))
        labels = {row["label"] for row in rows}
        for scenario in generate_corpus.EXIT_CODE_SCENARIOS:
            self.assertIn(scenario["label"], labels, f"missing exit-code scenario {scenario['label']}")

    def test_config_precedence_cases_committed(self) -> None:
        prec = _CORPUS / "config" / "precedence"
        for case in generate_corpus.CONFIG_CASES:
            self.assertTrue((prec / f"{case['label']}.json").exists())

    def test_normalized_result_json_markdown_junit_terminal_screenshot_cast(self) -> None:
        run_dir = _CORPUS / "runs" / "banner-basic"
        for name in ("result.json", "report.md", "final.txt", "final.svg", "session.cast"):
            self.assertTrue((run_dir / name).exists(), f"missing {name}")
        self.assertTrue((_CORPUS / "reports" / "junit.xml").exists(), "missing junit.xml")
        self.assertTrue((_CORPUS / "reports" / "latest-report.md").exists(), "missing latest-report.md")

    def test_video_cache_diff_contracts_committed(self) -> None:
        self.assertTrue((_CORPUS / "video" / "missing-tools-warning.txt").exists())
        self.assertTrue((_CORPUS / "video" / "presence-contract.json").exists())
        self.assertTrue((_CORPUS / "cache" / "cache-key-inputs.json").exists())
        self.assertTrue((_CORPUS / "diff" / "visual-diff.svg").exists())
        self.assertTrue((_CORPUS / "diff" / "diff-result.json").exists())

    def test_failure_and_partial_artifacts_committed(self) -> None:
        fail_dir = _CORPUS / "runs" / "fail-exit-code"
        result = json.loads((fail_dir / "result.json").read_text(encoding="utf-8"))
        self.assertFalse(result["passed"])
        self.assertNotEqual(0, result["exit_code"])

    def test_all_seven_builtin_steps_covered(self) -> None:
        recipe = self._recipe("v1/interact-all-steps.recipe.json")
        actions = {step["action"] for step in recipe["steps"]}
        self.assertEqual(ALL_BUILTIN_STEPS, actions)

    def test_all_eight_builtin_assertions_covered(self) -> None:
        recipe = self._recipe("v1/json-all-assertions.recipe.json")
        kinds = {assertion["type"] for assertion in recipe["assertions"]}
        self.assertEqual(ALL_BUILTIN_ASSERTIONS, kinds)

    def test_oracle_record_committed(self) -> None:
        oracle = json.loads((_CORPUS / "oracle.json").read_text(encoding="utf-8"))
        self.assertEqual(generate_corpus.ORACLE_COMMIT, oracle["oracle_commit"])
        self.assertIn("python_version", oracle)
        self.assertIn("pillow_version", oracle)


class CorpusDriftTest(unittest.TestCase):
    """Regenerating the corpus from the oracle must reproduce the committed
    fixtures exactly (after documented normalization)."""

    def test_drift_check_passes(self) -> None:
        exit_code = generate_corpus.check_drift(_CORPUS)
        self.assertEqual(0, exit_code, "corpus drift detected — regenerate with "
                         "python scripts/generate_corpus.py and commit")


if __name__ == "__main__":
    unittest.main()
