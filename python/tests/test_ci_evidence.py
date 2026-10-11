from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import yaml

from termproof import ci_evidence
from termproof.ci_evidence import compose_pr_comment, load_receipt, run_target
from termproof.evidence import STEPS_MANIFEST_NAME
from termproof.evidence_publish import NON_IMAGE_PAYLOAD_NAMES, prepare_screenshot_evidence, rewrite_screenshot_links

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
RECEIPT = ROOT / "docs" / "ci" / "evidence-receipt.json"
CI_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "python-ci.yml"
RELEASE_WORKFLOW = REPO_ROOT / ".github" / "workflows" / "python-release.yml"


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
        self.assertEqual("termproof-evidence", receipt["screenshots"]["branch"])
        self.assertIn(".svg", receipt["screenshots"]["image_extensions"])
        self.assertIn("/issues/69", receipt["screenshots"]["video_issue"])

    def test_workflows_are_receipt_backed(self) -> None:
        ci_text = CI_WORKFLOW.read_text(encoding="utf-8")
        release_text = RELEASE_WORKFLOW.read_text(encoding="utf-8")
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
            CI_WORKFLOW.read_text(encoding="utf-8")
        )
        verify = workflow["jobs"]["verify"]
        steps = verify["steps"]
        names = [step["name"] for step in steps]

        # `contents: write` is what pushes to the evidence branch. It sits on
        # this job rather than on the workflow, so the lint, test, stdlib and
        # wheel jobs cannot reach a write token; assert it where it now lives,
        # and assert the workflow default stayed read.
        self.assertEqual("read", workflow["permissions"]["contents"])
        self.assertEqual("write", verify["permissions"]["contents"])
        self.assertEqual("write", verify["permissions"]["pull-requests"])
        self.assertIn("Run base TUI verification for PR comparison", names)
        self.assertIn("Prepare screenshot evidence branch payload", names)
        self.assertIn("Publish screenshot evidence branch", names)
        self.assertIn("Compose TUI verification report", names)
        comment_step = next(
            step for step in steps if step["name"] == "Comment TUI verification report on PR"
        )
        self.assertIn(".termproof/ci-pr-comment.md", comment_step["with"]["script"])
        compose_step = next(step for step in steps if step["name"] == "Compose TUI verification report")
        self.assertIn("--screenshot-base-url", compose_step["run"])
        self.assertIn("raw.githubusercontent.com", compose_step["run"])

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
                        "screenshots": {
                            "branch": "termproof-evidence",
                            "image_extensions": [".svg"],
                            "video_issue": "https://github.com/md-mt/termproof/issues/69",
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
            base_svg = base / "demo" / "final.svg"
            head_svg = head / "demo" / "final.svg"
            base_svg.write_text("<svg />\n", encoding="utf-8")
            head_svg.write_text("<svg />\n", encoding="utf-8")
            (base / "latest-report.md").write_text(
                f"# before\n[screenshot]({base_svg}) / [video](base/demo/session.mp4)\n",
                encoding="utf-8",
            )
            (head / "latest-report.md").write_text(
                f"# after\n[screenshot]({head_svg}) / [video](head/demo/session.mp4)\n",
                encoding="utf-8",
            )

            body = compose_pr_comment(
                base,
                head,
                "https://example.test/run",
                base_label="abc123",
                head_label="def456",
                screenshot_base_url="https://raw.example/pr/1/2",
                receipt_path=receipt_path,
            )

        self.assertIn("<!-- termproof-ci-report -->", body)
        self.assertIn("PASS -> FAIL", body)
        self.assertIn("Before: base commit abc123", body)
        self.assertIn("# before", body)
        self.assertIn("After: head commit def456", body)
        self.assertIn("# after", body)
        self.assertIn("termproof-release-evidence.tgz", body)
        self.assertIn("https://raw.example/pr/1/2/base/demo/final.svg", body)
        self.assertIn("https://raw.example/pr/1/2/head/demo/final.svg", body)
        self.assertIn("base/demo/session.mp4", body)
        self.assertIn("issues/69", body)

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

    def test_prepare_screenshot_evidence_copies_images_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            base = root / "base"
            head = root / "head"
            (base / "run" / "steps").mkdir(parents=True)
            (head / "run").mkdir(parents=True)
            (base / "run" / "final.svg").write_text("<svg />\n", encoding="utf-8")
            (base / "run" / "steps" / "01.svg").write_text("<svg />\n", encoding="utf-8")
            (base / "run" / "session.mp4").write_text("video\n", encoding="utf-8")
            (head / "run" / "final.png").write_text("png\n", encoding="utf-8")

            manifest = prepare_screenshot_evidence(base, head, root / "publish", "68", "123")

            published = root / "publish" / "pr" / "68" / "123"
            self.assertTrue((published / "base" / "run" / "final.svg").is_file())
            self.assertTrue((published / "base" / "run" / "steps" / "01.svg").is_file())
            self.assertTrue((published / "head" / "run" / "final.png").is_file())
            self.assertFalse((published / "base" / "run" / "session.mp4").exists())
            self.assertEqual(3, len(manifest))

    def test_non_image_payload_names_pin_steps_manifest_name(self) -> None:
        # evidence_publish repeats the literal instead of importing evidence
        # (which would drag the replay/render stack into the CI helper); pin
        # the duplication here, where importing the producer constant is free.
        self.assertEqual({STEPS_MANIFEST_NAME}, NON_IMAGE_PAYLOAD_NAMES)

    def test_prepare_screenshot_evidence_copies_steps_manifest_alongside_images(self) -> None:
        # With dedup on, step 02 has no image of its own: only the manifest
        # records that it happened and is represented by 01's image (#160).
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            # Distinct bytes per scope: identical content would let a
            # base/head cross-copy swap pass undetected.
            steps_manifests: dict[str, str] = {}
            for scope in ("base", "head"):
                steps_manifest = (
                    json.dumps(
                        [
                            {"step": f"01-{scope}-first", "screenshot": "01-first.svg", "unchanged_from_previous": False},
                            {"step": f"02-{scope}-second", "screenshot": "01-first.svg", "unchanged_from_previous": True},
                            {"step": f"03-{scope}-third", "screenshot": "03-third.svg", "unchanged_from_previous": False},
                        ],
                        indent=2,
                    )
                    + "\n"
                )
                steps_manifests[scope] = steps_manifest
                steps = root / scope / "run" / "steps"
                steps.mkdir(parents=True)
                (steps / "01-first.svg").write_text("<svg />\n", encoding="utf-8")
                (steps / "03-third.svg").write_text("<svg />\n", encoding="utf-8")
                (steps / "steps-manifest.json").write_text(steps_manifest, encoding="utf-8")
                # An unrelated JSON file is not screenshot payload.
                (root / scope / "run" / "result.json").write_text("{}\n", encoding="utf-8")
            self.assertNotEqual(steps_manifests["base"], steps_manifests["head"])

            manifest = prepare_screenshot_evidence(root / "base", root / "head", root / "publish", "68", "123")

            published = root / "publish" / "pr" / "68" / "123"
            for scope in ("base", "head"):
                copied = published / scope / "run" / "steps" / "steps-manifest.json"
                self.assertTrue(copied.is_file(), copied)
                self.assertEqual(steps_manifests[scope], copied.read_text(encoding="utf-8"))
                self.assertTrue((published / scope / "run" / "steps" / "01-first.svg").is_file())
                self.assertTrue((published / scope / "run" / "steps" / "03-third.svg").is_file())
                self.assertFalse((published / scope / "run" / "result.json").exists())
            # The manifest rides alongside as a sibling file; it is not folded
            # into the screenshot manifest, which stays one entry per image.
            self.assertEqual(4, len(manifest))
            self.assertTrue(all(not entry["path"].endswith("steps-manifest.json") for entry in manifest))
            self.assertEqual(
                manifest,
                json.loads((published / "screenshot-manifest.json").read_text(encoding="utf-8")),
            )

    def test_rewrite_screenshot_links_leaves_video_links_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            evidence = root / "evidence"
            (evidence / "run").mkdir(parents=True)
            (evidence / "run" / "final.svg").write_text("<svg />\n", encoding="utf-8")
            report = "[screenshot]({}) / [video]({})".format(
                (evidence / "run" / "final.svg").as_posix(),
                (evidence / "run" / "session.mp4").as_posix(),
            )

            rewritten = rewrite_screenshot_links(report, evidence, "https://raw.example/head")

            self.assertIn("https://raw.example/head/run/final.svg", rewritten)
            self.assertIn((evidence / "run" / "session.mp4").as_posix(), rewritten)


    def test_load_results_missing_exit_code_is_tolerated_policy(self) -> None:
        # Policy regression test: RunResult.from_dict reads exit_code via
        # data.get (not data["exit_code"]), so a malformed ci_evidence
        # result.json missing exit_code yields exit_code=None instead of
        # raising KeyError. This is the selected, documented behavior of
        # load_results — the producer always writes exit_code, but the
        # evidence loader must not crash on legacy/truncated receipts.
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_dir = root / "demo"
            run_dir.mkdir(parents=True)
            data = {
                "recipe_name": "demo",
                "passed": True,
                # exit_code deliberately omitted
                "duration_seconds": 1.0,
                "priority": "P0",
                "execution": "scripted",
                "renderer": "default",
                "score": 1.0,
                "steps": [],
                "assertions": [],
                "artifacts": {},
            }
            (run_dir / "result.json").write_text(
                json.dumps(data), encoding="utf-8"
            )

            results = ci_evidence.load_results(root)

            self.assertEqual(1, len(results))
            self.assertIsNone(results[0].exit_code)


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
