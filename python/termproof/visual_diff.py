from __future__ import annotations

import base64
import html
import shutil
from dataclasses import replace
from pathlib import Path

from PIL import Image, ImageChops, ImageDraw, ImageFont

from .models import AssertionResult, RunResult, score_from_assertions


def apply_visual_diff(
    result: RunResult,
    baseline_root: Path,
    *,
    update: bool = False,
) -> RunResult:
    screenshot_value = result.artifacts.get("screenshot")
    artifacts = dict(result.artifacts)
    assertions = list(result.assertions)
    if not screenshot_value:
        assertions.append(
            AssertionResult("visual_diff", False, "no screenshot artifact to compare")
        )
        return _replace_result(result, assertions, artifacts)

    screenshot = Path(screenshot_value)
    baseline = _baseline_path(baseline_root, result, screenshot.suffix)
    artifacts["visual_baseline"] = str(baseline)

    if update:
        baseline.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(screenshot, baseline)
        assertions.append(
            AssertionResult("visual_diff", True, f"updated baseline: {baseline}")
        )
        return _replace_result(result, assertions, artifacts)

    if not baseline.exists():
        assertions.append(
            AssertionResult(
                "visual_diff",
                False,
                f"missing baseline: {baseline}; run with --update-baselines to create it",
            )
        )
        return _replace_result(result, assertions, artifacts)

    if _screenshots_match(baseline, screenshot):
        assertions.append(
            AssertionResult("visual_diff", True, f"matches baseline: {baseline}")
        )
        return _replace_result(result, assertions, artifacts)

    diff_path = screenshot.with_name(f"visual-diff{screenshot.suffix}")
    _write_diff_image(baseline, screenshot, diff_path)
    artifacts["visual_diff"] = str(diff_path)
    assertions.append(
        AssertionResult(
            "visual_diff",
            False,
            f"visual regression: baseline={baseline} actual={screenshot} diff={diff_path}",
        )
    )
    return _replace_result(result, assertions, artifacts)


def _replace_result(
    result: RunResult,
    assertions: list[AssertionResult],
    artifacts: dict[str, str],
) -> RunResult:
    return replace(
        result,
        passed=result.passed and all(assertion.passed for assertion in assertions),
        score=score_from_assertions(assertions),
        assertions=assertions,
        artifacts=artifacts,
    )


def _baseline_path(baseline_root: Path, result: RunResult, suffix: str) -> Path:
    return (
        baseline_root
        / _safe_path_part(result.recipe_name)
        / _safe_path_part(result.renderer)
        / f"final{suffix}"
    )


def _safe_path_part(value: str) -> str:
    safe = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in value)
    return safe or "default"


def _write_diff_image(baseline: Path, screenshot: Path, diff_path: Path) -> None:
    diff_path.parent.mkdir(parents=True, exist_ok=True)
    if screenshot.suffix.lower() == ".png" and baseline.suffix.lower() == ".png":
        _write_png_diff(baseline, screenshot, diff_path)
        return
    _write_svg_side_by_side(baseline, screenshot, diff_path.with_suffix(".svg"))


def _screenshots_match(baseline: Path, screenshot: Path) -> bool:
    if screenshot.suffix.lower() == ".png" and baseline.suffix.lower() == ".png":
        with Image.open(baseline) as baseline_image, Image.open(screenshot) as actual_image:
            baseline_rgb = baseline_image.convert("RGB")
            actual_rgb = actual_image.convert("RGB")
            if baseline_rgb.size != actual_rgb.size:
                return False
            return ImageChops.difference(baseline_rgb, actual_rgb).getbbox() is None
    return baseline.read_bytes() == screenshot.read_bytes()


def _write_png_diff(baseline: Path, screenshot: Path, diff_path: Path) -> None:
    with Image.open(baseline) as baseline_image, Image.open(screenshot) as actual_image:
        baseline_rgb = baseline_image.convert("RGB")
        actual_rgb = actual_image.convert("RGB")
        width = max(baseline_rgb.width, actual_rgb.width)
        height = max(baseline_rgb.height, actual_rgb.height)
        baseline_panel = _padded_image(baseline_rgb, width, height)
        actual_panel = _padded_image(actual_rgb, width, height)
        diff_panel = ImageChops.difference(baseline_panel, actual_panel)
        label_height = 28
        combined = Image.new("RGB", (width * 3, height + label_height), "white")
        combined.paste(baseline_panel, (0, label_height))
        combined.paste(actual_panel, (width, label_height))
        combined.paste(diff_panel, (width * 2, label_height))
        draw = ImageDraw.Draw(combined)
        font = ImageFont.load_default()
        for index, label in enumerate(("baseline", "actual", "diff")):
            draw.text((width * index + 8, 8), label, fill="black", font=font)
        combined.save(diff_path, format="PNG")


def _padded_image(image: Image.Image, width: int, height: int) -> Image.Image:
    padded = Image.new("RGB", (width, height), "white")
    padded.paste(image, (0, 0))
    return padded


def _write_svg_side_by_side(baseline: Path, screenshot: Path, diff_path: Path) -> None:
    baseline_uri = _data_uri(baseline)
    actual_uri = _data_uri(screenshot)
    width = 1200
    height = 620
    panel_width = 560
    panel_height = 520
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#f6f8fa"/>',
        '<style>text{font:16px ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;fill:#24292f}</style>',
        '<text x="24" y="32">baseline</text>',
        '<text x="616" y="32">actual</text>',
        f'<image href="{html.escape(baseline_uri)}" x="24" y="56" width="{panel_width}" height="{panel_height}" preserveAspectRatio="xMinYMin meet"/>',
        f'<image href="{html.escape(actual_uri)}" x="616" y="56" width="{panel_width}" height="{panel_height}" preserveAspectRatio="xMinYMin meet"/>',
        "</svg>",
    ]
    diff_path.write_text("\n".join(parts) + "\n", encoding="utf-8")


def _data_uri(path: Path) -> str:
    media_type = "image/png" if path.suffix.lower() == ".png" else "image/svg+xml"
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:{media_type};base64,{encoded}"
