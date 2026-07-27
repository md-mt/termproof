from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

from termproof import ci_evidence
from termproof.ci_evidence import compose_pr_comment, load_receipt, run_target


ROOT = Path(__file__).resolve().parents[1]
RECEIPT = ROOT / "docs" / "ci" / "evidence-receipt.json"


class CiEvidenceReceiptTest(unittest.TestCase):
    def test_receipt_targets_existing_recipes(self) -> None:
        receipt = load_receipt(RECEIPT)
        for target in receipt["targets"].values():
            for recipe in target["recipes"]:
                self.assertTrue((ROOT / recipe).exists(), recipe)

    def test_ci_and_release_share_evidence_suite(self) -> None:
        receipt = load_receipt(RECEIPT)
        self.assertEqual(
            receipt["targets"]["ci"]["recipes"],
            receipt["targets"]["release"]["recipes"],
        )
        self.assertEqual(True, receipt["targets"]["release"]["video"])
        self.assertEqual(60, receipt["targets"]["release"]["video_fps"])

    def test_workflows_are_receipt_backed(self) -> None:
        ci_text = (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        release_text = (ROOT / ".github" / "workflows" / "release.yml").read_text(
            encoding="utf-8"
        )
        receipt = load_receipt(RECEIPT)

        self.assertIn("python -m termproof.ci_evidence run ci", ci_text)
        self.assertIn("python -m termproof.ci_evidence run release", release_text)
        self.assertIn(receipt["targets"]["ci"]["artifact_name"], ci_text)
        self.assertIn(".termproof/pr-base", ci_text)
        self.assertIn(".termproof/ci-pr-comment.md", ci_text)
        self.assertIn(receipt["targets"]["release"]["artifact_name"], release_text)
        self.assertIn(receipt["targets"]["release"]["archive_name"], release_text)

    def test_pr_comment_step_posts_composed_report(self) -> None:
        workflow = yaml.safe_load(
            (ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        )
        steps = workflow["jobs"]["verify"]["steps"]
        names = [step["name"] for step in steps]

        self.assertIn("Run base TUI verification for PR comparison", names)
        self.assertIn("Compose TUI verification report", names)
        comment_step = next(
            step for step in steps if step["name"] == "Comment TUI verification report on PR"
        )
        self.assertIn(".termproof/ci-pr-comment.md", comment_step["with"]["script"])

    def test_run_target_uses_receipt_command_and_copies_receipt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            receipt_path = root / "receipt.json"
            receipt_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "targets": {
                            "ci": {
                                "artifact_name": "artifact",
                                "out": "out",
                                "recipes": ["recipe.json"],
                                "video": True,
                                "video_fps": 24,
                            }
                        },
                        "pr_comment": {"marker": "<!-- marker -->", "max_chars": 55000},
                    }
                ),
                encoding="utf-8",
            )

            with patch("termproof.ci_evidence.subprocess.run") as run:
                run.return_value.returncode = 0
                code = run_target("ci", root, receipt_path=receipt_path)

            self.assertEqual(0, code)
            self.assertEqual(
                [
                    "uv",
                    "run",
                    "termproof",
                    "run",
                    "recipe.json",
                    "--video",
                    "--video-fps",
                    "24",
                    "--out",
                    "out",
                ],
                run.call_args.args[0],
            )
            self.assertTrue((root / "out" / "evidence-receipt.json").is_file())

    def test_pr_comment_includes_before_after_reports_and_delta(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            receipt_path = root / "receipt.json"
            receipt_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "targets": {
                            "ci": {
                                "artifact_name": "termproof-ci-evidence",
                                "archive_name": "",
                                "out": ".termproof/ci",
                                "recipes": [],
                                "video": True,
                                "video_fps": 60,
                            },
                            "release": {
                                "artifact_name": "termproof-release-evidence",
                                "archive_name": "termproof-release-evidence.tgz",
                                "out": ".termproof/release",
                                "recipes": [],
                                "video": True,
                                "video_fps": 60,
                            },
                        },
                        "pr_comment": {
                            "marker": "<!-- termproof-ci-report -->",
                            "max_chars": 55000,
                        },
                    }
                ),
                encoding="utf-8",
            )
            base = root / "base"
            head = root / "head"
            _write_result(base, True)
            _write_result(head, False)
            (base / "latest-report.md").write_text("# before\n", encoding="utf-8")
            (head / "latest-report.md").write_text("# after\n", encoding="utf-8")

            body = compose_pr_comment(
                base,
                head,
                "https://example.test/run",
                base_label="abc123",
                head_label="def456",
                receipt_path=receipt_path,
            )

        self.assertIn("<!-- termproof-ci-report -->", body)
        self.assertIn("PASS -> FAIL", body)
        self.assertIn("Before: base commit abc123", body)
        self.assertIn("# before", body)
        self.assertIn("After: head commit def456", body)
        self.assertIn("# after", body)
        self.assertIn("termproof-release-evidence.tgz", body)

    def test_absolute_artifact_paths_are_normalized_to_artifact_relative(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            out = root / ".termproof" / "pr-base"
            run_dir = out / "demo"
            run_dir.mkdir(parents=True)
            absolute_svg = run_dir / "final.svg"
            (out / "latest-report.md").write_text(
                f"[screenshot]({absolute_svg})\n",
                encoding="utf-8",
            )
            (run_dir / "report.md").write_text(
                f"- screenshot: `{absolute_svg}`\n",
                encoding="utf-8",
            )
            (run_dir / "result.json").write_text(
                json.dumps({"artifacts": {"screenshot": str(absolute_svg)}}),
                encoding="utf-8",
            )

            with patch("termproof.ci_evidence.Path.cwd", return_value=root):
                ci_evidence._normalize_artifact_paths(out)

            self.assertIn(
                "(.termproof/pr-base/demo/final.svg)",
                (out / "latest-report.md").read_text(encoding="utf-8"),
            )
            data = json.loads((run_dir / "result.json").read_text(encoding="utf-8"))
            self.assertEqual(
                ".termproof/pr-base/demo/final.svg",
                data["artifacts"]["screenshot"],
            )


def _write_result(root: Path, passed: bool) -> None:
    run_dir = root / "demo"
    run_dir.mkdir(parents=True)
    (run_dir / "result.json").write_text(
        json.dumps(
            {
                "recipe_name": "demo",
                "passed": passed,
                "exit_code": 0 if passed else 1,
                "duration_seconds": 1.0,
                "priority": "P0",
                "execution": "scripted",
                "renderer": "default",
                "score": 1.0 if passed else 0.0,
                "steps": [],
                "assertions": [],
                "artifacts": {},
            }
        ),
        encoding="utf-8",
    )


if __name__ == "__main__":
    unittest.main()
