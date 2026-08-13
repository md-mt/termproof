from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from PIL import Image

from termproof.models import RunResult
from termproof.visual_diff import apply_visual_diff


class VisualDiffTest(unittest.TestCase):
    def test_update_baselines_writes_current_screenshot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            screenshot = root / "run" / "final.svg"
            screenshot.parent.mkdir()
            screenshot.write_text("<svg>current</svg>\n", encoding="utf-8")

            result = apply_visual_diff(_result(screenshot), root / "baselines", update=True)

            baseline = root / "baselines" / "recipe" / "default" / "final.svg"
            self.assertTrue(result.passed)
            self.assertEqual(screenshot.read_text(encoding="utf-8"), baseline.read_text(encoding="utf-8"))
            self.assertEqual(str(baseline), result.artifacts["visual_baseline"])

    def test_missing_baseline_fails_with_actionable_message(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            screenshot = root / "run" / "final.svg"
            screenshot.parent.mkdir()
            screenshot.write_text("<svg>current</svg>\n", encoding="utf-8")

            result = apply_visual_diff(_result(screenshot), root / "baselines")

            self.assertFalse(result.passed)
            self.assertIn("missing baseline", result.assertions[-1].detail)
            self.assertIn("--update-baselines", result.assertions[-1].detail)

    def test_matching_baseline_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            screenshot = root / "run" / "final.svg"
            baseline = root / "baselines" / "recipe" / "default" / "final.svg"
            screenshot.parent.mkdir()
            baseline.parent.mkdir(parents=True)
            screenshot.write_text("<svg>same</svg>\n", encoding="utf-8")
            baseline.write_text("<svg>same</svg>\n", encoding="utf-8")

            result = apply_visual_diff(_result(screenshot), root / "baselines")

            self.assertTrue(result.passed)
            self.assertIn("matches baseline", result.assertions[-1].detail)

    def test_svg_difference_writes_side_by_side_diff(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            screenshot = root / "run" / "final.svg"
            baseline = root / "baselines" / "recipe" / "default" / "final.svg"
            screenshot.parent.mkdir()
            baseline.parent.mkdir(parents=True)
            screenshot.write_text("<svg>actual</svg>\n", encoding="utf-8")
            baseline.write_text("<svg>baseline</svg>\n", encoding="utf-8")

            result = apply_visual_diff(_result(screenshot), root / "baselines")

            diff_path = screenshot.with_name("visual-diff.svg")
            self.assertFalse(result.passed)
            self.assertTrue(diff_path.is_file())
            self.assertEqual(str(diff_path), result.artifacts["visual_diff"])

    def test_png_difference_writes_pixel_diff(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            screenshot = root / "run" / "final.png"
            baseline = root / "baselines" / "recipe" / "default" / "final.png"
            screenshot.parent.mkdir()
            baseline.parent.mkdir(parents=True)
            Image.new("RGB", (20, 20), "red").save(screenshot)
            Image.new("RGB", (20, 20), "blue").save(baseline)

            result = apply_visual_diff(_result(screenshot), root / "baselines")

            diff_path = screenshot.with_name("visual-diff.png")
            self.assertFalse(result.passed)
            self.assertTrue(diff_path.is_file())
            with Image.open(diff_path) as image:
                self.assertEqual("PNG", image.format)


def _result(screenshot: Path) -> RunResult:
    return RunResult(
        recipe_name="recipe",
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


if __name__ == "__main__":
    unittest.main()
