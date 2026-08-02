from __future__ import annotations

import json
import re
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

# Make scripts/ importable for the corpus generator module.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import generate_corpus  # noqa: E402

_REPO_ROOT = Path(__file__).resolve().parent.parent
_CORPUS = _REPO_ROOT / "corpus"


def _runtime_steps() -> set[str]:
    """Authoritative built-in step names from the runtime registry."""
    from termproof.config import BUILTIN_DEFAULTS

    return set(BUILTIN_DEFAULTS["steps"])


def _runtime_assertions() -> set[str]:
    """Authoritative built-in assertion names from the runtime registry."""
    from termproof.config import BUILTIN_DEFAULTS

    return set(BUILTIN_DEFAULTS["assertions"])


def _extract_flags_from_help(text: str) -> list[str]:
    """Extract the public --flags argparse actually exposes in --help output.

    Parsed from the verbatim parser help (committed under corpus/cli/help), so
    this is an independently derived inventory, not a generator constant.
    """
    flags: list[str] = []
    for line in text.splitlines():
        match = re.match(r"^\s+(--[a-z0-9-]+)", line)
        if match and match.group(1) != "--help":
            flag = match.group(1)
            if flag not in flags:
                flags.append(flag)
    return flags


def _extract_subcommands_from_help(text: str) -> list[str]:
    """Extract subcommand names from an argparse usage line like {list,search}."""
    first = text.splitlines()[0] if text.splitlines() else ""
    match = re.search(r"\{([a-z_,]+)\}", first)
    if not match:
        return []
    return [part for part in match.group(1).split(",") if part]


def _flags_from_committed_help() -> dict:
    """Re-derive the complete flag inventory from the committed help files."""
    help_dir = _CORPUS / "cli" / "help"
    run_flags = _extract_flags_from_help((help_dir / "run-help.txt").read_text(encoding="utf-8"))
    other: dict[str, list[str]] = {}
    for command, _argv in generate_corpus.PUBLIC_COMMANDS:
        if command in ("termproof", "run"):
            continue
        safe = command.replace("-", "_")
        text = (help_dir / f"{safe}-help.txt").read_text(encoding="utf-8")
        subcommands = _extract_subcommands_from_help(text)
        other[safe] = subcommands if subcommands else _extract_flags_from_help(text)
    return {"public_commands": [c for c, _ in generate_corpus.PUBLIC_COMMANDS], "run_flags": run_flags, "other_command_flags": other}


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

    def test_other_command_flags_derived_from_parser_help(self) -> None:
        """Every non-run flag in flags.json must match the verbatim argparse
        help output; no generator constant may silently drift from the parser."""
        committed = json.loads((_CORPUS / "cli" / "flags.json").read_text(encoding="utf-8"))
        derived = _flags_from_committed_help()
        self.assertEqual(derived["public_commands"], committed["public_commands"])
        self.assertEqual(derived["run_flags"], committed["run_flags"])
        self.assertEqual(derived["other_command_flags"], committed["other_command_flags"])

    def test_plugins_list_config_flag_committed(self) -> None:
        """plugins list --config is a public flag (termproof/cli.py:65-67) and
        must be present in the flag inventory and in the help fixture."""
        flags = json.loads((_CORPUS / "cli" / "flags.json").read_text(encoding="utf-8"))
        self.assertIn("plugins_list", flags["other_command_flags"])
        self.assertIn("--config", flags["other_command_flags"]["plugins_list"])
        help_text = (_CORPUS / "cli" / "help" / "plugins_list-help.txt").read_text(encoding="utf-8")
        self.assertIn("--config", help_text)

    def test_exit_codes_committed(self) -> None:
        rows = json.loads((_CORPUS / "cli" / "exit-codes.json").read_text(encoding="utf-8"))
        labels = {row["label"] for row in rows}
        for scenario in generate_corpus.EXIT_CODE_SCENARIOS:
            self.assertIn(scenario["label"], labels, f"missing exit-code scenario {scenario['label']}")

    def test_config_precedence_cases_committed(self) -> None:
        prec = _CORPUS / "config" / "precedence"
        for case in generate_corpus.CONFIG_CASES:
            self.assertTrue((prec / f"{case['label']}.json").exists())

    def test_config_precedence_hermetic_builtin_only(self) -> None:
        """builtin-only must resolve to builtin defaults even when the ambient
        (real) home has a termproof config — generation is host-independent."""
        builtin = json.loads(
            (_CORPUS / "config" / "precedence" / "builtin-only.json").read_text(encoding="utf-8")
        )
        self.assertEqual(3.0, builtin["resolved"]["defaults"]["idle_cap_seconds"])
        self.assertEqual("", builtin["resolved"]["docker"]["image"])

    def test_config_precedence_layered_partial_keys(self) -> None:
        """A higher-precedence file that provides only one key must win that
        key while lower-precedence partial keys survive (per-key layering)."""
        case = json.loads(
            (_CORPUS / "config" / "precedence" / "termproof-user-wins.json").read_text(
                encoding="utf-8"
            )
        )
        # legacy user provides idle + docker.image; termproof user provides idle only
        self.assertEqual(2.5, case["resolved"]["defaults"]["idle_cap_seconds"])
        self.assertEqual("legacy-img", case["resolved"]["docker"]["image"])

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

    def test_video_tools_present_contract_executed(self) -> None:
        """The tools-present video success path must be exercised with a
        deterministic fake backend that writes a sentinel session.mp4, and the
        returned artifact registration must be committed."""
        contract_path = _CORPUS / "video" / "tools-present-contract.json"
        self.assertTrue(contract_path.exists(), "missing tools-present-contract.json")
        contract = json.loads(contract_path.read_text(encoding="utf-8"))
        self.assertTrue(contract["requested_video"])
        self.assertTrue(contract["video_artifact_present"])
        self.assertEqual("session.mp4", contract["artifact_name"])
        self.assertEqual("video", contract["artifact_key"])

    def test_cache_miss_then_hit_executed(self) -> None:
        """A real cache miss followed by a hit must be committed: stored cache
        entry plus the normalized cached RunResult with the <cache> marker."""
        entry_path = _CORPUS / "cache" / "cache-entry.json"
        hit_path = _CORPUS / "cache" / "cache-hit-result.json"
        self.assertTrue(entry_path.exists(), "missing cache-entry.json")
        self.assertTrue(hit_path.exists(), "missing cache-hit-result.json")
        entry = json.loads(entry_path.read_text(encoding="utf-8"))
        self.assertIn("key", entry)
        self.assertIn("result", entry)
        self.assertTrue(entry["result"]["passed"])
        hit = json.loads(hit_path.read_text(encoding="utf-8"))
        self.assertTrue(hit["passed"])
        self.assertEqual("<cache>", hit["artifacts"]["cache"])
        self.assertEqual(0.0, hit["duration_seconds"])

    def test_failure_classes_committed(self) -> None:
        """Each required executable failure class has a committed run with
        passed=false, a normalized diagnostic, and the expected surviving
        partial artifacts. Enumerated from the committed failure manifest."""
        manifest_path = _CORPUS / "failures" / "manifest.json"
        self.assertTrue(manifest_path.exists(), "missing failure manifest")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        required = {entry["failure_class"] for entry in manifest["required"]}
        self.assertEqual(
            {
                "step-timeout",
                "step-regex-timeout",
                "step-input-invalid",
                "send-exception",
                "process-timeout",
                "launch-failure",
                "plugin-exception",
            },
            required,
        )
        for entry in manifest["required"]:
            run_dir = _CORPUS / "runs" / entry["id"]
            result = json.loads((run_dir / "result.json").read_text(encoding="utf-8"))
            self.assertFalse(result["passed"], f"{entry['id']} must fail")
            # Normalized diagnostic present in a failed step or assertion.
            all_details = " | ".join(
                [s.get("detail", "") for s in result.get("steps", [])]
                + [a.get("detail", "") for a in result.get("assertions", [])]
            )
            self.assertIn(entry["expected_diagnostic"], all_details, f"{entry['id']} diagnostic")
            for artifact in entry["surviving_artifacts"]:
                self.assertTrue(
                    (run_dir / artifact).exists(),
                    f"{entry['id']} missing partial artifact {artifact}",
                )

    def test_all_seven_builtin_steps_covered(self) -> None:
        recipe = self._recipe("v1/interact-all-steps.recipe.json")
        actions = {step["action"] for step in recipe["steps"]}
        self.assertEqual(_runtime_steps(), actions)

    def test_all_eight_builtin_assertions_covered(self) -> None:
        recipe = self._recipe("v1/json-all-assertions.recipe.json")
        kinds = {assertion["type"] for assertion in recipe["assertions"]}
        self.assertEqual(_runtime_assertions(), kinds)

    def test_builtin_inventories_derived_from_runtime_registry(self) -> None:
        """The corpus test must not duplicate hard-coded step/assertion sets;
        the authoritative names come from termproof.config.BUILTIN_DEFAULTS."""
        self.assertEqual(7, len(_runtime_steps()))
        self.assertEqual(8, len(_runtime_assertions()))
        self.assertIn("wait_for_text", _runtime_steps())
        self.assertIn("json_schema", _runtime_assertions())

    def test_oracle_record_committed(self) -> None:
        oracle = json.loads((_CORPUS / "oracle.json").read_text(encoding="utf-8"))
        self.assertEqual(generate_corpus.ORACLE_COMMIT, oracle["oracle_commit"])
        self.assertIn("python_version", oracle)
        self.assertIn("pillow_version", oracle)

    def test_oracle_provenance_verified(self) -> None:
        """The committed oracle record must carry a source-tree digest that
        matches the live termproof/ tree; editing oracle source without an
        intentional oracle-commit update fails this check."""
        oracle = json.loads((_CORPUS / "oracle.json").read_text(encoding="utf-8"))
        self.assertIn("oracle_source_sha256", oracle)
        self.assertEqual(generate_corpus.compute_oracle_source_sha256(), oracle["oracle_source_sha256"])

    def test_duration_semantics_validated_before_normalization(self) -> None:
        """Normalization must reject invalid durations (negative / NaN / Inf)
        instead of silently mapping them to 0.0."""
        with self.assertRaises(ValueError):
            generate_corpus.normalize_result_json('{"duration_seconds": -1.0}')
        with self.assertRaises(ValueError):
            generate_corpus.normalize_result_json('{"duration_seconds": NaN}')
        with self.assertRaises(ValueError):
            generate_corpus.normalize_result_json('{"duration_seconds": Infinity}')
        with self.assertRaises(ValueError):
            generate_corpus.normalize_result_json('{"duration_seconds": "fast"}')
        # Valid durations still normalize to 0.0.
        normalized = generate_corpus.normalize_result_json('{"duration_seconds": 1.5}')
        self.assertEqual(0.0, json.loads(normalized)["duration_seconds"])

    def test_junit_normalizes_build_provenance(self) -> None:
        """JUnit build-provenance properties must not depend on the machine
        that regenerated the corpus (this is what CI caught on py3.11/3.13)."""
        oracle_env = (
            '<?xml version="1.0"?><testsuites name="termproof" tests="1" time="1.234" '
            'timestamp="2026-08-02T07:00:00+00:00" hostname="ci-runner">'
            '<testsuite name="termproof-installed" tests="1" time="1.234">'
            '<properties><property name="version" value="Python 3.12.12" />'
            '<property name="git_commit" value="165c367ca0b0e2a4663a8773ee18b67c2264979c" />'
            "</properties><testcase classname=\"scripted\" name=\"banner-basic\" time=\"1.234\">"
            "<system-out>Steps:\n  PASS wait: found 'x'\n</system-out></testcase></testsuite></testsuites>"
        )
        other_env = oracle_env.replace(
            'value="Python 3.12.12"', 'value="Python 3.13.0"'
        ).replace(
            'value="165c367ca0b0e2a4663a8773ee18b67c2264979c"',
            'value="51c3a7bbc2266f974ffb798aece7c0f51fcdab61"',
        )
        self.assertEqual(
            generate_corpus.normalize_junit_xml(oracle_env),
            generate_corpus.normalize_junit_xml(other_env),
        )
        normalized = generate_corpus.normalize_junit_xml(oracle_env)
        self.assertIn('value="Python 3.x"', normalized)
        self.assertIn('value="<oracle-commit>"', normalized)
        self.assertIn('timestamp="1970-01-01T00:00:00+00:00"', normalized)
        self.assertIn('hostname="localhost"', normalized)

    def test_oracle_record_normalizes_environment_metadata(self) -> None:
        """python_version/pillow_version describe the machine that generated
        the corpus; the drift comparison must ignore them so CI on any
        supported Python can verify the committed fixtures."""
        oracle_env = json.dumps(
            {
                "oracle_commit": "165c367ca0b0e2a4663a8773ee18b67c2264979c",
                "termproof_version": "0.2.1",
                "generator": "scripts/generate_corpus.py",
                "python_version": "3.12.12",
                "pillow_version": "12.3.0",
                "generated_at": "2026-08-02T07:34:24+00:00",
            }
        )
        other_env = json.dumps(
            {
                "oracle_commit": "165c367ca0b0e2a4663a8773ee18b67c2264979c",
                "termproof_version": "0.2.1",
                "generator": "scripts/generate_corpus.py",
                "python_version": "3.13.0",
                "pillow_version": "11.0.0",
                "generated_at": "2026-08-02T09:00:00+00:00",
            }
        )
        self.assertEqual(
            generate_corpus.normalize_oracle_json(oracle_env),
            generate_corpus.normalize_oracle_json(other_env),
        )
        self.assertIn('"oracle_commit"', generate_corpus.normalize_oracle_json(oracle_env))


class CorpusDriftTest(unittest.TestCase):
    """Regenerating the corpus from the oracle must reproduce the committed
    fixtures exactly (after documented normalization)."""

    def test_drift_check_passes(self) -> None:
        exit_code = generate_corpus.check_drift(_CORPUS)
        self.assertEqual(0, exit_code, "corpus drift detected — regenerate with "
                         "python scripts/generate_corpus.py and commit")

    def test_drift_rejects_committed_only_extra(self) -> None:
        """A fixture that the generator no longer produces must fail the drift
        gate with EXTRA IN COMMITTED (stale committed artifacts are visible)."""
        with tempfile.TemporaryDirectory() as tmp:
            committed = Path(tmp) / "committed"
            shutil.copytree(_CORPUS, committed)
            (committed / "unexpected-extra-fixture.json").write_text("{}\n", encoding="utf-8")
            with patch("sys.stdout") as fake_stdout:
                import io

                fake_stdout.write = io.StringIO().write
                rc = generate_corpus.check_drift(committed)
                # capture printed output via contextlib
                import contextlib

                buf = io.StringIO()
                with contextlib.redirect_stdout(buf):
                    rc = generate_corpus.check_drift(committed)
            self.assertEqual(1, rc)
            self.assertIn("EXTRA IN COMMITTED: unexpected-extra-fixture.json", buf.getvalue())

    def test_drift_rejects_missing_optional_output(self) -> None:
        """A fixture the generator now produces but that is absent from the
        committed corpus must fail with MISSING IN COMMITTED."""
        with tempfile.TemporaryDirectory() as tmp:
            committed = Path(tmp) / "committed"
            shutil.copytree(_CORPUS, committed)
            (committed / "runs" / "banner-basic" / "result.json").unlink()
            import contextlib
            import io

            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                rc = generate_corpus.check_drift(committed)
            self.assertEqual(1, rc)
            self.assertIn("MISSING IN COMMITTED: runs/banner-basic/result.json", buf.getvalue())

    def test_drift_allowlists_static_committed_file(self) -> None:
        """Intentionally static files (normalization-policy.md) are not
        generated and must not fail the symmetric drift gate."""
        with tempfile.TemporaryDirectory() as tmp:
            committed = Path(tmp) / "committed"
            shutil.copytree(_CORPUS, committed)
            # A static file is present committed but absent from fresh output.
            self.assertTrue((committed / "normalization-policy.md").exists())
            self.assertEqual(
                generate_corpus.STATIC_COMMITTED_FILES,
                {"normalization-policy.md"},
            )

    def test_drift_check_has_no_repository_side_effects(self) -> None:
        """--check must be read-only with respect to the checkout: no fixture
        app writes under the real repo and no committed path is deleted."""
        apps = _CORPUS / "apps"
        before = {p.name for p in apps.iterdir()}
        repo_termproof_before = (_REPO_ROOT / ".termproof" / "corpus").exists()
        rc = generate_corpus.check_drift(_CORPUS)
        self.assertEqual(0, rc)
        after = {p.name for p in apps.iterdir()}
        self.assertEqual(before, after, "fixture app wrote into the real corpus/apps")
        self.assertEqual(
            repo_termproof_before,
            (_REPO_ROOT / ".termproof" / "corpus").exists(),
            "exit-code scenario wrote under REPO_ROOT/.termproof/corpus",
        )


if __name__ == "__main__":
    unittest.main()
